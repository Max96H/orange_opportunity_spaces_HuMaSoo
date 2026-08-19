import json
import time
import logging
import os
from typing import List
from dotenv import load_dotenv
from groq import Groq
from pydantic import BaseModel, Field, field_validator
from rapidfuzz import fuzz, process
import sqlite3

# Setup Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY environment variable is not set.")

client = Groq(api_key=GROQ_API_KEY)
MODEL_ID = "openai/gpt-oss-120b"


# ==========================================
# 1. PYDANTIC SCHEMAS
# ==========================================

class TechnologyExtract(BaseModel):
    rank: int
    technology_name: str
    rationale: str
    source_article_ids: List[str] = Field(default_factory=list)

    @field_validator("source_article_ids", mode="before")
    @classmethod
    def ensure_list(cls, v):
        if isinstance(v, str):
            return [v]
        if v is None:
            return []
        return v


class Step1Response(BaseModel):
    domain: str
    top_5_emerging_technologies: List[TechnologyExtract]


# ==========================================
# 2. STEP 1: EXTRACT TECHNOLOGIES
# ==========================================

STEP1_SYSTEM_PROMPT = """You are an expert technology foresight analyst specializing in domain innovation mapping.
Your task is to analyze a list of articles (provided as JSON with ID and Title) and identify the top 5 hot, emerging technologies.

If you output any key other than "domain" or "top_5_emerging_technologies", your answer is invalid. 
You MUST follow the exact schema. No alternative keys are allowed.

Rules:
1. Focus strictly on specific, actionable technologies.
2. Ensure all 5 technologies belong strictly to the target domain.
3. Base your selection on frequency, market buzz, and novelty.
4. Include exact article IDs supporting each technology.
5. Output ONLY valid JSON following the schema.
"""
def force_step1_schema(raw_json_str: str) -> dict:
    data = json.loads(raw_json_str)

    # If the model used wrong keys, fix them
    if "technologies" in data:
        data["top_5_emerging_technologies"] = data.pop("technologies")

    if "article_ids" in data:
        for tech in data["top_5_emerging_technologies"]:
            tech["source_article_ids"] = tech.get("article_ids", [])
            tech.pop("article_ids", None)

    # If domain missing, add it manually
    if "domain" not in data:
        data["domain"] = "unknown"

    return data

def extract_technologies(domain: str, raw_articles: list[dict]) -> dict:
    logging.info(f"Executing Step 1: Extracting Top Technologies from {domain}")

    articles_payload = [{"id": a["id"], "title": a["title"]} for a in raw_articles]

    user_content = f"Target Domain: {domain}\n\nArticles:\n{json.dumps(articles_payload, indent=2)}"

    response = client.chat.completions.create(
        model=MODEL_ID,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": STEP1_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )

    raw_json_str = response.choices[0].message.content
    safe_json = force_step1_schema(raw_json_str)
    validated_model = Step1Response.model_validate(safe_json)
    return validated_model.model_dump()


# ==========================================
# 3. DEFENSIVE ID RESOLUTION
# ==========================================

def resolve_and_filter_articles(step1_output: dict, raw_articles: list[dict], fuzzy_threshold: float = 70.0):
    valid_id_map = {article["id"]: article for article in raw_articles}
    valid_ids_set = set(valid_id_map.keys())

    title_to_id_map = {article["title"]: article["id"] for article in raw_articles}
    all_titles = list(title_to_id_map.keys())

    collected_valid_ids = set()

    for tech in step1_output.get("top_5_emerging_technologies", []):
        tech_name = tech.get("technology_name", "")
        raw_ids = tech.get("source_article_ids", [])

        valid_ids = list(set(raw_ids).intersection(valid_ids_set))

        hallucinated_ids = set(raw_ids) - valid_ids_set
        if hallucinated_ids:
            logging.warning(f"LLM hallucinated IDs for '{tech_name}': {hallucinated_ids}")

        if not valid_ids:
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
        filtered_articles = raw_articles

    return step1_output, filtered_articles


# ==========================================
# 4. STEP 2: GENERATE OPPORTUNITY SPACE
# ==========================================

STEP2_SYSTEM_PROMPT = """You are a senior strategic analyst creating an Opportunity Space.
Analyze the provided article contents and URLs to evaluate the target technologies.

Rules:
1. Only extract signals explicitly present in the article content.
2. Preserve exact URLs.
3. Provide objective scoring.
4. Output ONLY valid JSON following the schema.
"""

def generate_opportunity_space(domain: str, step1_result: dict, filtered_articles: list[dict]) -> dict:
    logging.info("Executing Step 2: Building Opportunity Space...")

    articles_formatted = ""
    for article in filtered_articles:
        articles_formatted += f"---\nID: {article['id']}\nURL: {article['url']}\nContent: {article['content']}\n\n"

    user_content = (
        f"Target Domain: {domain}\n\n"
        f"Technologies:\n{json.dumps(step1_result, indent=2)}\n\n"
        f"Articles:\n{articles_formatted}"
    )

    response = client.chat.completions.create(
        model=MODEL_ID,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": STEP2_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )

    return json.loads(response.choices[0].message.content)


# ==========================================
# 5. INSERT INTO OPPORTUNITY SPACE TABLES
# ==========================================

def insert_opportunity_space(cursor, opp):
    cursor.execute("""
        INSERT INTO opportunity_space (technology_name, overview_definition)
        VALUES (?, ?)
    """, (opp["technology_name"], opp["overview_definition"]))
    return cursor.lastrowid


def insert_signals(cursor, opportunity_id, signals):
    for category, items in signals.items():
        for item in items:
            cursor.execute("""
                INSERT INTO opportunity_signals (opportunity_id, article_id, signal_type, insight)
                VALUES (?, ?, ?, ?)
            """, (
                opportunity_id,
                item["url"],  # temporarily store URL until article_id mapping is added
                category,
                item["insight"]
            ))


def insert_use_cases(cursor, opportunity_id, use_cases):
    for uc in use_cases:
        cursor.execute("""
            INSERT INTO use_cases (opportunity_id, use_case, value_driver)
            VALUES (?, ?, ?)
        """, (opportunity_id, uc["use_case"], uc["value_driver"]))


def insert_target_audience(cursor, opportunity_id, audience):
    for persona in audience["personas"]:
        cursor.execute("""
            INSERT INTO target_audience (opportunity_id, persona, vertical, geography)
            VALUES (?, ?, ?, ?)
        """, (opportunity_id, persona, None, None))

    for vertical in audience["verticals"]:
        cursor.execute("""
            INSERT INTO target_audience (opportunity_id, persona, vertical, geography)
            VALUES (?, ?, ?, ?)
        """, (opportunity_id, None, vertical, None))

    for geo in audience["geographies"]:
        cursor.execute("""
            INSERT INTO target_audience (opportunity_id, persona, vertical, geography)
            VALUES (?, ?, ?, ?)
        """, (opportunity_id, None, None, geo))


def insert_scoring(cursor, opportunity_id, scoring):
    cursor.execute("""
        INSERT INTO scoring (
            opportunity_id,
            attractiveness_score,
            attractiveness_rationale,
            urgency_score,
            urgency_rationale
        ) VALUES (?, ?, ?, ?, ?)
    """, (
        opportunity_id,
        scoring["attractiveness_score"],
        scoring["attractiveness_rationale"],
        scoring["urgency_score"],
        scoring["urgency_rationale"]
    ))


# ==========================================
# 6. MAIN PIPELINE
# ==========================================

if __name__ == "__main__":

    from config import DOMAIN_KEYWORD_MAP

    for DOMAIN in DOMAIN_KEYWORD_MAP.keys():

        conn = sqlite3.connect("./data/signals.db")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT a.id, a.title, a.url, b.body
            FROM articles a
            JOIN article_bodies b ON a.id = b.article_id
            WHERE a.domain = ?
        """, (DOMAIN,))

        rows = cursor.fetchall()

        RAW_ARTICLES = [
            {"id": row[0], "title": row[1], "url": row[2], "content": row[3]}
            for row in rows
        ]

        conn.close()

        try:
            step1_raw = extract_technologies(DOMAIN, RAW_ARTICLES)
            step1_sanitized, filtered_articles = resolve_and_filter_articles(step1_raw, RAW_ARTICLES)
            step2_final = generate_opportunity_space(DOMAIN, step1_sanitized, filtered_articles)

            # Insert into DB
            conn = sqlite3.connect("./data/signals.db")
            cursor = conn.cursor()

            for opp in step2_final["opportunity_space"]:
                opp_id = insert_opportunity_space(cursor, opp)
                insert_signals(cursor, opp_id, opp["signals_and_sources"])
                insert_use_cases(cursor, opp_id, opp["use_cases_and_value_drivers"])
                insert_target_audience(cursor, opp_id, opp["target_audience"])
                insert_scoring(cursor, opp_id, opp["scoring"])

            conn.commit()
            conn.close()

        except Exception as e:
            logging.error(f"Pipeline execution error: {e}", exc_info=True)

        time.sleep(10)
