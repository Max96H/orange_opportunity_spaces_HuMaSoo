import logging
from typing import List, Tuple
from rapidfuzz import fuzz, process


def resolve_and_filter_articles(
    step1_output: dict, raw_articles: List[dict], fuzzy_threshold: float = 70.0
) -> Tuple[dict, List[dict]]:

    valid_id_map = {str(article["id"]): article for article in raw_articles}
    valid_ids_set = set(valid_id_map.keys())

    title_to_id_map = {article["title"]: article["id"] for article in raw_articles}
    all_titles = list(title_to_id_map.keys())

    collected_valid_ids = set()

    for tech in step1_output.get("top_5_trending_themes", []):
        tech_name = tech.get("theme", "")
        raw_ids = tech.get("source_article_ids", [])

        valid_ids = list(set(raw_ids).intersection(valid_ids_set))

        hallucinated_ids = set(raw_ids) - valid_ids_set
        if hallucinated_ids:
            logging.warning(f"LLM hallucinated IDs for '{tech_name}': {hallucinated_ids}")

        if not valid_ids and all_titles:
            match_result = process.extractOne(tech_name, all_titles, scorer=fuzz.WRatio)
            if match_result and match_result[1] >= fuzzy_threshold:
                matched_title, score, _ = match_result
                valid_ids.append(title_to_id_map[matched_title])
            else:
                logging.warning(f"No fuzzy match found for '{tech_name}'")

        tech["source_article_ids"] = valid_ids
        collected_valid_ids.update(valid_ids)

    filtered_articles = [valid_id_map[aid] for aid in collected_valid_ids if aid in valid_id_map]

    if not filtered_articles:
        filtered_articles = raw_articles[:10]

    return step1_output, filtered_articles
