# PharmaSentinel

**Hospital Pharmacy Supply Chain Intelligence Platform**

A multi-agent AI system that predicts drug shortages, recommends substitutes, optimizes ordering, and prevents surgical disruptions through real-time supply chain monitoring.  
Built for **TartanHacks at Carnegie Mellon University**.

---

## Overview

PharmaSentinel monitors 10 critical hospital drugs (ranked by criticality 1-10) and uses AI agents to:

- **Predict shortages** via FDA data and web Search
- **Find clinical substitutes** using AI agents when drugs are unavailable
- **Optimize supplier selection** based on urgency, cost, reliability, and is based on potential disruption signals
- **Generate purchase orders** from distributors or nearby hospitals
- **Monitor supply chain risks** via web Search (finding news/updates)

### The 10 Monitored Drugs (Example)

1. **Epinephrine** — Anaphylaxis/Cardiac (life-saving)
2. **Oxygen** — Respiratory Support
3. **Levofloxacin** — Broad-Spectrum Antibiotic
4. **Propofol** — Anesthetic
5. **Penicillin** — Foundational antibiotic
6. **IV Fluids** — Hydration/Shock/Blood Loss
7. **Heparin** — Anticoagulant
8. **Insulin** — Diabetes Management
9. **Morphine** — Pain Management
10. **Vaccines** — Immunization

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│           FRONTEND (React + TypeScript)                  │
│   Dashboard | Drugs | Shortages | Suppliers | Alerts    │
│                 (Real-time Updates)                     │
└──────────────────────┬──────────────────────────────────┘
                       │
          Supabase (PostgreSQL + Realtime)
                       │
┌──────────────────────▼──────────────────────────────────┐
│              BACKEND SERVER (server.py)                  │
│                                                          │
│  [Continuous Pipeline Loop]                              │
│  Phase 1: Agent 0 (Inventory) + Agent 1 (FDA)            │
│  Phase 2: Agent 2 (News - Brave MCP)                     │
│  Phase 3: Overseer (Decision Synthesizer)                │
│                                                          │
│  [Order Agent]                               │
│  Agent 4: Pricing Analysis & Order Generation            │
│           (Triggered via API / User Action)              │
└─────────────────────────────────────────────────────────┘
```

The system requires `server.py` to be running. This file manages:
1.  **The Continuous Pipeline**: Runs on a schedule (e.g., every 60 mins) to check FDA data, news, and inventory.
2.  **The API**: Exposes endpoints for the frontend to trigger specific agents (like the Order Agent) on demand, independent of the main pipeline.

### Agents
-   **Agent 0 (Inventory)**: Monitors Inventory, predicts usage, plans around surgeries, and ralculates burn rates.
-   **Agent 1 (FDA)**: Monitors FDA shortage database.
-   **Agent 2 (News)**: Uses web Search to find supply chain disruption news and potential shortages.
-   **Overseer**: Synthesizes data to create alerts.
-   **Agent 3 (Substitutes)**: Finds valid clinical substitutes dynamically.
-   **Agent 4 (Orders)**: Analyze pricing and availability to build orders.

---

## Quick Start

### Prerequisites
-   **Python 3.11+**
-   **Node.js 18+**
-   **Supabase** project
-   **LLM API Keys** (Dedalus/OpenAI etc.)

### 1. Database Setup
1.  Create a Supabase project.
2.  Run `db/schema.sql` in the SQL Editor to create tables.
3.  Run `db/seed_data.sql` to populate initial example data.

### 2. Backend
```bash
# Install dependencies
pip install -r requirements.txt

# Setup .env
# Ensure you have SUPABASE_URL, ANTHROPIC_API_KEY/DEDALUS_KEYS, etc.

# Run the server 
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

-   **Manual Drug Entry**: Allow users to manually add new drugs to the monitoring list via the UI.
-   **Database Integration**: Connect directly to existing hospital inventory databases instead of using the standalone database.

