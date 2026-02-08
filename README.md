# PharmaSentinel

**Hospital Pharmacy Supply Chain Intelligence Platform**

A multi-agent AI supply-chain system that predicts drug shortages, finds substitutes, and generates purchase orders to prevent surgical disruptions.  
Built for **TartanHacks 2026** at **Carnegie Mellon University**.

---

## Overview

For example purposes PharmaSentinel monitors **10 critical hospital drugs** and uses AI agents to:

- **Predict shortages** via FDA data and Web Search
- **Find clinical substitutes** dynamically when drugs are unavailable (the Substitute Agent identifies valid alternatives)
- **Optimize supplier selection** based on urgency, cost, location, and supply chain signals
- **Generate autonmatic purchase orders** from distributors and usage prediction

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              FRONTEND (React + TypeScript)                   │
│     Dashboard | Drugs | Shortages | Suppliers | Orders       │
│                   (Supabase Realtime)                        │
└───────────────────────┬─────────────────────────────────────┘
                        │
                   PostgreSQL 
                        │
┌───────────────────────▼─────────────────────────────────────┐
│                 BACKEND SERVER (server.py)                   │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐     │
│  │  CONTINUOUS PIPELINE (runs every ~60 min)           │     │
│  │  Phase 1: Agent 0 (Inventory) + Agent 1 (FDA)       │     │
│  │  Phase 2: Agent 2 (News via Web MCP)              │     │
│  │  Phase 3: Overseer → Alerts + Agent 3 (Substitutes) │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐     │
│  │  ORDER AGENT (API-triggered)           │     │
│  │  Agent 4: Pricing Analysis & Order Generation       │     │
│  └─────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────┘
```

**server.py** must be running to power the system. It manages:
1. **Continuous Pipeline** — scheduled checks on FDA data, news, and inventory
2. **API Endpoints** — allows the frontend to trigger the Order Agent independently

### Agents
| Agent | Role |
|-------|------|
| **Agent 0 (Inventory)** | Monitors stock, predicts usage (based on surgery schedule), calculates burn rates |
| **Agent 1 (FDA)** | Pulls FDA drug shortage database |
| **Agent 2 (News)** | Uses Web (Brave) MCP to find supply chain disruption signals from news|
| **Overseer** | Synthesizes data from Agent 0-2 into actionable alerts |
| **Agent 3 (Substitutes)** | Substitute Agent finds valid clinical substitutes when drugs are unavailable |
| **Agent 4 (Orders)** | Analyzes pricing/availability, builds purchase orders |

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Supabase project
- LLM API Keys (Anthropic/OpenAI/Dedalus etc.)

### 1. Database Setup
1. Create a Supabase project
2. Run `db/schema.sql` in the SQL Editor
3. Run `db/seed_data.sql` to populate example data

### 2. Backend
```bash
pip install -r requirements.txt

# Configure .env with:
# SUPABASE_URL, SUPABASE_SERVICE_KEY, ANTHROPIC_API_KEY, etc.

# Start the server (required for pipeline + API)
python server.py
```

### 3. Frontend
```bash
cd frontend
npm install
npm run dev
```
---

## Future Work

- **Manual Drug Entry** — Allow users to manually add new drugs to the monitoring list via the UI
- **Database Integration** — Connect directly to existing hospital inventory databases

