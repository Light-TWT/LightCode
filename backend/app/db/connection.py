"""SQLite connection factory for Phase 1 (WP2 / P0-3).

``open_connection()`` returns a *fresh* connection to the same database file,
configured identically (WAL, busy_timeout, row factory, foreign keys). The
cross-process write mutex for Phase 1 is the atomic, file-scoped conditional
``UPDATE`` in ``app.services.phase1.Phase1Service.submit_approval`` (serialised
by SQLite's file-level write lock under WAL). This factory is used by tests
that must open independent connections to prove that mutex is cross-process,
and is available for future per-request connection isolation. No new table and
no schema change.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


def open_connection(database_path: Path) -> sqlite3.Connection:
    """Open a fresh, correctly configured connection to the Phase 1 database.

    Callers performing the exclusive write section issue an explicit
    ``BEGIN IMMEDIATE`` so the cross-process mutex is unambiguous and
    serializable under WAL. The settings mirror ``initialize_database`` exactly
    so every connection behaves identically.
    """
    connection = sqlite3.connect(str(database_path), check_same_thread=False)
    connection.row_factory = sqlite3.Row
    # WAL enables one serialized writer + concurrent readers; busy_timeout lets a
    # contending writer wait instead of raising SQLITE_BUSY, which is what makes
    # the at-most-one claim deterministic across processes.
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=5000")
    connection.execute("PRAGMA foreign_keys=ON")
    return connection
