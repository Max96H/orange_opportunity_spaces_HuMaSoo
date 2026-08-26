import logging
import json
from src.backend.safe_api_calls import safe_api_call
from typing import Dict, Any, List
import time

def score_single_opportunity(opportunity: Dict[str, Any], 
                             model_id: str,
                             system_prompt: str,
                             client: str) -> Dict[str, Any]:
    """Helper function to call API and score one opportunity space."""
    user_payload = json.dumps(opportunity, separators=(',', ':'))
    user_content = f"Input:\n{user_payload}"
    try:
        # Calls your existing safe_api_call function from earlier steps
        raw_response = safe_api_call(system_prompt, user_content, client, model_id, max_tokens=4096)
        
        # Clean potential markdown wrapping if returned
        cleaned = raw_response.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        
        score_data = json.loads(cleaned.strip())
        return score_data

    except Exception as e:
        logging.warning(f"Failed to score opportunity '{opportunity.get('technology_name')}': {e}")
        # Return fallback zeroed structure on failure so pipeline doesn't break
        return {
            "score": 0.0,
            "components": {
                "market_signal_strength": 0.0,
                "source_diversity": 0.0,
                "evidence_quality": 0.0
            }
        }


def generate_scoring(opportunity_spaces: List[Dict[str, Any]], 
                     model: str,
                     system_prompt: str,
                     client: str) -> List[Dict[str, Any]]:
    """Iterates through all opportunity spaces, scores them, and sorts them by final score.

    :param opportunity_spaces: List of dicts produced by Step 2.
    :param model_id: Specific model to use.
    :return: Updated list of opportunity spaces sorted by score descending.
    """
    logging.info(f"Starting Step 3: Scoring {len(opportunity_spaces)} opportunity spaces...")

    scored_spaces = []
    
    for idx, opp in enumerate(opportunity_spaces, start=1):
        tech_name = opp.get("technology_name", f"Space {idx}")
        logging.info(f"Scoring [{idx}/{len(opportunity_spaces)}]: {tech_name}")

        # Compute scores using LLM engine
        score_result = score_single_opportunity(opp, model, system_prompt, client)

        # Attach score breakdown into the dictionary
        opp["final_score"] = score_result.get("score", 0.0)
        opp["score_components"] = score_result.get("components", {
            "market_signal_strength": 0.0,
            "source_diversity": 0.0,
            "evidence_quality": 0.0
        })

        scored_spaces.append(opp)
        logging.info("Space scored, pausing 10 seconds before next scoring.")
        time.sleep(10)

    # Sort opportunities from highest attractiveness to lowest
    scored_spaces.sort(key=lambda x: x.get("final_score", 0.0), reverse=True)
    
    logging.info("Step 3 complete. Opportunities successfully scored and sorted.")
    return scored_spaces
