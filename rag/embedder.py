import math
from typing import List, Dict

class SimpleEmbedder:
    """
    Lightweight character n-gram TF-IDF vectorizer for zero-dependency product embedding.
    """
    def __init__(self, ngram_size: int = 3):
        self.ngram_size = ngram_size

    def _get_ngrams(self, text: str) -> Dict[str, float]:
        clean = text.lower().strip()
        counts = {}
        for i in range(len(clean) - self.ngram_size + 1):
            gram = clean[i:i+self.ngram_size]
            counts[gram] = counts.get(gram, 0) + 1.0
        
        # Normalize vector
        length = math.sqrt(sum(v*v for v in counts.values())) or 1.0
        return {k: v / length for k, v in counts.items()}

    def embed(self, text: str) -> Dict[str, float]:
        return self._get_ngrams(text)

    def similarity(self, vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
        # Cosine similarity for sparse ngram vectors
        score = 0.0
        for k, v in vec1.items():
            if k in vec2:
                score += v * vec2[k]
        return score
