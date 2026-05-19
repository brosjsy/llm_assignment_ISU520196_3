"""LLM service — wraps llama-cpp-python, stateless, one instance per process."""
import os
from typing import Generator

from app.config import settings


class LLMService:
    """Thin wrapper around the local GGUF model loaded via llama-cpp-python."""

    _model = None  # module-level singleton

    def _get_model(self):
        if LLMService._model is None and os.path.exists(settings.model_path):
            from llama_cpp import Llama
            LLMService._model = Llama(
                model_path=settings.model_path,
                n_ctx=512,
                n_threads=4,
            )
        return LLMService._model

    def generate(self, prompt: str, max_tokens: int = 300) -> str:
        """Return the full LLM completion for *prompt* (non-streaming)."""
        model = self._get_model()
        if model is None:
            return (
                "[LLM not available: model file not found. "
                f"Place a GGUF model at {settings.model_path!r}]"
            )
        result = model(prompt, max_tokens=max_tokens, stream=False)
        return result["choices"][0]["text"].strip()

    def generate_streaming(
        self, prompt: str, max_tokens: int = 300
    ) -> Generator[str, None, None]:
        """Yield tokens one-by-one (streaming)."""
        model = self._get_model()
        if model is None:
            yield "[LLM not available: model file not found]"
            return
        for chunk in model(prompt, max_tokens=max_tokens, stream=True):
            token = chunk["choices"][0]["text"]
            if token:
                yield token

    @staticmethod
    def build_prompt(messages: list[dict]) -> str:
        """Build a plain-text prompt from the last 6 messages of history."""
        lines = []
        for m in messages[-6:]:
            role = "User" if m["role"] == "user" else "Assistant"
            lines.append(f"{role}: {m['content']}")
        lines.append("Assistant:")
        return "\n".join(lines)
