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
            WHERE a.domain = ?;
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
                    if persona:
                        cursor.execute("""
                            INSERT INTO opp_personas (opportunity_id, persona)
                            VALUES (?, ?);
                        """, (opp_id, persona))
                for vertical in audience.get("verticals", []):
                    cursor.execute("""
                        INSERT INTO opp_verticals (opportunity_id, vertical)
                        VALUES (?, ?);
                    """, (opp_id, vertical))
                for geo in audience.get("geographies", []):
                    cursor.execute("""
                        INSERT INTO opp_geographies (opportunity_id, geography)
                        VALUES (?, ?);
                    """, (opp_id, geo))

            score_components = opp.get("scores", {})
            if isinstance(score_components, dict):
                print("Inserting score , scores_components: ", score_components)
                cursor.execute("""
                    INSERT INTO scores (
                        opportunity_id, 
                        final_score,
                        market_signal_strength,
                        source_diversity,
                        weighted_score,
                        market_urgency,
                        business_value_impact,
                        technology_readiness,
                        ease_of_implementation,
                        cross_vertical_scalability,
                        competitive_differentiation,
                        scoring_rationale,
                        priority_tier
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (opp_id, 
                      opp.get("final_score", 0.0), 
                      opp.get("market_signal_strength", 0.0), 
                      opp.get("source_diversity", 0.0), 
                      opp.get("weighted_score", 0.0),
                      score_components.get("market_urgency", 0.0),
                      score_components.get("business_value_impact", 0.0),
                      score_components.get("technology_readiness", 0.0),
                      score_components.get("ease_of_implementation", 0.0),
                      score_components.get("cross_vertical_scalability", 0.0),
                      score_components.get("competitive_differentiation", 0.0),
                      opp.get("scoring_rationale", "Unknown"),
                      opp.get("priority_tier", "Unknown")))


        conn.commit()
