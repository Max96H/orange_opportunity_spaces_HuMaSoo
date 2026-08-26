import sqlite3
from typing import Optional, List
from datetime import datetime, timezone

SIGNAL_TYPE_MAP = {
    "market_drivers": "market_trends",
    "market_trends": "market_trends",
    "buying_signals": "buying_signals",
    "buying_signal": "buying_signals",
    "regulation": "regulation",
    "regulations": "regulation",
    "regulatory": "regulation"
}

def init_db(db_path: str):
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS opportunity_space (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT,
                technology_name TEXT,
                overview_definition TEXT
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_state (
                domain TEXT PRIMARY KEY,
                status TEXT,
                updated_at TEXT
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS opportunity_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                opportunity_id INTEGER,
                article_id TEXT,
                signal_type TEXT,
                insight TEXT
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS use_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                opportunity_id INTEGER,
                use_case TEXT,
                value_driver TEXT
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS target_audience (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                opportunity_id INTEGER,
                persona TEXT,
                vertical TEXT,
                geography TEXT
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scoring (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                opportunity_id INTEGER,
                attractiveness_score REAL,
                attractiveness_rationale TEXT,
                urgency_score REAL,
                urgency_rationale TEXT
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS new_scoring (
                opportunity_id INTEGER,
                final_score REAL,
                market_signal_strength REAL,
                source_diversity REAL,
                evidence_quality REAL,
                FOREIGN KEY(opportunity_id) REFERENCES opportunity_space(id) ON DELETE CASCADE
            );
        """)

        # Migration for DBs created before `domain` existed on this table.
        cursor.execute("PRAGMA table_info(opportunity_space)")
        existing_cols = {row[1] for row in cursor.fetchall()}
        if "domain" not in existing_cols:
            cursor.execute("ALTER TABLE opportunity_space ADD COLUMN domain TEXT;")

        conn.commit()


def get_domain_status(db_path: str, domain: str) -> Optional[str]:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM pipeline_state WHERE domain = ?;", (domain,))
        row = cursor.fetchone()
        return row[0] if row else None


def set_domain_status(db_path: str, domain: str, status: str):
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO pipeline_state (domain, status, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(domain) DO UPDATE SET status = excluded.status, updated_at = excluded.updated_at;
        """, (domain, status, datetime.now(timezone.utc).isoformat()))
        conn.commit()


def fetch_raw_articles(db_path: str, domain: str) -> List[dict]:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.id, a.title, a.url, b.body
            FROM articles a
            JOIN article_bodies b ON a.id = b.article_id
            WHERE a.domain = ?
            LIMIT 40;
        """, (domain,))
        rows = cursor.fetchall()

    return [
        {"id": str(row[0]), "title": row[1], "url": row[2], "content": row[3]}
        for row in rows
    ]


def save_opportunity_data(db_path: str, domain: str, opportunity_space_list: List[dict]):
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        for opp in opportunity_space_list:
            if not isinstance(opp, dict):
                continue

            cursor.execute("""
                INSERT INTO opportunity_space (domain, technology_name, overview_definition)
                VALUES (?, ?, ?);
            """, (domain, opp.get("technology_name"), opp.get("overview_definition")))
            opp_id = cursor.lastrowid

            signals = opp.get("signals_and_sources", {})
            if isinstance(signals, dict):
                for raw_category, items in signals.items():
                    normalized_signal_type = SIGNAL_TYPE_MAP.get(raw_category.lower(), "market_trends")
                    if isinstance(items, list):
                        for item in items:
                            if isinstance(item, dict):
                                cursor.execute("""
                                    INSERT INTO opportunity_signals (opportunity_id, article_id, signal_type, insight)
                                    VALUES (?, ?, ?, ?);
                                """, (
                                    opp_id,
                                    item.get("url"),
                                    normalized_signal_type,
                                    item.get("insight")
                                ))

            for uc in opp.get("use_cases_and_value_drivers", []):
                if isinstance(uc, dict):
                    cursor.execute("""
                        INSERT INTO use_cases (opportunity_id, use_case, value_driver)
                        VALUES (?, ?, ?);
                    """, (opp_id, uc.get("use_case"), uc.get("value_driver")))

            audience = opp.get("target_audience", {})
            if isinstance(audience, dict):
                for persona in audience.get("personas", []):
                    cursor.execute("""
                        INSERT INTO target_audience (opportunity_id, persona, vertical, geography)
                        VALUES (?, ?, ?, ?);
                    """, (opp_id, persona, None, None))
                for vertical in audience.get("verticals", []):
                    cursor.execute("""
                        INSERT INTO target_audience (opportunity_id, persona, vertical, geography)
                        VALUES (?, ?, ?, ?);
                    """, (opp_id, None, vertical, None))
                for geo in audience.get("geographies", []):
                    cursor.execute("""
                        INSERT INTO target_audience (opportunity_id, persona, vertical, geography)
                        VALUES (?, ?, ?, ?);
                    """, (opp_id, None, None, geo))

            fs = opp.get("final_score", {})
            score_components = opp.get("score_components")
            if isinstance(fs, float) and isinstance(score_components, dict):
                cursor.execute("""
                    INSERT INTO new_scoring (
                        opportunity_id, final_score, market_signal_strength, source_diversity, evidence_quality)
                        VALUES (?, ?, ?, ?, ?);
                """, (opp_id, 
                      opp.get("final_score", 0.0), 
                      score_components.get("market_signal_strength", 0.0), 
                      score_components.get("source_diversity", 0.0), 
                      score_components.get("evidence_quality", 0.0)))


        conn.commit()
