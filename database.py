# =============================================================================
# database.py — LUMINIH2 Persistent Data Layer
# SQLite tick storage · trend queries · session management
# Version: 1.0
# =============================================================================
#
# PURPOSE:
#   Persist every simulation tick to a local SQLite database so that:
#   - Degradation trends are visible across days and weeks
#   - Physics models can be validated against real measurements
#   - Investment reports use real accumulated data, not just session data
#   - The dashboard can show 7-day / 30-day history charts
#
# DATABASE FILE:
#   Default: luminih2_data.db (same directory as main.py)
#   Override: set DB_PATH environment variable
#
# SCHEMA:
#   Table: ticks      — one row per simulation tick (10 seconds)
#   Table: sessions   — one row per Streamlit session (start/end/summary)
#   Table: alerts     — persistent alert log with timestamps
#
# USAGE:
#   from database import Database
#   db = Database()                         # opens / creates the DB
#   db.write_tick(state)                    # call after every tick
#   df = db.read_history(days=7)            # returns pandas DataFrame
#   df = db.read_daily_summary(days=30)     # daily aggregates for Tab 6
#   db.close()
#
# INTEGRATION:
#   In core_engine.py TickEngine.run():
#       state, fc = ...
#       if self.db:
#           self.db.write_tick(state)
#       return state, fc
#
# NOTE:
#   All writes are batched — SQLite WAL mode is used so reads never block
#   writes. The database is safe to query from the Streamlit main thread
#   while the tick loop writes from a background update.
# =============================================================================

from __future__ import annotations

import logging
import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger("Database")

# Default database path — next to main.py, or override via env var
DB_PATH: str = os.environ.get("LUMINIH2_DB", "luminih2_data.db")

# How many ticks to buffer before flushing to disk (reduces I/O)
WRITE_BATCH_SIZE: int = 6   # flush every 6 ticks = 60 seconds


# =============================================================================
# Schema
# =============================================================================

_CREATE_TICKS = """
CREATE TABLE IF NOT EXISTS ticks (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                  TEXT    NOT NULL,           -- ISO timestamp (Zagreb UTC+2)
    tick                INTEGER NOT NULL,
    session_id          TEXT    NOT NULL,

    -- Generation
    solar_kw            REAL,
    wind_kw             REAL,
    total_gen_kw        REAL,
    wx_irradiance       REAL,
    wx_wind_ms          REAL,
    wx_temp_c           REAL,
    wx_soiling          REAL,

    -- BESS
    bess_soc_pct        REAL,
    bess_soh_pct        REAL,
    bess_temp_c         REAL,
    bess_charge_kw      REAL,

    -- Electrolyzer
    elec_kw             REAL,
    elec_eff_pct        REAL,
    elec_soh_pct        REAL,
    elec_purity         REAL,
    h2_kg_h             REAL,

    -- H2 storage chain
    buffer_pct          REAL,
    main_tank_pct       REAL,
    hrs_pct             REAL,
    pressure_bar        REAL,
    tank_temp_c         REAL,
    compressor_on       INTEGER,   -- 0/1

    -- Fuel cell
    fc_kw               REAL,
    fc_eff_pct          REAL,

    -- Grid
    grid_export_kw      REAL,
    grid_import_kw      REAL,
    ev_kw               REAL,

    -- Economics
    lcoh                REAL,
    cum_h2_kg           REAL,
    cum_revenue_eur     REAL,
    cum_co2_kg          REAL,

    -- Safety flags
    leak_detected       INTEGER,   -- 0/1
    fc_h2_shortage      INTEGER    -- 0/1
);
"""

_CREATE_SESSIONS = """
CREATE TABLE IF NOT EXISTS sessions (
    id              TEXT    PRIMARY KEY,   -- UUID / timestamp string
    started_at      TEXT    NOT NULL,
    ended_at        TEXT,
    total_ticks     INTEGER DEFAULT 0,
    total_h2_kg     REAL    DEFAULT 0,
    total_revenue   REAL    DEFAULT 0,
    notes           TEXT
);
"""

_CREATE_ALERTS = """
CREATE TABLE IF NOT EXISTS alerts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT    NOT NULL,
    session_id  TEXT    NOT NULL,
    level       TEXT    NOT NULL,    -- 'error' | 'warning' | 'info'
    code        TEXT    NOT NULL,
    message     TEXT    NOT NULL
);
"""

_CREATE_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_ticks_ts         ON ticks (ts);",
    "CREATE INDEX IF NOT EXISTS idx_ticks_session    ON ticks (session_id);",
    "CREATE INDEX IF NOT EXISTS idx_alerts_session   ON alerts (session_id);",
]


# =============================================================================
# Database class
# =============================================================================

class Database:
    """
    SQLite persistence layer for LUMINIH2 tick data.

    Thread safety: SQLite in WAL mode is safe for one writer + many readers.
    Streamlit runs on a single thread per session, so this is always safe.

    Usage:
        db = Database()
        db.write_tick(state)
        df = db.read_history(days=7)
        db.close()
    """

    def __init__(
        self,
        path:       str = DB_PATH,
        batch_size: int = WRITE_BATCH_SIZE,
    ) -> None:
        self.path       = path
        self.batch_size = batch_size
        self._batch:    list = []
        self._session_id = datetime.now(timezone(timedelta(hours=2))).strftime(
            "%Y%m%d_%H%M%S")

        self._conn = sqlite3.connect(
            self.path,
            check_same_thread=False,
            isolation_level=None,   # autocommit — we manage transactions manually
        )
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA cache_size=4000")
        self._init_schema()
        self._register_session()
        logger.info("Database opened: %s (session %s)", self.path, self._session_id)

    # ------------------------------------------------------------------
    # Schema init
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        c = self._conn
        c.execute(_CREATE_TICKS)
        c.execute(_CREATE_SESSIONS)
        c.execute(_CREATE_ALERTS)
        for idx in _CREATE_INDICES:
            c.execute(idx)

    def _register_session(self) -> None:
        now = self._now_str()
        self._conn.execute(
            "INSERT OR IGNORE INTO sessions (id, started_at) VALUES (?, ?)",
            (self._session_id, now))

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def write_tick(self, state) -> None:
        """
        Buffer one TickState and flush to disk every WRITE_BATCH_SIZE ticks.

        Args:
            state : TickState object from core_engine.py
        """
        row = (
            self._now_str(),
            getattr(state, "tick", 0),
            self._session_id,
            # Generation
            getattr(state, "solar_kw",       None),
            getattr(state, "wind_kw",        None),
            getattr(state, "total_gen_kw",   None),
            getattr(state, "wx_irradiance",  None),
            getattr(state, "wx_wind_ms",     None),
            getattr(state, "wx_temp_c",      None),
            getattr(state, "wx_soiling",     None),
            # BESS
            getattr(state, "bess_soc_pct",   None),
            getattr(state, "bess_soh_pct",   None),
            getattr(state, "bess_temp_c",    None),
            getattr(state, "bess_charge_kw", None),
            # Electrolyzer
            getattr(state, "elec_kw",        None),
            getattr(state, "elec_eff_pct",   None),
            getattr(state, "elec_soh_pct",   None),
            getattr(state, "elec_purity",    None),
            getattr(state, "h2_kg_h",        None),
            # H2 chain
            getattr(state, "buffer_pct",     None),
            getattr(state, "main_tank_pct",  None),
            getattr(state, "hrs_pct",        None),
            getattr(state, "pressure_bar",   None),
            getattr(state, "tank_temp_c",    None),
            int(getattr(state, "compressor_on",  False)),
            # Fuel cell
            getattr(state, "fc_kw",          None),
            getattr(state, "fc_eff_pct",     None),
            # Grid
            getattr(state, "grid_export_kw", None),
            getattr(state, "grid_import_kw", None),
            getattr(state, "ev_kw",          None),
            # Economics
            getattr(state, "lcoh",           None),
            getattr(state, "cum_h2_kg",      None),
            getattr(state, "cum_revenue_eur",None),
            getattr(state, "cum_co2_kg",     None),
            # Safety
            int(getattr(state, "leak_detected",   False)),
            int(getattr(state, "fc_h2_shortage",  False)),
        )
        self._batch.append(row)
        if len(self._batch) >= self.batch_size:
            self._flush()

    def write_alert(self, level: str, code: str, message: str) -> None:
        """Persist an alert to the alerts table."""
        self._conn.execute(
            "INSERT INTO alerts (ts, session_id, level, code, message) "
            "VALUES (?, ?, ?, ?, ?)",
            (self._now_str(), self._session_id, level, code, message))

    def _flush(self) -> None:
        """Write buffered rows to disk in one transaction."""
        if not self._batch:
            return
        cols = ("ts,tick,session_id,solar_kw,wind_kw,total_gen_kw,"
                "wx_irradiance,wx_wind_ms,wx_temp_c,wx_soiling,"
                "bess_soc_pct,bess_soh_pct,bess_temp_c,bess_charge_kw,"
                "elec_kw,elec_eff_pct,elec_soh_pct,elec_purity,h2_kg_h,"
                "buffer_pct,main_tank_pct,hrs_pct,pressure_bar,tank_temp_c,"
                "compressor_on,fc_kw,fc_eff_pct,grid_export_kw,grid_import_kw,"
                "ev_kw,lcoh,cum_h2_kg,cum_revenue_eur,cum_co2_kg,"
                "leak_detected,fc_h2_shortage")
        n   = cols.count(",") + 1
        ph  = ",".join(["?"] * n)
        self._conn.execute("BEGIN")
        self._conn.executemany(
            f"INSERT INTO ticks ({cols}) VALUES ({ph})",
            self._batch)
        self._conn.execute("COMMIT")
        self._batch.clear()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def read_history(self, days: int = 7) -> pd.DataFrame:
        """
        Return tick data for the last N days as a DataFrame.

        Args:
            days : number of days to look back (default 7)

        Returns:
            DataFrame with all tick columns, indexed by timestamp
        """
        cutoff = (datetime.now(timezone(timedelta(hours=2)))
                  .replace(hour=0, minute=0, second=0)
                  .isoformat())
        # Approximate cutoff by row count if timestamp comparison is slow
        query = f"""
            SELECT * FROM ticks
            WHERE ts >= datetime('now', '-{days} days')
            ORDER BY ts ASC
        """
        try:
            df = pd.read_sql_query(query, self._conn, parse_dates=["ts"])
            df = df.set_index("ts")
            logger.info("read_history(%d days): %d rows", days, len(df))
            return df
        except Exception as exc:
            logger.error("read_history failed: %s", exc)
            return pd.DataFrame()

    def read_daily_summary(self, days: int = 30) -> pd.DataFrame:
        """
        Return daily aggregated KPIs for the last N days.

        Useful for Tab 6 annual simulation charts that need real historical
        data rather than simulated projections.

        Returns:
            DataFrame with columns: date, h2_kg, revenue_eur, avg_lcoh,
            solar_kwh, wind_kwh, elec_hours, avg_bess_soc, peak_h2_g_h
        """
        query = f"""
            SELECT
                DATE(ts)                        AS date,
                SUM(h2_kg_h * 10.0 / 3600.0)   AS h2_kg,
                MAX(cum_revenue_eur) -
                  MIN(cum_revenue_eur)           AS revenue_eur,
                AVG(lcoh)                       AS avg_lcoh,
                SUM(solar_kw * 10.0 / 3600.0)  AS solar_kwh,
                SUM(wind_kw  * 10.0 / 3600.0)  AS wind_kwh,
                SUM(CASE WHEN elec_kw > 0.74
                    THEN 10.0/3600.0 ELSE 0 END) AS elec_hours,
                AVG(bess_soc_pct)               AS avg_bess_soc,
                MAX(h2_kg_h * 1000.0)           AS peak_h2_g_h
            FROM ticks
            WHERE ts >= datetime('now', '-{days} days')
            GROUP BY DATE(ts)
            ORDER BY date ASC
        """
        try:
            df = pd.read_sql_query(query, self._conn, parse_dates=["date"])
            return df
        except Exception as exc:
            logger.error("read_daily_summary failed: %s", exc)
            return pd.DataFrame()

    def read_session_summary(self) -> dict:
        """Return KPI summary for the current session."""
        query = """
            SELECT
                COUNT(*)                        AS tick_count,
                MAX(cum_h2_kg)                  AS total_h2_kg,
                MAX(cum_revenue_eur)            AS total_revenue,
                AVG(lcoh)                       AS avg_lcoh,
                MIN(bess_soc_pct)               AS min_soc,
                MAX(bess_temp_c)                AS max_bess_temp,
                SUM(CASE WHEN leak_detected=1
                    THEN 1 ELSE 0 END)          AS leak_events
            FROM ticks
            WHERE session_id = ?
        """
        try:
            row = self._conn.execute(query, (self._session_id,)).fetchone()
            if row:
                return {
                    "tick_count":    row[0],
                    "total_h2_kg":   row[1] or 0.0,
                    "total_revenue": row[2] or 0.0,
                    "avg_lcoh":      row[3] or 0.0,
                    "min_soc":       row[4] or 0.0,
                    "max_bess_temp": row[5] or 0.0,
                    "leak_events":   row[6] or 0,
                }
        except Exception as exc:
            logger.error("read_session_summary failed: %s", exc)
        return {}

    def read_alert_log(self, days: int = 7) -> pd.DataFrame:
        """Return alert history for the last N days."""
        query = f"""
            SELECT ts, level, code, message, session_id
            FROM alerts
            WHERE ts >= datetime('now', '-{days} days')
            ORDER BY ts DESC
        """
        try:
            return pd.read_sql_query(query, self._conn, parse_dates=["ts"])
        except Exception as exc:
            logger.error("read_alert_log failed: %s", exc)
            return pd.DataFrame()

    def db_size_mb(self) -> float:
        """Return database file size in MB."""
        try:
            return round(Path(self.path).stat().st_size / 1_048_576, 2)
        except FileNotFoundError:
            return 0.0

    def row_count(self) -> int:
        """Return total number of tick rows stored."""
        try:
            return self._conn.execute(
                "SELECT COUNT(*) FROM ticks").fetchone()[0]
        except Exception:
            return 0

    # ------------------------------------------------------------------
    # Housekeeping
    # ------------------------------------------------------------------

    def vacuum(self, keep_days: int = 90) -> None:
        """
        Delete ticks older than keep_days and VACUUM the database.
        Call monthly or when db_size_mb() > 500.
        """
        self._conn.execute(
            f"DELETE FROM ticks WHERE ts < datetime('now', '-{keep_days} days')")
        self._conn.execute(
            f"DELETE FROM alerts WHERE ts < datetime('now', '-{keep_days} days')")
        self._conn.execute("VACUUM")
        logger.info("VACUUM complete — kept last %d days", keep_days)

    def close(self) -> None:
        """Flush remaining buffer and close the connection."""
        self._flush()
        # Update session end time and totals
        summary = self.read_session_summary()
        self._conn.execute(
            "UPDATE sessions SET ended_at=?, total_ticks=?, "
            "total_h2_kg=?, total_revenue=? WHERE id=?",
            (self._now_str(),
             summary.get("tick_count", 0),
             summary.get("total_h2_kg", 0.0),
             summary.get("total_revenue", 0.0),
             self._session_id))
        self._conn.close()
        logger.info("Database closed: %s", self.path)

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    @staticmethod
    def _now_str() -> str:
        """ISO timestamp in Zagreb timezone."""
        return datetime.now(timezone(timedelta(hours=2))).isoformat(
            timespec="seconds")


# =============================================================================
# Smoke-test
# =============================================================================

if __name__ == "__main__":
    import tempfile, os

    print("=" * 55)
    print("  database.py v1.0 — Smoke test")
    print("=" * 55)

    # Use temp file so test doesn't pollute project folder
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()

    db = Database(path=tmp.name, batch_size=3)
    print(f"\n✅ Database created: {tmp.name}")

    # Simulate a minimal TickState-like object
    class FakeTick:
        def __init__(self, n):
            self.tick            = n
            self.solar_kw        = 8.5
            self.wind_kw         = 3.2
            self.total_gen_kw    = 11.7
            self.wx_irradiance   = 650.0
            self.wx_wind_ms      = 6.4
            self.wx_temp_c       = 22.0
            self.wx_soiling      = 0.97
            self.bess_soc_pct    = 65.0
            self.bess_soh_pct    = 100.0
            self.bess_temp_c     = 26.5
            self.bess_charge_kw  = 5.0
            self.elec_kw         = 3.0
            self.elec_eff_pct    = 78.0
            self.elec_soh_pct    = 100.0
            self.elec_purity     = 99.999
            self.h2_kg_h         = 0.0593
            self.buffer_pct      = 12.0
            self.main_tank_pct   = 45.0
            self.hrs_pct         = 60.0
            self.pressure_bar    = 220.0
            self.tank_temp_c     = 22.0
            self.compressor_on   = True
            self.fc_kw           = 0.0
            self.fc_eff_pct      = 0.0
            self.grid_export_kw  = 0.5
            self.grid_import_kw  = 0.0
            self.ev_kw           = 2.0
            self.lcoh            = 1.45
            self.cum_h2_kg       = n * 0.000165
            self.cum_revenue_eur = n * 0.0024
            self.cum_co2_kg      = n * 0.0015
            self.leak_detected   = False
            self.fc_h2_shortage  = False

    # Write 10 ticks — should trigger flush at tick 3, 6, 9
    for i in range(10):
        db.write_tick(FakeTick(i + 1))
    db._flush()  # flush remainder
    print(f"✅ Wrote 10 ticks — stored: {db.row_count()} rows")
    assert db.row_count() == 10

    # Read history
    df = db.read_history(days=1)
    print(f"✅ read_history(1 day): {len(df)} rows, {len(df.columns)} columns")
    assert len(df) == 10

    # Session summary
    s = db.read_session_summary()
    print(f"✅ Session summary: {s['tick_count']} ticks, "
          f"H₂ {s['total_h2_kg']:.4f} kg, "
          f"revenue €{s['total_revenue']:.4f}")
    assert s["tick_count"] == 10

    # Alert log
    db.write_alert("warning", "BESS_TEMP", "BESS temperature elevated (>55°C)")
    alerts = db.read_alert_log(days=1)
    print(f"✅ Alert log: {len(alerts)} entries")
    assert len(alerts) == 1

    # DB size
    print(f"✅ DB size: {db.db_size_mb()} MB")

    db.close()
    os.unlink(tmp.name)
    print(f"\n✅ database.py v1.0 — all tests passed")
