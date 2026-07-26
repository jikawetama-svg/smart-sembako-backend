from typing import List, Dict, Any, Tuple
from rag.embedder import SimpleEmbedder

class VectorStore:
    def __init__(self):
        self.embedder = SimpleEmbedder()
        self.documents: List[Dict[str, Any]] = []
        self.vectors: List[Dict[str, float]] = []

    def add_document(self, doc: Dict[str, Any], text_field: str = "name"):
        text = doc.get(text_field, "")
        vec = self.embedder.embed(text)
        self.documents.append(doc)
        self.vectors.append(vec)

    def search(self, query: str, top_k: int = 5) -> List[Tuple[Dict[str, Any], float]]:
        query_vec = self.embedder.embed(query)
        scored = []
        for i, vec in enumerate(self.vectors):
            sim = self.embedder.similarity(query_vec, vec)
            scored.append((self.documents[i], sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
