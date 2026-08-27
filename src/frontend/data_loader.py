import base64
import json
import sqlite3
from pathlib import Path

import streamlit as st


DB_DOMAIN_LABELS = {
    "smart_industries": "Smart Industries",
    "connectivity": "Connectivity Solutions",
    "cybersecurity": "Cybersecurity",
    "cloud": "Cloud",
    "cx": "Customer Experience",
    "ex": "Employee Experience",
    "sustainability": "Sustainability",
}


@st.cache_data
# Main entry point. It connets to db, builds opportunity spaces, and closes connection to db.
def load_opportunity_spaces(path: Path) -> list[dict]:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row

    try:
        spaces = connection.execute(
            """
            SELECT id,
                   domain,
                   technology_name,
                   overview_definition
            FROM opportunity_space
            WHERE id >= 49
            ORDER BY id
            """
        ).fetchall()

        return [
            build_opportunity_space(connection, space)
            for space in spaces
        ]
    finally:
        connection.close()


# Builds the opportunity space object from different tables of db.
def build_opportunity_space(
    connection: sqlite3.Connection,
    space: sqlite3.Row,
) -> dict:
    opportunity_id = space["id"]
    domain = space["domain"]
    scoring = fetch_scoring(connection, opportunity_id)

    return {
        "id": f"OS{opportunity_id:03}",
        "domain": DB_DOMAIN_LABELS.get(space["domain"], space["domain"] or "Unassigned"),
        "technology_name": space["technology_name"],
        "overview_definition": space["overview_definition"],
        "signals_and_sources": fetch_signals(connection, opportunity_id, domain),
        "use_cases_and_value_drivers": fetch_use_cases(connection, opportunity_id),
        "target_audience": fetch_target_audience(connection, opportunity_id),
        "scoring": {
            "final_score": scoring["final_score"] if scoring else None,
            "market_signal_strength": scoring["market_signal_strength"] if scoring else None,
            "source_diversity": scoring["source_diversity"] if scoring else None,
            "weighted_score": scoring["weighted_score"] if scoring else None,
            "market_urgency": scoring["market_urgency"] if scoring else None,
            "business_value_impact": scoring["business_value_impact"] if scoring else None,
            "technology_readiness": scoring["technology_readiness"] if scoring else None,
            "ease_of_implementation": scoring["ease_of_implementation"] if scoring else None,
            "cross_vertical_scalability": scoring["cross_vertical_scalability"] if scoring else None,
            "competitive_differentiation": scoring["competitive_differentiation"] if scoring else None,
            "scoring_rationale": scoring["scoring_rationale"] if scoring else "",
            "priority_tier": scoring["priority_tier"] if scoring else "",
        },
    }


# Fetches the current scoring model from scores table.
def fetch_scoring(
    connection: sqlite3.Connection,
    opportunity_id: int,
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT final_score,
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
        FROM scores
        WHERE opportunity_id = ?
        LIMIT 1
        """,
        (opportunity_id,),
    ).fetchone()


# Fetches signals by category + add url and summary if available. Sources from tables opportunity_signals (os) and articles.
def fetch_signals(
    connection: sqlite3.Connection,
    opportunity_id: int,
    domain: str
) -> dict[str, list[dict]]:
    signals_by_type = {
        "regulation": [],
        "buying_signals": [],
        "market_trends": [],
    }

    signal_rows = connection.execute(
        """
        SELECT os.signal_type,
               os.insight,
               os.article_id,
               articles.title,
               articles.url
        FROM opportunity_signals os
        LEFT JOIN articles ON CAST(articles.id AS TEXT) = os.article_id
        WHERE os.opportunity_id = ? AND articles.domain = ?
        ORDER BY os.rowid
        """,
        (opportunity_id, domain),
    ).fetchall()

    for signal in signal_rows:
        signal_type = signal["signal_type"]
        if signal_type not in signals_by_type:
            continue

        url = signal["url"] or signal["article_id"]
        signals_by_type[signal_type].append(
            {
                "title": signal["title"] or url,
                "insight": signal["insight"] or "",
                "url": url,
            }
        )

    return signals_by_type


# Fetches use cases from table use_cases
def fetch_use_cases(
    connection: sqlite3.Connection,
    opportunity_id: int,
) -> list[dict]:
    rows = connection.execute(
        """
        SELECT use_case,
               value_driver
        FROM use_cases
        WHERE opportunity_id = ?
        ORDER BY rowid
        """,
        (opportunity_id,),
    ).fetchall()

    return [
        {
            "use_case": row["use_case"],
            "value_driver": row["value_driver"],
        }
        for row in rows
    ]


# Fetches target information from the current audience tables.
def fetch_target_audience(
    connection: sqlite3.Connection,
    opportunity_id: int,
) -> dict[str, list[str]]:
    personas = connection.execute(
        """
        SELECT persona
        FROM opp_personas
        WHERE opportunity_id = ?
        """,
        (opportunity_id,),
    ).fetchall()

    verticals = connection.execute(
        """
        SELECT vertical
        FROM opp_verticals
        WHERE opportunity_id = ?
        """,
        (opportunity_id,),
    ).fetchall()

    geographies = connection.execute(
        """
        SELECT geography
        FROM opp_geographies
        WHERE opportunity_id = ?
        """,
        (opportunity_id,),
    ).fetchall()

    return {
        "personas": unique_non_empty_values(row["persona"] for row in personas),
        "verticals": unique_non_empty_values(row["vertical"] for row in verticals),
        "geographies": unique_non_empty_values(row["geography"] for row in geographies),
    }


# Utility function to remove empty values from lists. Especially useful for audience tables.
def unique_non_empty_values(values) -> list[str]:
    unique_values = []

    for value in values:
        if value and value not in unique_values:
            unique_values.append(value)

    return unique_values


def load_css(path: Path) -> None:
    with path.open("r", encoding="utf-8") as file:
        st.markdown(f"<style>{file.read()}</style>", unsafe_allow_html=True)


@st.cache_data
def image_to_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")
