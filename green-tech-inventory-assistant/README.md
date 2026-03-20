# 🌿 Green-Tech Inventory Assistant

**Candidate Name**: Jujjavarapu Raviteja  
**Scenario Chosen**: Green-Tech Inventory Assistant  
**Estimated Time Spent**: ~5.5 hours  

## Problem Statement

Small organizations (cafés, labs, non-profits) frequently over-order perishable goods, face unexpected stockouts, and lack data-driven tools to make procurement decisions. This assistant provides deterministic, trustworthy reorder recommendations alongside optional AI-powered natural-language explanations to help managers optimize stock constraints, minimizing waste and avoiding expirations.

## Quick Start

The app utilizes a persistent, built-in SQLite database (`data/inventory.db`) that comes pre-seeded with synthetic suppliers, items, and usage logs. 

```bash
# 1. Navigate to the project
cd green-tech-inventory-assistant

# 2. Create virtual environment
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

### 4. Environment Variables
Copy the example environment file and add your Groq API key:
```bash
cp .env.example .env
```
Open `.env` and set `GROQ_API_KEY=your_actual_api_key_here`.
*(Note: The app will run smoothly with rule-based text generation if you choose not to provide an API key).*
*(Get a free API key from [Groq Console](https://console.groq.com)).*

# 5. Seed the database (auto-runs on first launch, or explicitly run it)
python seed_db.py
```

## Run Commands

```bash
# Start the Streamlit application
python -m streamlit run app.py
```

## Test Commands

The project includes 19 comprehensive automated tests covering the deterministic math engine, edge cases, and isolated database CRUD operations.

```bash
# Run all tests
pytest tests/ -v

# Run specific suites
pytest tests/test_happy_path.py -v     # 5 happy-path behavioral tests
pytest tests/test_edge_case.py -v      # 9 critical missing data / negative boundary tests
pytest tests/test_database.py -v       # 5 isolated SQLite integration tests
```

## AI Disclosure

This project uses Groq's LLM API (Llama 3.3 70B via OpenAI-compatible SDK) **only** for generating natural-language explanations of mathematically deterministic inventory recommendations linking stockouts to waste risks. All inventory logic occurs definitively within local Python modules (`reorder_engine.py`) to maintain auditability and credibility. 

The application operates fully offline locally without AI — via identical, equivalent Fallback templates triggered seamlessly through the Sidebar toggle ("Simulate AI unavailable").

## One Suggestion Rejected/Changed

Initially, AI was experimented with for inferring actual future usage algorithms instead of just language translation. I actively **rejected** this suggestion to maintain strict product trust and avoid "black-box" unpredictability. AI should assist the operator to quickly decipher the data rather than directly making algorithmic business executions on its own unstructured weights. I anchored the generative AI rigidly to the outputs of the safe Python logic engine so it cannot hallucinate non-existent stock quantities.

## What I Cut to Stay in the Timebox

To strictly remain within the 5.5-hour scope limit while retaining maximal impact, the following were explicitly omitted:
- **PostgreSQL / Multi-User Architecture**: Relying purely on SQLite drastically improved local prototype stability, at the complete cost of multi-user concurrency tracking and RBAC authorization overheads.
- **Physical Integration**: Barcode scanner inputs or live POS API webhooks are completely excluded, simulated safely via `seed_db.py`.
- **Optimization Algorithms**: A strict lack of complex multi-item mathematical purchasing optimization.
- **Extended Horizons**: Projections explicitly cut off gracefully at exactly 7-days, preventing arbitrary guess factors extending outwards.

## Known Limitations

- **Single-User Focused**: Due to SQLite lock configurations, it is optimized purely for single operators, rendering it fragile under high concurrent multi-user writes.
- **Aggressive Perishable Capping**: The code rigidly restricts perishable goods orders to *exactly* what can be used before expiry. If demand spikes unpredictably, this aggressive cap could trigger localized stockouts.
- **No Partial Deliveries**: Simulated shipments assume perfect logistics, fulfilling 100% of quantity demands instantly upon completed lead times.

## Video Link

https://youtu.be/3N8YczN2KDw
