from typing import Optional
import logging
import time
from google import genai
from google.genai import types

def _get_status_code(exc: Exception) -> Optional[int]:
    """Extract HTTP status code from Groq / httpx exceptions."""
    if hasattr(exc, "status_code"):
        return exc.status_code
    response = getattr(exc, "response", None)
    if response is not None:
        return getattr(response, "status_code", None)
    return None


def safe_api_call(
    system_prompt: str, 
    user_content: str, 
    client: str,
    model_id: str, 
    max_tokens: int = 4096, 
    retries: int = 3
) -> str:
    """Safely executes Gemini API requests with structured JSON schema enforcement."""
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model=model_id,
                contents=user_content,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.2,
                    max_output_tokens=max_tokens,
                    response_mime_type="application/json",  # Forces valid JSON natively
                ),
            )
            impacts = getattr(response, "impacts", None)
            if impacts is not None:
                logging.info(f"EcoLogits impacts for model '{model_id}': {impacts}")

            return response.text

        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                delay = 10.0 * (attempt + 1)
                logging.warning(f"Gemini Rate Limit hit. Sleeping {delay}s...")
                time.sleep(delay)
                continue
            
            logging.error(f"Gemini API Attempt {attempt + 1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(4.0)

    raise RuntimeError(f"Gemini API completion failed after {retries} attempts.")