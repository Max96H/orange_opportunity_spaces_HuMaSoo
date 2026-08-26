import logging
import json
from typing import List
from src.backend.safe_api_calls import safe_api_call
from src.backend.json_repair_utilities import repair_json, normalize_step2

def generate_opportunity_space(domain: str, 
                               step1_result: dict, 
                               filtered_articles: List[dict],
                               system_prompt: str,
                               model: str,
                               client: str) -> dict:
    logging.info(f"Executing Step 2: Building Opportunity Space for {domain}...")

    articles_formatted = "\n".join(
        f"[{a['id']}] {a['url']} | {a['content'].strip()}..."
        for a in filtered_articles
    )

    lean_techs = [
        {"name": t.get("theme"), "ids": t.get("source_article_ids")}
        for t in step1_result.get("top_10_trending_themes", [])
    ]
    tech_json = json.dumps(lean_techs, separators=(',', ':'))

    user_content = (
        f"Domain: {domain}\n"
        f"Themes: {tech_json}\n"
        f"Articles:\n{articles_formatted}"
    )

    raw_json_str = safe_api_call(system_prompt, user_content, client, model, max_tokens=16384)
    repaired = repair_json(raw_json_str, fallback={"opportunity_space": []})
    normalized = normalize_step2(repaired)

    return normalized
