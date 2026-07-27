import os
from typing import List, Dict, Any
from rag.vector_store import VectorStore

class KnowledgeManager:
    """
    Manages Store SOPs, store rules, FAQs, and business knowledge documents.
    Syncs local SOP files with in-memory RAG VectorStore & Supabase.
    """

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.vector_store = VectorStore()
        self._is_indexed = False

    def load_and_index_sops(self) -> int:
        """Reads local markdown/text files from data/ directory and indexes chunks into VectorStore."""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)
            self._create_default_sop(os.path.join(self.data_dir, "sop_toko.md"))

        count = 0
        for root, _, files in os.walk(self.data_dir):
            for file in files:
                if file.endswith((".md", ".txt")):
                    filepath = os.path.join(root, file)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            content = f.read()

                        # Split into paragraph chunks
                        chunks = [c.strip() for c in content.split("\n\n") if len(c.strip()) > 20]
                        for i, chunk in enumerate(chunks):
                            self.vector_store.add_document({
                                "source": file,
                                "chunk_id": i,
                                "content": chunk
                            }, text_field="content")
                            count += 1
                    except Exception as e:
                        print(f"[KnowledgeManager Error]: Failed to read {file}: {e}")

        self._is_indexed = True
        return count

    def search_knowledge(self, query: str, top_k: int = 3) -> str:
        if not self._is_indexed:
            self.load_and_index_sops()

        results = self.vector_store.search(query, top_k=top_k)
        relevant_chunks = []
        for doc, score in results:
            if score > 0.15:  # Relevance threshold
                relevant_chunks.append(f"[{doc.get('source')}]: {doc.get('content')}")

        if not relevant_chunks:
            return ""

        return "\n---\n".join(relevant_chunks)

    def _create_default_sop(self, filepath: str):
        default_sop = """# SOP Standar Operasional Toko Sembako

## 1. Aturan Retur Barang
- Barang cair (minyak, susu) dapat diretur dalam 1x24 jam jika terjadi kebocoran saat pembelian.
- Barang kadaluarsa yang lolos dari kasir wajib diganti 100% barang baru.

## 2. Kebijakan Piutang / Pelanggan
- Pembayaran piutang pelanggan dapat dilakukan secara partial atau lunas melalui sistem POS.
- Batas maksimal piutang per pelanggan regular adalah Rp 500.000 dengan jatuh tempo 14 hari.

## 3. Penyimpanan & Restock Barang
- Barang cepat laku (Fast Moving) seperti beras, minyak goreng, dan gula pasir diprioritaskan untuk restock setiap awal minggu.
- Produk dengan tanggal kedaluwarsa mendekati (kurang dari 30 hari) ditarik ke rak depan (First Expired First Out).
"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(default_sop)
