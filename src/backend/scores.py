import logging
from typing import Dict, Any, List, Tuple


MSS_SCORING = {0: 0, 1: 2, 2: 4, 3: 5, 4: 6, 5: 7, 6: 8, 7: 9}
SD_SCORING = {0: 0, 1: 3, 2: 7, 3: 10}


def score_single_opportunity(signals_and_sources: Dict[str, Any]) -> Tuple[int]:
    market_signal_strength = 0
    source_diversity = 0
    n_type = 0
    n_signals = 0
    for type, signals in signals_and_sources.items():
        if len(signals) >= 1:
            n_type += 1
            n_signals += len(signals)
    
    if n_signals >= 8:
        market_signal_strength = 10
    else:
        market_signal_strength = MSS_SCORING[n_signals]
    source_diversity = SD_SCORING[n_type]

    return market_signal_strength, source_diversity
    


def generate_scoring(opportunity_spaces: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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

        signals_and_sources = opp.get("signals_and_sources", {})
        opp["market_signal_strength"], opp["source_diversity"] = score_single_opportunity(signals_and_sources)

    
        opp["final_score"] = opp["market_signal_strength"]*0.4 + opp["source_diversity"]*0.2 + opp["weighted_score"]*0.4
        scored_spaces.append(opp)

    scored_spaces.sort(key=lambda x: x.get("final_score", 0.0), reverse=True)
    
    logging.info("Step 3 complete. Opportunities successfully scored and sorted.")
    return scored_spaces
