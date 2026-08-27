import logging
import json_repair
from typing import List
TOP_N_THEMES = 10
TOP_N_OPPORTUNITY_SPACES = 20

def repair_json(raw_json_str: str, fallback: dict) -> dict:
    try:
        data = json_repair.loads(raw_json_str)
        if not isinstance(data, dict):
            return fallback
        return data
    except Exception as e:
        logging.error(f"JSON repair failed: {e}")
        return fallback

def repair_json_ted(raw_json_str: str, fallback: List[dict]) -> List[dict]:
    try:
        data = json_repair.loads(raw_json_str)
        if not isinstance(data, list):
            return fallback
    
        valid_dicts = [item for item in data if isinstance(item, dict)]
        return valid_dicts if valid_dicts else fallback
    
    except Exception as e:
        logging.error(f"JSON repair failed: {e}")
        return fallback

def normalize_step1(data: dict) -> dict:
    if "domain" not in data:
        data["domain"] = "unknown"

    techs = data.get("top_5_trending_themes") or data.get("themes") or []
    normalized = []

    for idx, tech in enumerate(techs, start=1):
        t = {}
        t["rank"] = tech.get("rank", idx)
        t["theme"] = (
            tech.get("theme")
            or tech.get("technology")
            or tech.get("name")
            or "Unknown Theme"
        )

        raw_ids = tech.get("source_article_ids") or tech.get("article_ids") or []
        if isinstance(raw_ids, (str, int, float)):
            raw_ids = [str(raw_ids)]
        elif isinstance(raw_ids, list):
            raw_ids = [str(x) for x in raw_ids]

        t["source_article_ids"] = raw_ids
        normalized.append(t)

    data["top_5_trending_themes"] = normalized[:TOP_N_THEMES]
    return data


def normalize_step2(data: dict) -> dict:
    if "opportunity_spaces" not in data or not isinstance(data["opportunity_spaces"], list):
        return {"opportunity_spaces": []}

    cleaned_list = []
    for opp in data["opportunity_spaces"]:
        if not isinstance(opp, dict):
            continue

        opp.setdefault("technology_name", "Unknown Technology")
        opp.setdefault("overview_definition", "No overview provided.")
        opp.setdefault("signals_and_sources", {})
        opp.setdefault("use_cases_and_value_drivers", [])
        opp.setdefault("target_audience", {"personas": [], "verticals": [], "geographies": []})
        opp.setdefault("scores", {})
        opp.setdefault("weighted_score", 0.0)
        opp.setdefault("priority_tier", "Unknown priority")
        opp.setdefault("scoring_rationale", "Unknown scoring rationale")

        cleaned_list.append(opp)

    if len(cleaned_list) > TOP_N_OPPORTUNITY_SPACES:
        logging.warning(
            f"Model returned {len(cleaned_list)} opportunity spaces; "
            f"truncating to top {TOP_N_OPPORTUNITY_SPACES}."
        )
        cleaned_list = cleaned_list[:TOP_N_OPPORTUNITY_SPACES]
    else:
        logging.info(f"Model returned {len(cleaned_list)} opportunity spaces.")

    return {"opportunity_spaces": cleaned_list}
