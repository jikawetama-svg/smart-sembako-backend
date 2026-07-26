import asyncio
from typing import List, Dict, Any
from model_manager.manager import ModelManager

class MapReduceCompressor:
    def __init__(self, model_manager: ModelManager):
        self.model_manager = model_manager

    async def summarize_large_dataset(self, records: List[Dict[str, Any]], query: str) -> str:
        """
        Bagi dataset besar (>20 record) menjadi chunks, ringkas secara paralel,
        lalu gabungkan menjadi final summary.
        """
        if not records:
            return "Tidak ada data untuk diringkas."

        if len(records) <= 20:
            lines = [f"- {r.get('name', 'Item')}: {r.get('stock', 0)} {r.get('unit', 'pcs')}" for r in records]
            return "\n".join(lines)

        # Split into chunks of 20
        chunks = [records[i:i+20] for i in range(0, len(records), 20)]

        # Map phase - ringkas tiap chunk
        map_tasks = []
        for idx, chunk in enumerate(chunks):
            chunk_str = ", ".join([f"{r.get('name')}: {r.get('stock')}" for r in chunk])
            prompt = [
                {"role": "system", "content": "Ringkas data produk dan stok berikut secara singkat."},
                {"role": "user", "content": f"Query: '{query}'. Data Chunk {idx+1}: {chunk_str}"}
            ]
            map_tasks.append(self.model_manager.chat(prompt, model_tier="fast"))

        map_results = await asyncio.gather(*map_tasks)
        summaries = [res[0] for res in map_results]

        # Reduce phase - gabungkan hasil summary
        combined_summaries = "\n".join(summaries)
        reduce_prompt = [
            {"role": "system", "content": "Gabungkan ringkasan berikut menjadi jawaban laporan akhir yang rapi dan profesional."},
            {"role": "user", "content": f"Query: '{query}'. Ringkasan per bagian:\n{combined_summaries}"}
        ]
        final_summary, _ = await self.model_manager.chat(reduce_prompt, model_tier="balanced")

        return final_summary
