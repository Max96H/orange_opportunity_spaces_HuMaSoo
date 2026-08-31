from typing import Optional, List
import logging
import time
from google import genai
from google.genai import types
import os
import itertools


def get_next_client(key_pool, CLIENT_CACHE) -> tuple[genai.Client, str]:
    """Retrieves the next client and a masked key for logging."""
    key = next(key_pool)
    masked_key = f"...{key[-4:]}"
    return CLIENT_CACHE[key], masked_key


def safe_api_call(
    system_prompt: str, 
    user_content: str, 
    models: List[str], 
    #json_format,
    max_tokens: int = 4096, 
    retries_per_key: int = 3
) -> str:
    """
    Executes a Gemini generation call with double-fallback resiliency:
    1. Iterates through fallback models (e.g., gemini-3.6-flash -> gemini-3.5-flash-lite).
    2. Rotates through available API keys on 429/ResourceExhausted errors.
    """
    API_KEYS = [
        key for key in [
            os.getenv("GEMINI_API_KEY_1"),
            os.getenv("GEMINI_API_KEY_2"),
            os.getenv("GEMINI_API_KEY_3")
        ] if key  # Filter out None/empty strings
    ]


    # Create an infinite round-robin iterator over your API keys
    key_pool = itertools.cycle(API_KEYS)

    # Re-using SDK clients prevents overhead from creating connections repeatedly
    CLIENT_CACHE = {key: genai.Client(api_key=key) for key in API_KEYS}


    last_exception: Optional[Exception] = None

    # LEVEL 1: Iterate through models from primary to secondary
    for model_id in models:
        logging.info(f"Attempting inference with model target: {model_id}")

        # LEVEL 2: Rotate across all available API keys for this model
        for key_attempt in range(len(API_KEYS)):
            print("entered loop", key_attempt)
            client, masked_key = get_next_client(key_pool, CLIENT_CACHE)

            for attempt in range(retries_per_key):
                try:
                    response = client.models.generate_content(
                        model=model_id,
                        contents=user_content,
                        config=types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            temperature=0.1,
                            max_output_tokens=max_tokens,
                            response_mime_type="application/json",
                            # response_schema=json_format,
                            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
                        ),
                    )
                    #print("Response from llm : ", response.text)
                    return response.text

                except Exception as e:
                    last_exception = e
                    error_msg = str(e)

                    # Catch rate limits or quota exhaustion
                    if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                        logging.warning(
                            f"Key [{masked_key}] hit rate limit on '{model_id}' "
                            f"(Attempt {attempt + 1}/{retries_per_key})."
                        )
                        # Switch keys immediately on quota issues
                        break

                    # Handle non-quota errors (transient network glitches)
                    logging.error(f"Error on key [{masked_key}] with model '{model_id}': {e}")
                    if attempt < retries_per_key - 1:
                        time.sleep(5.0)
                        logging.warning("Waiting 5 secondes before retry...")

        logging.warning(f"All API keys exhausted for model '{model_id}'. Falling back to next model...")

    raise RuntimeError(
        f"All API keys and model candidates were exhausted. Last error: {last_exception}"
    )