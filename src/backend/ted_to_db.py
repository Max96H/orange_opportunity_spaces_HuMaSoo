"""
Inject scanner output into the article database.
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[2]))
import sqlite3
from src.backend.safe_api_calls import safe_api_call
from src.backend.scanner_ted import scan_ted_notices
from src.prompts import TED_PROMPT
from src.config import MODELS_STEP1
from src.backend.json_repair_utilities import repair_json_ted
from pydantic import BaseModel
from google.genai import types

# 1. Define the exact structure expected
class ArticleClassification(BaseModel):
    id: str
    domain: str

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "opportunity_spaces.db"


def insert_article(cursor, signal):
    cursor.execute(
        """
        INSERT INTO articles (
            domain, title, date, url, source_domain, signal_type_guess
        ) VALUES (?, ?, ?, ?, ?, ?);
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
        ) VALUES (?, ?);
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

    try:
        for signal in signals:
            article_id = insert_article(cursor, signal)
            insert_body(cursor, article_id, signal)
        conn.commit()

        cursor.execute("""
            SELECT a.id, a.title
            FROM articles AS a
            WHERE a.source_domain LIKE '%ted.europa.eu%'
            AND a.domain IS NULL;
        """)
        rows = cursor.fetchall()

        if not rows:
            print("No unclassified TED articles found.")
            return
        
        rows_dict = [
            {"id": str(row[0]), "title": row[1]}
            for row in rows
        ]
        articles_payload = []

        for a in rows_dict:
            clean_title = str(a.get("title", "")).replace("\n", " ").strip()[:300]
            articles_payload.append(f"- [{a['id']}] : {clean_title}")

        formatted_articles = "\n".join(articles_payload)
        json_format = list[ArticleClassification]
        res = safe_api_call(TED_PROMPT, formatted_articles, MODELS_STEP1, json_format=json_format)

        repaired = repair_json_ted(res, fallback=[{}])

        for row in repaired:
            id = row.get("id", None)
            if not id: continue

            domain = row.get("domain", "-1")
            cursor.execute("""
                UPDATE articles
                SET domain = ?
                WHERE id = ?; 
                """, (domain, id))
            
        conn.commit()

        print(f"Inserted {len(signals)} signals into database: {DB_PATH}")
        if errors:
            print(f"Scanner errors: {errors}")

    except Exception as e:
        conn.rollback()
        print(f"Error during execution: {e}")
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()
