import os
from typing import Generator
from app.config import settings

_llm = None


def get_llm():
    global _llm
    if _llm is None and os.path.exists(settings.model_path):
        from llama_cpp import Llama
        _llm = Llama(model_path=settings.model_path, n_ctx=512, n_threads=4)
    return _llm


def generate_response(prompt: str, max_tokens: int = 300) -> str:
    llm = get_llm()
    if llm is None:
        return "[LLM not available: model.gguf not found. Place a GGUF model file at the path set in MODEL_PATH]"
    result = llm(prompt, max_tokens=max_tokens, stream=False)
    return result["choices"][0]["text"].strip()


def generate_streaming(prompt: str, max_tokens: int = 300) -> Generator[str, None, None]:
    llm = get_llm()
    if llm is None:
        yield "[LLM not available: model.gguf not found]"
        return
    stream = llm(prompt, max_tokens=max_tokens, stream=True)
    for chunk in stream:
        token = chunk["choices"][0]["text"]
        if token:
            yield token


def build_prompt(messages: list[dict]) -> str:
    """Build a simple prompt from message history."""
    lines = []
    for m in messages[-6:]:  # last 6 messages for context
        role = "User" if m["role"] == "user" else "Assistant"
        lines.append(f"{role}: {m['content']}")
    lines.append("Assistant:")
    return "\n".join(lines)
