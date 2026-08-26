"""
Inject scanner output into the article database.
"""

import sqlite3
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from backend.scanner_ted import scan_ted_notices


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "sus_cyb_fullBody_signals.db"


def create_tables(cursor):
    cursor.execute("PRAGMA foreign_keys = ON;")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT,
            title TEXT,
            date TEXT,
            url TEXT,
            source_domain TEXT,
            signal_type_guess TEXT
        );
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS article_bodies (
            article_id INTEGER PRIMARY KEY,
            body TEXT,
            FOREIGN KEY(article_id) REFERENCES articles(id) ON DELETE CASCADE
        );
        """
    )


def insert_article(cursor, signal):
    cursor.execute(
        """
        INSERT INTO articles (
            domain, title, date, url, source_domain, signal_type_guess
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            signal.get("domain"),
            signal.get("title"),
            signal.get("date"),
            signal.get("url"),
            signal.get("source_domain"),
            signal.get("signal_type_guess"),
        ),
    )
    return cursor.lastrowid


def insert_body(cursor, article_id, signal):
    cursor.execute(
        """
        INSERT INTO article_bodies (
            article_id, body
        ) VALUES (?, ?)
        """,
        (
            article_id,
            signal.get("body"),
        ),
    )


def main():
    scan_result = scan_ted_notices()
    signals = scan_result.get("signals", [])
    errors = scan_result.get("errors", [])

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    create_tables(cursor)

    for signal in signals:
        article_id = insert_article(cursor, signal)
        insert_body(cursor, article_id, signal)

    conn.commit()
    conn.close()

    print(f"Inserted {len(signals)} signals into database: {DB_PATH}")
    if errors:
        print(f"Scanner errors: {errors}")


if __name__ == "__main__":
    main()
