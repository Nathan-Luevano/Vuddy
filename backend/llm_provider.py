"""
Vuddy Backend — LLM Provider Abstraction.
Every LLM call goes through this module. Never call Ollama or PatriotAI directly.
Active provider is selected by LLM_PROVIDER env var.
"""

import os

import httpx

from backend.constants import LLM_PROVIDERS

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")


class LLMProvider:
    """Base class for LLM providers."""

    async def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        raise NotImplementedError

    async def health_check(self) -> bool:
        raise NotImplementedError

    @property
    def name(self) -> str:
        raise NotImplementedError


class OllamaProvider(LLMProvider):
    """Ollama local LLM. Works out of the box with `ollama serve`."""

    def __init__(self):
        self.base_url = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.model = os.getenv("OLLAMA_MODEL", "qwen3:8b")
        self.client = httpx.AsyncClient(timeout=180.0)

    @property
    def name(self) -> str:
        return "ollama"

    async def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        payload = {
            "model": self.model,
            "messages": messages,
            "options": {"num_ctx": 4096},
            "keep_alive": -1,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
        resp = await self.client.post(f"{self.base_url}/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {})

    async def health_check(self) -> bool:
        try:
            resp = await self.client.get(f"{self.base_url}/api/tags")
            return resp.status_code == 200
        except Exception:
            return False


class PatriotAIProvider(LLMProvider):
    """PatriotAI cloud LLM. Swap to this for judging."""

    def __init__(self):
        self.base_url = os.getenv("PATRIOTAI_BASE_URL", "https://api.patriotai.com/v1")
        self.api_key = os.getenv("PATRIOTAI_API_KEY", "")
        self.model = os.getenv("PATRIOTAI_MODEL", "patriotai-default")
        self.client = httpx.AsyncClient(timeout=60.0)

    @property
    def name(self) -> str:
        return "patriotai"

    async def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {"model": self.model, "messages": messages}
        if tools:
            payload["tools"] = tools
        resp = await self.client.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]

    async def health_check(self) -> bool:
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            resp = await self.client.get(f"{self.base_url}/models", headers=headers)
            return resp.status_code == 200
        except Exception:
            return False


def create_llm_provider() -> LLMProvider:
    """Factory: create the active LLM provider based on env var."""
    if LLM_PROVIDER == "patriotai":
        return PatriotAIProvider()
    return OllamaProvider()  # default
