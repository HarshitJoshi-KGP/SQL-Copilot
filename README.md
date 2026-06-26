# 🧠 SQL Analytics Co-pilot

Natural language → SQL → Results → Chart → Explanation → Follow-ups

## Features
- **Schema-aware SQL generation** — injects table names, columns, sample rows into context
- **Self-correction loop** — validates SQL before running, auto-fixes errors (up to 3 retries)
- **Auto chart selection** — picks bar/line/pie/scatter based on result shape
- **Plain English explanation** — LLM explains what the query found in simple terms  
- **Follow-up suggestions** — suggests 3 next questions based on result
- **Query caching** — same question returns instantly
- **30-query eval benchmark** — measures execution accuracy + self-correction rescue rate
- **CSV upload support** — works on any data, not just demo DB
- **Free** — uses Groq API (Llama 3.1 70B), no cost

## Quickstart
```bash
pip install -r requirements.txt

# Seed demo e-commerce database
python data/seed_db.py

# Run dashboard
streamlit run dashboard/app.py
```

Get a free Groq API key at: https://console.groq.com

## Database
Demo: E-commerce DB with customers, products, orders, order_items, reviews (200 customers, 775 orders)

Or upload your own:
- CSV file → auto-converted to SQLite table
- SQLite .db file → used directly

## Benchmark Results (demo)
- Execution accuracy: ~89%
- Self-correction rescue rate: ~62%
- Average attempts: 1.18

## Resume Bullet
> Built Text2SQL co-pilot with LLM-powered self-correction loop; validator catches
> schema errors before execution; benchmarked on 30-query eval set achieving 89%
> execution accuracy across single-table, join, and window function queries.
