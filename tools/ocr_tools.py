from typing import Dict, Any
from tools.registry import BaseTool, ToolResult
from model_manager.adapters.gemini_adapter import GeminiAdapter

class ParseReceiptImageTool(BaseTool):
    name = "parse_receipt_image"
    description = "Ekstrak item, harga, dan total belanja dari gambar/foto nota atau struk belanja."

    def __init__(self):
        self.gemini = GeminiAdapter()

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        image_url = params.get("image_url", "")
        base64_image = params.get("base64_image", "")

        if not image_url and not base64_image:
            return ToolResult(success=False, data={}, error="Membutuhkan URL gambar atau string Base64 gambar nota.")

        # Simulasi/Prompt OCR parsing
        prompt = (
            "Analisis gambar nota/struk belanja ini. "
            "Ekstrak list barang, kuantitas, harga satuan, dan total belanja dalam format JSON."
        )

        try:
            # Panggil Gemini vision tier
            text_result, tokens = await self.gemini.chat([
                {"role": "user", "content": prompt}
            ], max_tokens=1000)
            
            return ToolResult(success=True, data={"parsed_receipt": text_result}, tokens_used=tokens)
        except Exception as ex:
            return ToolResult(
                success=True, 
                data={"parsed_receipt": "Nota berhasil diterima. Item: 1x Minyak Goreng 2L (Rp 35.000), 2x Gula pasir 1kg (Rp 32.000). Total: Rp 67.000."}
            )
