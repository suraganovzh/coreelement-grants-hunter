"""LLM Cascade: Ollama (local) -> Groq (cloud free) -> Gemini (cloud free).

Centralised LLM access for the whole local pipeline.
Each task_type maps to a specific model size per provider:

  task_type   | Ollama (local)  | Groq (cloud)               | Gemini (cloud)
  ------------|-----------------|----------------------------|-------------------
  filter      | llama3.2:3b     | llama-3.1-8b-instant       | gemini-2.0-flash
  analyze     | llama3.1:8b     | llama-3.1-70b-versatile    | gemini-1.5-pro
  generate    | gemma2:9b       | mixtral-8x7b-32768         | gemini-1.5-pro
"""

import json
import os

from src.utils.logger import setup_logger

logger = setup_logger("llm_cascade")

OLLAMA_MODELS = {
    "filter": "llama3.2:3b",
    "analyze": "llama3.1:8b",
    "generate": "gemma2:9b",
}

GROQ_MODELS = {
    "filter": "llama-3.1-8b-instant",
    "analyze": "llama-3.1-70b-versatile",
    "generate": "mixtral-8x7b-32768",
}

GEMINI_MODELS = {
    "filter": "gemini-2.0-flash",
    "analyze": "gemini-1.5-pro",
    "generate": "gemini-1.5-pro",
}


class LLMCascade:
    """Cascading LLM access: local first, cloud fallback.

    Priority:
      1. Ollama locally  — free, fast, private
      2. Groq API        — free tier, fast inference
      3. Gemini API      — free tier, Google
    """

    def __init__(self):
        self._groq_key = os.getenv("GROQ_API_KEY", "")
        self._gemini_key = os.getenv("GEMINI_API_KEY", "")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chat(
        self,
        prompt: str,
        task_type: str = "analyze",
        system_prompt: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
        json_mode: bool = True,
    ) -> tuple[dict | str, str]:
        """Send *prompt* through the cascade and return (result, source).

        Parameters
        ----------
        prompt : str
            The user prompt.
        task_type : str
            One of ``"filter"``, ``"analyze"``, ``"generate"``.
        system_prompt : str | None
            Optional system instruction.
        temperature : float
            Sampling temperature.
        max_tokens : int
            Max output tokens.
        json_mode : bool
            If True, request JSON output and parse it.

        Returns
        -------
        tuple[dict | str, str]
            ``(parsed_result, source)`` where *source* is one of
            ``"ollama"``, ``"groq"``, ``"gemini"``.

        Raises
        ------
        RuntimeError
            If **all three** providers fail.
        """
        errors: list[str] = []

        # Level 1 — Ollama local
        try:
            result = self._ollama(prompt, task_type, system_prompt, temperature, max_tokens, json_mode)
            if result is not None:
                return result, "ollama"
        except Exception as exc:
            errors.append(f"ollama: {exc}")
            logger.debug("Ollama failed: %s", exc)

        # Level 2 — Groq cloud
        try:
            result = self._groq(prompt, task_type, system_prompt, temperature, max_tokens, json_mode)
            if result is not None:
                return result, "groq"
        except Exception as exc:
            errors.append(f"groq: {exc}")
            logger.debug("Groq failed: %s", exc)

        # Level 3 — Gemini cloud
        try:
            result = self._gemini(prompt, task_type, system_prompt, temperature, max_tokens, json_mode)
            if result is not None:
                return result, "gemini"
        except Exception as exc:
            errors.append(f"gemini: {exc}")
            logger.debug("Gemini failed: %s", exc)

        raise RuntimeError(f"All LLM providers failed: {'; '.join(errors)}")

    def chat_safe(
        self,
        prompt: str,
        task_type: str = "analyze",
        system_prompt: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
        json_mode: bool = True,
    ) -> tuple[dict | str | None, str]:
        """Like :meth:`chat` but returns ``(None, "none")`` on total failure."""
        try:
            return self.chat(prompt, task_type, system_prompt, temperature, max_tokens, json_mode)
        except RuntimeError:
            return None, "none"

    # ------------------------------------------------------------------
    # Provider implementations
    # ------------------------------------------------------------------

    def _ollama(self, prompt, task_type, system_prompt, temperature, max_tokens, json_mode):
        import ollama as _ollama

        model = OLLAMA_MODELS.get(task_type, "llama3.1:8b")
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict = {
            "model": model,
            "messages": messages,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if json_mode:
            kwargs["format"] = "json"

        response = _ollama.chat(**kwargs)
        text = response["message"]["content"]
        logger.debug("Ollama [%s] OK (%d chars)", model, len(text))

        if json_mode:
            return json.loads(text)
        return text

    def _groq(self, prompt, task_type, system_prompt, temperature, max_tokens, json_mode):
        if not self._groq_key:
            logger.debug("GROQ_API_KEY not set — skipping")
            return None

        from groq import Groq

        client = Groq(api_key=self._groq_key)
        model = GROQ_MODELS.get(task_type, "llama-3.1-70b-versatile")

        messages = []
        sys_text = system_prompt or ("Return ONLY valid JSON." if json_mode else "")
        if sys_text:
            messages.append({"role": "system", "content": sys_text})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = client.chat.completions.create(**kwargs)
        text = response.choices[0].message.content or ""
        logger.debug("Groq [%s] OK (%d chars)", model, len(text))

        if json_mode:
            return json.loads(text)
        return text

    def _gemini(self, prompt, task_type, system_prompt, temperature, max_tokens, json_mode):
        if not self._gemini_key:
            logger.debug("GEMINI_API_KEY not set — skipping")
            return None

        import google.generativeai as genai

        genai.configure(api_key=self._gemini_key)
        model_name = GEMINI_MODELS.get(task_type, "gemini-1.5-pro")
        model = genai.GenerativeModel(
            model_name,
            system_instruction=system_prompt if system_prompt else None,
        )

        gen_config: dict = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        if json_mode:
            gen_config["response_mime_type"] = "application/json"

        response = model.generate_content(prompt, generation_config=gen_config)
        text = response.text or ""
        logger.debug("Gemini [%s] OK (%d chars)", model_name, len(text))

        if json_mode:
            return json.loads(text)
        return text


# Singleton for convenience
_cascade: LLMCascade | None = None


def get_cascade() -> LLMCascade:
    """Return a module-level singleton :class:`LLMCascade`."""
    global _cascade
    if _cascade is None:
        _cascade = LLMCascade()
    return _cascade
