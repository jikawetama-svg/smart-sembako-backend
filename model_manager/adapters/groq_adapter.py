import httpx
from typing import List, Dict, Any, Tuple
from config import settings
from model_manager.adapters.base import BaseModelAdapter

class GroqAdapter(BaseModelAdapter):
    provider_name = "groq"

    def __init__(self, api_key: str = "", model_name: str = ""):
        self.api_key = api_key or settings.GROQ_API_KEY
        self.model_name = model_name or settings.GROQ_MODEL

    async def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 500,
        temperature: float = 0.7,
        **kwargs
    ) -> Tuple[str, int]:
        if not self.api_key:
            raise ValueError("GROQ_API_KEY tidak dikonfigurasi.")

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=20.0)
            if response.status_code != 200:
                raise RuntimeError(f"Groq API Error ({response.status_code}): {response.text}")

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            tokens_used = data.get("usage", {}).get("total_tokens", 0)
            return content, tokens_used

    async def health_check(self) -> bool:
        if not self.api_key:
            return False
        try:
            _, tokens = await self.chat([{"role": "user", "content": "ping"}], max_tokens=5)
            return True
        except Exception:
            return False
