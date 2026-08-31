"""
Innovation Radar - Database Schema Creator
==========================================
Creates all normalized tables required for:
- Raw signals (articles, bodies, verticals)
- Opportunity Space (technologies, signals, use cases, audience, scoring)

Run this once to initialize the SQLite database.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("./data/opportunity_spaces.db")


def create_tables():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT,
            title TEXT,
            date TEXT,
            url TEXT,
            source_domain TEXT,
            signal_type_guess TEXT
        );
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS article_bodies (
            article_id INTEGER,
            body TEXT,
            FOREIGN KEY(article_id) REFERENCES articles(id) ON DELETE CASCADE
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS article_verticals (
            article_id INTEGER,
            vertical TEXT,
            FOREIGN KEY(article_id) REFERENCES articles(id) ON DELETE CASCADE
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS opportunity_space (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT,
            technology_name TEXT NOT NULL,
            overview_definition TEXT
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS opportunity_signals (
            opportunity_id INTEGER NOT NULL,
            article_id INTEGER NOT NULL,
            signal_type TEXT CHECK(signal_type IN (
                'regulation', 'buying_signals', 'market_trends'
            )),
            insight TEXT,
            FOREIGN KEY(opportunity_id) REFERENCES opportunity_space(id) ON DELETE CASCADE,
            FOREIGN KEY(article_id) REFERENCES articles(id) ON DELETE CASCADE
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS use_cases (
            opportunity_id INTEGER NOT NULL,
            use_case TEXT,
            value_driver TEXT,
            FOREIGN KEY(opportunity_id) REFERENCES opportunity_space(id) ON DELETE CASCADE
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS opp_personas (
            opportunity_id INTEGER,
            persona TEXT,
            FOREIGN KEY(opportunity_id) REFERENCES opportunity_space(id) ON DELETE CASCADE
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS opp_verticals (
            opportunity_id INTEGER,
            vertical TEXT,
            FOREIGN KEY(opportunity_id) REFERENCES opportunity_space(id) ON DELETE CASCADE
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS opp_geographies (
            opportunity_id INTEGER,
            geography TEXT,
            FOREIGN KEY(opportunity_id) REFERENCES opportunity_space(id) ON DELETE CASCADE
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            opportunity_id INTEGER,
            final_score REAL,
            market_signal_strength REAL,
            source_diversity REAL,
            weighted_score REAL,
            market_urgency REAL,
            business_value_impact REAL,
            technology_readiness REAL,
            ease_of_implementation REAL,
            cross_vertical_scalability REAL,
            competitive_differentiation REAL,
            scoring_rationale TEXT,
            priority_tier TEXT,
            FOREIGN KEY(opportunity_id) REFERENCES opportunity_space(id) ON DELETE CASCADE
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS partners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT,
            partner TEXT,
            UNIQUE(domain, partner)
        );
    """)

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_state (
                domain TEXT PRIMARY KEY,
                status TEXT,
                updated_at TEXT
            );
        """)
    
    conn.commit()
    conn.close()

    print(f"Database initialized successfully at: {DB_PATH}")


if __name__ == "__main__":
    create_tables()
