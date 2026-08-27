import logging
from typing import List
from src.backend.safe_api_calls import safe_api_call
from src.backend.json_repair_utilities import repair_json, normalize_step1
from src.backend.pydantic_schemas import Step1Response

def extract_themes(domain: str, 
                         raw_articles: List[dict],
                         system_prompt: str,
                         models: List[str],) -> dict:
    logging.info(f"Executing Step 1: Extracting Trending Themes from {domain}")

    articles_payload = []
    for a in raw_articles:
        clean_title = str(a.get("title", "")).replace("\n", " ").strip()[:300]
        articles_payload.append(f"- [{a['id']}] : {clean_title}")

    formatted_articles = "\n".join(articles_payload)
    user_content = f"Target Domain: {domain}\n\nArticles:\n{formatted_articles}"


    raw_json_str = safe_api_call(system_prompt, user_content, models, max_tokens=4096)
    logging.info(f"{raw_json_str}")
    repaired = repair_json(raw_json_str, fallback={"domain": domain, "top_5_trending_themes": []})
    normalized = normalize_step1(repaired)

    validated = Step1Response.model_validate(normalized)
    return validated.model_dump()
