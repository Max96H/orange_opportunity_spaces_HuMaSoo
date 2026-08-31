from src.prompts import STEP1_SYSTEM_PROMPT, STEP2_SYSTEM_PROMPT
from src.backend.first_extraction import extract_themes
from src.backend.first_extraction_safety import resolve_and_filter_articles
from src.backend.opportunity_spaces import generate_opportunity_space
from src.backend.scores import generate_scoring
from src.backend.db_operations import get_domain_status, set_domain_status, fetch_raw_articles, save_opportunity_data
import logging
import os
from dotenv import load_dotenv
from google import genai
from codecarbon import EmissionsTracker
import time
import sys
import argparse
from src.config import DOMAIN_KEYWORD_MAP
from ecologits import EcoLogits

# ==========================================
# 0. CONFIGURATION & INITIALIZATION
# ==========================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("pipeline.log", encoding="utf-8"),
    ],
)

load_dotenv()
EcoLogits.init(providers=["google_genai"])

from src.config import MODELS_STEP1, MODELS_STEP2

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR, "data", "opportunity_spaces.db")

NON_RETRYABLE_STATUS_CODES = {400, 401, 402, 403, 404, 413, 422}
FATAL_PIPELINE_STATUS_CODES = {400, 401, 402, 403}

class FatalPipelineError(RuntimeError):
    """Raised when an error means the whole run should stop, not just the
    current domain (e.g. exhausted HF credits, invalid model, bad auth)."""


# ==========================================
# 1. MAIN PIPELINE
# ==========================================


def parse_args():
    parser = argparse.ArgumentParser(description="Run the opportunity-space generation pipeline.")
    parser.add_argument(
        "--domains",
        type=str,
        default=None,
        help="Comma-separated subset of domains to run (default: all domains in DOMAIN_KEYWORD_MAP).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess domains even if they already succeeded in a previous run.",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=DB_PATH,
        help=f"Path to the SQLite database (default: {DB_PATH}).",
    )
    return parser.parse_args()

def main():
    args = parse_args()
    db_path = args.db_path


    domains_to_run = list(DOMAIN_KEYWORD_MAP.keys())
    if args.domains:
        requested = {d.strip() for d in args.domains.split(",") if d.strip()}
        unknown = requested - set(domains_to_run)
        if unknown:
            logging.warning(f"Ignoring unknown domain(s) not in DOMAIN_KEYWORD_MAP: {unknown}")
        domains_to_run = [d for d in domains_to_run if d in requested]

    for domain in domains_to_run:
        if not args.force and get_domain_status(db_path, domain) == "success":
            logging.info(f"Skipping domain '{domain}' — already completed in a previous run (use --force to redo).")
            continue

        logging.info(f"--- Starting Processing for Domain: {domain} ---")

        raw_articles = fetch_raw_articles(db_path, domain)
        if not raw_articles:
            logging.warning(f"No articles found for domain '{domain}'. Skipping...")
            continue

        try:
            step1_raw = extract_themes(domain, raw_articles, STEP1_SYSTEM_PROMPT, MODELS_STEP1)

            if not step1_raw.get("top_5_trending_themes"):
                logging.warning(f"No themes extracted for domain '{domain}'. Skipping Step 2.")
                set_domain_status(db_path, domain, "failed")
                continue

            step1_sanitized, filtered_articles = resolve_and_filter_articles(step1_raw, raw_articles)

            logging.info("Extracted themes for {domain}, pausing 60 seconds...")
            time.sleep(60)

            step2_final = generate_opportunity_space(domain, step1_sanitized, filtered_articles, STEP2_SYSTEM_PROMPT, MODELS_STEP2)

            opportunity_spaces = step2_final.get("opportunity_spaces", [])
            step3_scored_spaces = generate_scoring(opportunity_spaces)

            if step3_scored_spaces:
                save_opportunity_data(db_path, domain, step3_scored_spaces)
                logging.info(f"Successfully saved Opportunity Space for domain: {domain}")
                set_domain_status(db_path, domain, "success")
            else:
                logging.warning(f"Step 2 produced no opportunity spaces for domain '{domain}'.")
                set_domain_status(db_path, domain, "failed")

            logging.info(f"Generation done for {domain}, pausing 60 seconds...")
            time.sleep(60)

        except FatalPipelineError as e:
            set_domain_status(db_path, domain, "failed")
            logging.error(f"Fatal pipeline error on domain '{domain}': {e}")
            logging.error("Stopping the run — this error will not resolve by moving to the next domain. "
                           "Fix the underlying issue (credits, auth, or model config) and rerun; "
                           "already-completed domains will be skipped automatically.")
            sys.exit(1)

        except Exception as e:
            logging.error(f"Pipeline execution error for domain {domain}: {e}", exc_info=True)
            set_domain_status(db_path, domain, "failed")

        time.sleep(10)

    logging.info("Pipeline run complete.")


if __name__ == "__main__":
    tracker = EmissionsTracker(
        project_name="gen_ai_prompt_pipeline",
        output_dir="./data",
        output_file="codecarbon_gen_ai_prompt.csv",
    )

    tracker.start()

    try:
        main()

    except KeyboardInterrupt:
        logging.info("Interrupted by user. Progress so far is saved — rerun to resume from where you left off.")
        sys.exit(130)

    finally:
        emissions = tracker.stop()
        logging.info(f"CodeCarbon emissions: {emissions} kg CO2eq")