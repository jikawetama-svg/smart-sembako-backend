import urllib.request
import json
from typing import List, Dict, Any

class HFDatasetLoader:
    """
    Loader untuk mengunduh dan mengintegrasikan dataset HuggingFace
    https://huggingface.co/datasets/SmartSembako/smart-sembako-dataset
    ke dalam RAG VectorStore & katalog produk.
    """
    DATASET_URL = "https://datasets-server.huggingface.co/rows?dataset=SmartSembako/smart-sembako-dataset&config=default&split=train&offset=0&length=100"

    @classmethod
    def fetch_hf_dataset(cls) -> List[Dict[str, Any]]:
        """Mengambil baris dataset dari HuggingFace Datasets Server API."""
        try:
            req = urllib.request.Request(cls.DATASET_URL, headers={"User-Agent": "SmartSembakoBot/6.2.0"})
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    rows = [item.get("row", {}) for item in data.get("rows", [])]
                    return rows
        except Exception as e:
            print(f"[HFDatasetLoader] Warning fallback local dataset: {e}")
        
        # Fallback catalog jika offline / offline mode
        return [
            {"code": "HF-001", "name": "Beras Ramos Super 5kg", "category": "Beras", "price": 68000, "unit": "karung"},
            {"code": "HF-002", "name": "Minyak Goreng Bimoli 2L", "category": "Minyak", "price": 34500, "unit": "pouch"},
            {"code": "HF-003", "name": "Gula Pasir Gulaku 1kg", "category": "Gula", "price": 17500, "unit": "kg"},
            {"code": "HF-004", "name": "Telur Ayam Negeri 1kg", "category": "Telur", "price": 28000, "unit": "kg"}
        ]
