---
title: Smart Sembako Cloud Bot
emoji: 🛒
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
short_description: FastAPI Cloud Bot Router for Smart Sembako POS
---

# 🛒 Smart Sembako Cloud Bot (FastAPI + Supabase + Multi-Agent LLM)

Cloud Bot Runtime cerdas yang terhubung dengan database POS kasir via Supabase Cloud, mendukung verifikasi Webhook Telegram HMAC, Role-Based Access Control (RBAC), multi-agent LLM failover (Groq & Gemini), RAG fuzzy product search, serta laporan transaksi toko real-time.

## 🚀 Fitur Utamanya
- **FastAPI Endpoint**: Webhook Telegram `/webhook/telegram` & status kesehatan sistem `/` atau `/bot-health`.
- **Keamanan (HMAC & RBAC)**: Validasi `X-Telegram-Bot-Api-Secret-Token` & pembagian role (`owner`, `kasir`, `public`).
- **Supabase Cloud REST Integration**: Mengambil stok produk (`products_sync`) & ringkasan penjualan (`transactions_summary`) secara real-time.
- **RAG & Fuzzy Product Search**: Matching relevansi n-gram karakter untuk pencarian stok produk cepat.
- **Provider Failover Chain**: Groq Llama 3.1 70B ➔ Gemini 2.5 Flash ➔ Local Fallback.

## 🔧 Environment Variables / Secrets di Hugging Face Spaces

Tambahkan Secrets berikut di **Space Settings ➔ Variables and secrets**:

| Secret Name | Deskripsi |
| :--- | :--- |
| `SUPABASE_URL` | Project URL dari Supabase Console (contoh: `https://xyzabc123.supabase.co`) |
| `SUPABASE_KEY` | `service_role key` atau `anon key` Supabase |
| `TELEGRAM_BOT_TOKEN` | Token Bot Telegram dari @BotFather |
| `TELEGRAM_SECRET_TOKEN` | Token acak rahasia untuk header `X-Telegram-Bot-Api-Secret-Token` |
| `GROQ_API_KEY` | API Key dari Groq Console (opsional) |
| `GEMINI_API_KEY` | API Key dari Google AI Studio (opsional) |
| `OWNER_TELEGRAM_IDS` | Telegram User ID milik Owner toko (dipisahkan koma) |

## 📡 Webhook Setup Command
Setelah Space ini berstatus `Running`, daftarkan Webhook di Telegram via browser:
```http
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=https://<YOUR-HF-SPACE-URL>/webhook/telegram&secret_token=<TELEGRAM_SECRET_TOKEN>
```
