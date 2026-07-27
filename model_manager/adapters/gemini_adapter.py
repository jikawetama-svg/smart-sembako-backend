import httpx
from typing import List, Dict, Any, Tuple
from config import settings
from model_manager.adapters.base import BaseModelAdapter

class GeminiAdapter(BaseModelAdapter):
    provider_name = "gemini"
    supports_vision = True

    def __init__(self, api_key: str = "", model_name: str = ""):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_name = model_name or settings.GEMINI_MODEL

    async def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **kwargs
    ) -> Tuple[str, int]:
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY tidak dikonfigurasi.")

        # Gabungkan pesan prompt
        prompt_text = "\n".join([f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages])

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{
                "parts": [{"text": prompt_text}]
            }],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=25.0)
            if response.status_code != 200:
                raise RuntimeError(f"Gemini API Error ({response.status_code}): {response.text}")

            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return "Maaf, tidak ada respons yang dihasilkan.", 0

            text_result = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return text_result, len(text_result.split())

    async def health_check(self) -> bool:
        if not self.api_key:
            return False
        try:
            _, tokens = await self.chat([{"role": "user", "content": "ping"}], max_tokens=5)
            return True
        except Exception:
            return False
