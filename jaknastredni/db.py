"""Připojení k SQLite databázi a založení schématu."""
from __future__ import annotations

import sqlite3
from importlib import resources
from pathlib import Path


def connect(path: str | Path = ":memory:") -> sqlite3.Connection:
    """Otevře databázi, zapne cizí klíče a zajistí, že schéma existuje."""
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    schema = resources.files(__package__).joinpath("schema.sql").read_text(encoding="utf-8")
    conn.executescript(schema)
    return conn
