# Unimplemented Features in PharmaSentinel

This document outlines the features that are currently unimplemented or incomplete in the PharmaSentinel project, based on a comparison with the `project_instructions.md` specification and the existing codebase. This is intended to guide further development by other agents.

---

## Summary

The project has a robust structural foundation, including a complete file structure, a fully defined database schema, and all specified dependencies correctly configured. However, the core business logic for both the backend agents and the frontend components is largely missing. The project is in an initial setup phase where boilerplate code is complete, but the functional implementation remains to be done.

---

## Detailed Breakdown of Unimplemented/Incomplete Features

### 1. Backend Agent Logic (Core Business Logic)

All agent files (`agents/agent_0_inventory.py`, `agents/agent_1_fda.py`, `agents/agent_2_news.py`, `agents/agent_3_substitutes.py`, `agents/agent_4_orders.py`, `agents/overseer.py`) are present but essentially empty placeholders. They currently lack the functional code necessary to perform their specified tasks.

**Specific Missing Implementations:**

*   **Agent 0 (Inventory Analyzer & Burn Rate Calculator):**
    *   Fetching `drugs` and `surgery_schedule` data from Supabase.
    *   Calculating burn rates, predicted usage rates, and identifying at-risk surgeries.
    *   Interacting with the Dedalus LLM to get analysis and decisions.
    *   Updating the `drugs` table with predicted rates.
    *   Logging analysis results to `agent_logs`.
*   **Agent 1 (FDA Drug Shortage Monitor):**
    *   Querying the openFDA API for drug shortage data.
    *   Comparing FDA data with existing `shortages` records.
    *   Interacting with the Dedalus LLM for analysis of shortages, impact, and severity.
    *   Inserting new shortage records into the `shortages` table.
    *   Logging findings to `agent_logs`.
*   **Agent 2 (News & Supply Chain Sentiment Analyzer):**
    *   Building search queries for the NewsAPI.
    *   Fetching and deduplicating articles from NewsAPI.org.
    *   Interacting with the Dedalus LLM to analyze article sentiment, supply chain impact, and emerging risks.
    *   Inserting high-confidence risk signals into the `shortages` table.
    *   Logging analysis to `agent_logs`.
*   **Overseer Agent (Decision Synthesizer):**
    *   Reading outputs from Agents 0, 1, and 2 from `agent_logs`.
    *   Fetching current `drugs` inventory and unresolved `shortages`.
    *   Interacting with the Dedalus LLM to synthesize intelligence and make decisions based on the defined decision framework.
    *   Writing final `alerts` to the `alerts` table.
    *   Identifying drugs needing substitutes or orders for conditional agent invocation.
*   **Agent 3 (Drug Substitute Finder):**
    *   Accessing hard-coded substitution mappings.
    *   Checking `drugs` table for in-stock substitutes.
    *   Interacting with the Dedalus LLM to rank substitutes, note conversions, and identify contraindications.
    *   Upserting results into the `substitutes` table.
    *   Logging findings to `agent_logs`.
*   **Agent 4 (Order & Supplier Manager):**
    *   Accessing hard-coded major supplier list and `suppliers` table data.
    *   Fetching pricing and criticality from the `drugs` table.
    *   Interacting with the Dedalus LLM to select optimal suppliers and generate order recommendations based on urgency and criticality.
    *   Writing order-related alerts to the `alerts` table.
    *   Logging analysis to `agent_logs`.

### 2. Pipeline Orchestration

The `agents/pipeline.py` file is currently a placeholder.

**Specific Missing Implementations:**

*   **`pipeline.py` Logic:** The core orchestration logic, including generating a `run_id`, executing Agents 0, 1, and 2 in parallel (e.g., using `asyncio.gather`), running the Overseer synchronously, and conditionally invoking Agents 3 and 4, is not implemented.
*   **`main.py` Entry Point:** The `main.py` file is empty and does not contain the cron loop or any mechanism to trigger the pipeline execution at regular intervals.

### 3. Shared Agent Infrastructure

The `agents/shared.py` file is currently empty.

**Specific Missing Implementations:**

*   **Supabase Client Initialization:** Code to initialize the Supabase client (using the service role key for backend agents).
*   **Dedalus LLM Wrapper:** A utility function to interact with the Dedalus LLM, handling system/user prompts, API key distribution, and JSON response parsing.
*   **`MONITORED_DRUGS` Constant:** The definition of the 10 critical drugs with their names, types, and criticality rankings.
*   **`log_agent_output()` Function:** A utility to insert structured logs into the `agent_logs` table.
*   **`get_drugs_inventory()` and `get_surgery_schedule()` Functions:** Utilities to fetch relevant data from the database.

### 4. Frontend UI & Logic

The React components in `frontend/src/pages/` are boilerplate code, and the `frontend/src/lib/supabase.ts` is a placeholder.

**Specific Missing Implementations:**

*   **Page Content:** All pages (`Dashboard.tsx`, `DrugsPage.tsx`, `ShortagesPage.tsx`, `SuppliersPage.tsx`, `AlertsPage.tsx`) need to be populated with the actual UI elements specified:
    *   **Dashboard:** Summary cards (Critical Alerts, Urgent Alerts, Low Stock Drugs, Active Shortages), active alerts section with "Acknowledge" functionality, and an initial drug inventory table.
    *   **Drugs Page:** Detailed drug table, Recharts line charts for usage/stock projection, expandable rows for substitutes, shortages, and suppliers.
    *   **Shortages Page:** Table of shortage records with filtering by resolved status and severity.
    *   **Suppliers Page:** Table of suppliers with filtering by drug name and type.
    *   **Alerts Page:** Full alert history table with various filters.
*   **Supabase Client & Types:** The `frontend/src/lib/supabase.ts` needs the `createClient` call and TypeScript interfaces for all database tables.
*   **Data Fetching & State Management:** Logic to fetch data from Supabase for display on all pages, including handling loading states and errors.
*   **Realtime Subscriptions:** Implementation of Supabase Realtime subscriptions for the `alerts` and `drugs` tables to enable live updates on the frontend.
*   **Styling:** Application of Tailwind CSS utility classes, specific color schemes, and `lucide-react` icons as per the design specifications.
*   **Routing:** While `App.tsx` has basic routing setup, it needs to correctly render the implemented page components.

---
**Note:** API keys are acknowledged as not being in place, as per user instructions to ignore this fact during this analysis.
