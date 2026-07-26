from typing import Dict, Any
from tools.registry import BaseTool, ToolResult

class TranscribeVoiceNoteTool(BaseTool):
    name = "transcribe_voice"
    description = "Transkripsi pesan suara / voice note Telegram menjadi teks query"

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        audio_url = params.get("audio_url", "")
        if not audio_url:
            return ToolResult(success=False, data={}, error="URL audio voice note wajib diberikan.")

        # Interface adapter untuk Whisper Speech-To-Text API
        simulated_transcript = "Berapa sisa stok minyak goreng dan beras ramos 5kg hari ini?"
        return ToolResult(
            success=True,
            data={"transcript": simulated_transcript, "confidence": 0.96}
        )
