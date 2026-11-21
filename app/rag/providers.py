"""Real embedding and generation providers, created only when they are used.

Tests replace both with small fakes, so the test suite needs no model download,
network or API key. The Groq key is read from the server's environment and is
never sent to the browser or written to a trace.
"""

from dataclasses import dataclass
import math
import os
import time
from typing import Protocol

import httpx

EMBED_MODEL = os.environ.get("RAG_EMBED_MODEL", "BAAI/bge-small-en-v1.5")
CHAT_MODEL = os.environ.get("RAG_CHAT_MODEL", "openai/gpt-oss-20b")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class Embedder(Protocol):  # pylint: disable=too-few-public-methods
    """Turns texts into vectors; the same model must embed chunks and questions."""

    model: str

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one normalized vector per text."""


class ChatModel(Protocol):  # pylint: disable=too-few-public-methods
    """Writes an answer from the messages it is given."""

    model: str

    def complete(self, messages: list[dict], json_mode: bool = False) -> str:
        """Return the model's reply text."""


def normalize(vector) -> list[float]:
    """Scale to length 1 so a dot product is the cosine similarity."""
    values = [float(value) for value in vector]
    length = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / length for value in values]


class FastEmbedder:  # pylint: disable=too-few-public-methods
    """Local ONNX embeddings with fastembed (no API key; downloads the model once)."""

    def __init__(self, model: str = EMBED_MODEL) -> None:
        # Imported here so the web app and tests start without the package.
        # pylint: disable-next=import-outside-toplevel,import-error
        from fastembed import TextEmbedding

        self.model = model
        self._engine = TextEmbedding(model)

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of passages or questions."""
        return [normalize(vector) for vector in self._engine.embed(texts)]


@dataclass
class GroqChat:
    """Groq's OpenAI-compatible chat API, called from the server only."""

    api_key: str
    model: str = CHAT_MODEL
    timeout: float = 30.0

    def complete(self, messages: list[dict], json_mode: bool = False) -> str:
        """Send the messages and return the reply text."""
        body: dict = {"model": self.model, "messages": messages, "temperature": 0}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        for attempt in range(4):
            response = httpx.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=body,
                timeout=self.timeout,
            )
            if response.status_code != 429 or attempt == 3:
                break
            # Free tier: 30 requests/minute. Wait as long as Groq asks, then retry.
            time.sleep(min(float(response.headers.get("retry-after", 5)), 30))
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"] or ""


def groq_from_environment() -> GroqChat:
    """Build the chat model from GROQ_API_KEY, failing clearly when it is missing."""
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GROQ_API_KEY is not set on this server.")
    return GroqChat(api_key=key)
