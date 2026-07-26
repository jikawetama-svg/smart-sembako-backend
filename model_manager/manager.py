from typing import List, Dict, Any, Tuple, Optional
from model_manager.adapters.base import BaseModelAdapter
from model_manager.adapters.groq_adapter import GroqAdapter
from model_manager.adapters.gemini_adapter import GeminiAdapter

class ModelManager:
    def __init__(self):
        self.groq_adapter = GroqAdapter()
        self.gemini_adapter = GeminiAdapter()

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model_tier: str = "balanced",
        max_tokens: int = 500,
        temperature: float = 0.7
    ) -> Tuple[str, str]:
        """
        Melakukan chat dengan kaskade failover antar LLM providers.
        Mengembalikan tuple (response_text, provider_name_used).
        """
        providers: List[BaseModelAdapter] = []

        if model_tier == "fast":
            providers = [self.groq_adapter, self.gemini_adapter]
        elif model_tier == "vision":
            providers = [self.gemini_adapter]
        else: # "balanced" & "advanced"
            providers = [self.groq_adapter, self.gemini_adapter]

        errors = []
        for adapter in providers:
            try:
                content, _ = await adapter.chat(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                if content and content.strip():
                    return content, adapter.provider_name
            except Exception as ex:
                errors.append(f"{adapter.provider_name}: {str(ex)}")

        # Deterministic fallback response jika semua provider API key belum dikonfigurasi/down
        last_user_msg = messages[-1]["content"] if messages else ""
        fallback_msg = f"Halo! Saya Smart Sembako Cloud Bot. Data Anda aman. (Sistem AI siap diintegrasikan. Query Anda: '{last_user_msg}')"
        return fallback_msg, "fallback_local"
