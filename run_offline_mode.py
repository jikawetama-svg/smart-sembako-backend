"""
Smart Sembako Assistant - Standalone Offline Mode Runner
Jalankan bot & server lokal gratis 100% tanpa biaya langganan cloud.
"""
import sys
import os
import uvicorn
from main import app

if __name__ == "__main__":
    print("=" * 65)
    print("🛒 SMART SEMBAKO ASSISTANT - MODE OFFLINE / GRATIS 100%")
    print("=" * 65)
    print("✓ Berjalan secara standalone tanpa langganan cloud / API Key berbayar.")
    print("✓ Supabase URL & API Keys opsional (otomatis fallback ke mode lokal).")
    print("✓ Web Server FastAPI aktif di: http://127.0.0.1:8000")
    print("=" * 65)
    
    uvicorn.run(app, host="127.0.0.1", port=8000)
