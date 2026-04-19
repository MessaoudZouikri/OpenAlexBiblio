"""
Local LLM client for Ollama.
Handles health checks, prompt formatting, JSON output validation,
retry logic, and graceful fallback for classification tasks.
"""
import json
import logging
import time
from typing import Any, Dict, Optional, Tuple

import requests

logger = logging.getLogger("llm_client")


class OllamaClient:
    """
    HTTP client for local Ollama inference server.
    Designed for deterministic, structured-output tasks (classification).
    
    All LLM outputs are treated as HYPOTHESES to validate, not facts.
    """

    def __init__(
        self,
        endpoint: str = "http://localhost:11434",
        model: str = "qwen2.5:7b",
        temperature: float = 0.1,
        max_tokens: int = 256,
        max_retries: int = 3,
        timeout: int = 60,
        fallback_models: Optional[list] = None,
    ):
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.timeout = timeout
        self.fallback_models = fallback_models or []
        self._available = None  # Cached availability check

    # ── Health Check ──────────────────────────────────────────────────────

    def is_available(self, timeout: int = 5) -> bool:
        """Check if Ollama server is reachable and model is loaded."""
        try:
            resp = requests.get(f"{self.endpoint}/api/tags", timeout=timeout)
            if resp.status_code != 200:
                return False
            models = [m["name"] for m in resp.json().get("models", [])]
            available = any(self.model.split(":")[0] in m for m in models)
            if not available:
                logger.warning("Model %s not found in Ollama. Available: %s", self.model, models)
            return available
        except Exception as exc:
            logger.warning("Ollama not reachable at %s: %s", self.endpoint, exc)
            return False

    def get_active_model(self) -> Optional[str]:
        """Return the first available model from primary + fallback list."""
        candidates = [self.model] + self.fallback_models
        for model in candidates:
            client = OllamaClient(self.endpoint, model)
            if client.is_available():
                if model != self.model:
                    logger.info("Using fallback model: %s", model)
                return model
        return None

    # ── Core Generation ───────────────────────────────────────────────────

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
    ) -> Tuple[str, bool]:
        """
        Generate text from the LLM.
        
        Returns:
            (response_text, success_flag)
        """
        active_model = model or self.model
        payload = {
            "model": active_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
        }

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = requests.post(
                    f"{self.endpoint}/api/chat",
                    json=payload,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                text = resp.json()["message"]["content"].strip()
                return text, True
            except Exception as exc:
                logger.warning("LLM attempt %d/%d failed: %s", attempt, self.max_retries, exc)
                if attempt < self.max_retries:
                    time.sleep(1.0 * attempt)
        return "", False

    # ── JSON Output with Validation ───────────────────────────────────────

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        required_keys: Optional[list] = None,
    ) -> Tuple[Optional[Dict[str, Any]], bool]:
        """
        Generate and parse a JSON response from the LLM.
        
        Includes cleanup of markdown code fences and validation.
        Returns:
            (parsed_dict or None, success_flag)
        """
        text, ok = self.generate(system_prompt, user_prompt)
        if not ok or not text:
            return None, False
        
        # Attempt to extract JSON from response
        parsed = self._extract_json(text)
        if parsed is None:
            logger.warning("Failed to parse LLM JSON response: %s", text[:200])
            return None, False
        
        # Validate required keys
        if required_keys:
            missing = [k for k in required_keys if k not in parsed]
            if missing:
                logger.warning("LLM response missing keys %s: %s", missing, text[:200])
                return None, False
        
        return parsed, True

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict]:
        """
        Extract JSON from LLM output that may contain markdown fences or extra text.
        """
        # Strip markdown fences
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(
                line for line in lines
                if not line.startswith("```")
            ).strip()
        
        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Try to find JSON object within text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
        
        return None


# ── Validation Helpers ─────────────────────────────────────────────────────

VALID_DOMAINS = {"Political Science", "Economics", "Sociology", "Other"}

VALID_SUBCATEGORIES = {
    "Political Science": {
        "comparative_politics", "political_theory", "electoral_politics",
        "democratic_theory", "radical_right", "latin_american_politics", "european_politics",
    },
    "Economics": {
        "political_economy", "redistribution", "trade_globalization", "financial_crisis",
    },
    "Sociology": {
        "social_movements", "identity_politics", "media_communication", "culture_values",
    },
    "Other": {
        "international_relations", "history", "psychology", "geography", "interdisciplinary",
    },
}


def validate_classification_response(response: Dict) -> Tuple[bool, str]:
    """
    Validate a classification JSON response from the LLM.
    Returns (is_valid, error_message).
    """
    domain = response.get("domain", "")
    subcategory = response.get("subcategory", "")
    confidence = response.get("confidence")
    
    if domain not in VALID_DOMAINS:
        return False, f"Invalid domain: '{domain}'"
    
    valid_subs = VALID_SUBCATEGORIES.get(domain, set())
    if subcategory not in valid_subs:
        return False, f"Invalid subcategory '{subcategory}' for domain '{domain}'"
    
    if not isinstance(confidence, (int, float)) or not (0.0 <= confidence <= 1.0):
        return False, f"Invalid confidence: {confidence}"
    
    return True, ""

# Backward compatibility alias
LLMClient = OllamaClient

