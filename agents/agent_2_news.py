import json
import asyncio
import os
from typing import Dict, Any, List
from datetime import datetime, timedelta
from uuid import UUID
import traceback

from dedalus_labs import AsyncDedalus, DedalusRunner

from agents.shared import (
    supabase,
    call_dedalus,
    log_agent_output,
    get_drugs_inventory,
    get_unresolved_shortages,
    MONITORED_DRUGS,
    MONITORED_DRUG_NAMES,
    HOSPITAL_LOCATION,
    DEDALUS_API_KEYS
)

AGENT_NAME = "agent_2"
API_KEY_INDEX = 1
NEWS_TARGET_ARTICLES = 6
NEWS_MAX_ROUNDS = 2
NEWS_MAX_TOTAL = 20
MAX_LLM_QUERIES = 3

# The JSON schema Agent 2 expects the LLM to return
EXPECTED_JSON_SCHEMA = {
    "articles_analyzed": 0,
    "risk_signals": [
        {
            "drug_name": "string (must match a monitored drug exactly)",
            "headline": "string",
            "source": "string",
            "url": "string (valid URL to the article)",
            "published_date": "YYYY-MM-DD (prefer last 30 days; allow older if long-term shortage still only up to our max days)",
            "sentiment": "POSITIVE | NEUTRAL | NEGATIVE | CRITICAL",
            "supply_chain_impact": "NONE | LOW | MEDIUM | HIGH | CRITICAL",
            "confidence": 0.0,
            "reasoning": "string explaining why this is a credible, recent signal"
        }
    ],
    "emerging_risks": [
        {
            "description": "string",
            "affected_drugs": ["list"],
            "risk_level": "LOW | MEDIUM | HIGH",
            "time_horizon": "string",
            "source_url": "string (URL if available)"
        }
    ],
    "summary": "string"
}


async def fetch_news_via_web_agent() -> List[Dict[str, Any]]:
    """
    Uses Dedalus web search agent with MCP servers to find drug shortage news.
    Returns a list of article-like dictionaries.
    """
    api_key = DEDALUS_API_KEYS[API_KEY_INDEX]
    if not api_key or 'your_' in api_key:
        print("  WARNING: Dedalus API key not configured. Skipping web search.")
        return []

    # Build the search query focusing on drug shortages with STRONG recency emphasis
    drug_list = ", ".join(MONITORED_DRUG_NAMES[:5])  # Top 5 critical drugs

    # Get current date for recency filtering
    today = datetime.now()
    recent_days = 30
    max_days = 365
    recent_start = (today - timedelta(days=recent_days)).strftime('%Y-%m-%d')
    max_start = (today - timedelta(days=max_days)).strftime('%Y-%m-%d')
    today_str = today.strftime('%Y-%m-%d')

    def build_search_prompt(query_hint: str | None = None) -> str:
        focus_line = f"Focus on this query: {query_hint}" if query_hint else "Use your best judgment to find relevant US/local articles."
        return f"""Search for RECENT news (prefer last {recent_days} days, between {recent_start} and {today_str}) about pharmaceutical drug shortages.
If necessary, you may include older articles (as far back as {max_start}) ONLY if they clearly describe long-term or upcoming shortages.

CRITICAL REQUIREMENTS:
- STRONGLY prefer articles published in the last {recent_days} days
- You may include older articles up to {max_days} days old ONLY if they indicate long-term or future shortages
- Articles older than {max_days} must NOT be included
- If you cannot find recent or clearly long-term actionable articles, return an empty array
- Prefer U.S. or local relevance. Avoid non‑U.S. shortages unless clearly relevant to U.S. supply.
{focus_line}

Search for:
1. Current drug shortage alerts affecting: {drug_list}
2. Recent FDA drug shortage announcements
3. Active manufacturing disruptions or plant issues
4. Current supply chain problems affecting pharmaceutical distribution

For each relevant article found, extract:
- The headline/title
- The source name
- The URL
- The publication date (YYYY-MM-DD format)
- A brief description
- Which specific monitored drugs are mentioned (if any from: {drug_list})

Return articles (prefer recent) as a JSON array:
[
  {{
    "title": "Article headline",
    "source": "Source name",
    "url": "https://...",
    "published_date": "YYYY-MM-DD",
    "description": "Brief summary",
    "drugs_mentioned": ["Drug1", "Drug2"]
  }}
]

If no relevant articles are found, return an empty array: []
Quality over quantity - only include genuinely relevant articles with clear supply-impact signals."""
    def parse_articles(output_text: str) -> List[Dict[str, Any]]:
        articles = []
        try:
            if "```json" in output_text:
                import re
                match = re.search(r"```json\s*([\s\S]*?)\s*```", output_text)
                if match:
                    articles = json.loads(match.group(1))
            elif output_text.strip().startswith("["):
                articles = json.loads(output_text)
            else:
                import re
                match = re.search(r"\[[\s\S]*\]", output_text)
                if match:
                    articles = json.loads(match.group(0))
        except json.JSONDecodeError:
            articles = []
        return articles

    def generate_followup_queries(found_articles: List[Dict[str, Any]]) -> List[str]:
        system_prompt = """Generate 1-3 concise News search queries focused on U.S. drug shortages.
Constraints:
- Must be U.S./FDA focused.
- Prefer monitored drugs and manufacturing/supply disruptions.
- Avoid non‑U.S. regions unless clearly tied to U.S. supply.
Return JSON: {\"queries\": [\"...\"]}"""

        user_prompt = json.dumps({
            "hospital_location": HOSPITAL_LOCATION,
            "monitored_drugs": MONITORED_DRUG_NAMES,
            "recent_titles": [a.get("title") for a in found_articles if a.get("title")][:10]
        }, default=str)

        result = call_dedalus(system_prompt, user_prompt, API_KEY_INDEX, {"queries": ["string"]})
        if not result or "queries" not in result:
            return []
        queries = [q.strip() for q in result.get("queries", []) if isinstance(q, str)]
        return queries[:MAX_LLM_QUERIES]

    try:
        print("  Searching web for drug shortage news via Dedalus agent...")

        client = AsyncDedalus(api_key=api_key)
        runner = DedalusRunner(client)

        collected: List[Dict[str, Any]] = []
        seen = set()
        queue: List[str | None] = [None]
        rounds = 0

        while queue and rounds < NEWS_MAX_ROUNDS:
            query_hint = queue.pop(0)
            rounds += 1
            prompt = build_search_prompt(query_hint)

            result = await runner.run(
                input=prompt,
                model="openai/gpt-4o-mini",
                mcp_servers=[
                    "tsion/exa",                 # Semantic search engine
                    "windsor/brave-search-mcp"   # Privacy-focused web search
                ]
            )

            output_text = result.final_output if hasattr(result, 'final_output') else str(result)
            articles = parse_articles(output_text)
            if not articles:
                print("  WARNING: Could not parse JSON from web agent response")

            filtered = filter_recent_articles(articles, max_days=max_days)
            filtered = filter_location_articles(filtered)

            for a in filtered:
                key = a.get("url") or a.get("title")
                if not key or key in seen:
                    continue
                seen.add(key)
                collected.append(a)

            if len(collected) >= NEWS_TARGET_ARTICLES:
                break

            if rounds < NEWS_MAX_ROUNDS:
                followups = generate_followup_queries(collected)
                if followups:
                    queue.extend(followups)

        collected = collected[:NEWS_MAX_TOTAL]
        print(f"  ✓ Found {len(collected)} articles via web search (multi-round)")
        return collected

    except Exception as e:
        print(f"  ERROR: Web search failed: {e}")
        return []


def fetch_news_articles() -> List[Dict[str, Any]]:
    """Wrapper to run async web search from sync context."""
    return asyncio.run(fetch_news_via_web_agent())


def build_system_prompt() -> str:
    """Builds the system prompt for Agent 2."""
    drug_ranking_info = "\n".join([f"- Rank {d['rank']}: {d['name']}" for d in MONITORED_DRUGS])

    today = datetime.now()
    recent_days = 30
    max_days = 365
    recent_start = (today - timedelta(days=recent_days)).strftime('%Y-%m-%d')

    return f"""You are an expert pharmaceutical supply chain analyst. Your task is to analyze news articles for early warning signals of drug shortages.

The hospital monitors these critical drugs:
{drug_ranking_info}

CRITICAL REQUIREMENTS FOR RISK SIGNALS:

1. **EXPLICIT DRUG MENTION (MANDATORY)**: The article MUST explicitly name the specific drug by name in its title or body.
   - CORRECT: Article title "FDA Reports Propofol Shortage" → create signal for Propofol only
   - WRONG: Article about "general drug shortages" → do NOT assign to any drug
   - WRONG: Article mentions "anesthetics" generally → do NOT assume it means Propofol

2. **ONE ARTICLE = ONE DRUG (STRICT)**: Each article should produce AT MOST one risk_signal.
   - Do NOT assign the same article URL to multiple drugs
   - If an article mentions multiple drugs explicitly, pick the most critical one only
   - Generic shortage news that doesn't name specific drugs = no signal

3. **RECENCY**: Strongly prefer articles published in the LAST {recent_days} DAYS (after {recent_start}).
   You may include older articles (up to {max_days} days) ONLY if they clearly indicate long-term or upcoming shortages.

4. **CREDIBILITY**: Only include signals from credible sources with working URLs.

5. **RELEVANCE**: The article must indicate an actual or imminent supply issue, not general industry news.

For each VALID signal, determine:
- drug_name: Must EXACTLY match one of the monitored drug names above AND must be EXPLICITLY named in the article
- published_date: The article's publication date (YYYY-MM-DD format)
- sentiment: POSITIVE, NEUTRAL, NEGATIVE, or CRITICAL
- supply_chain_impact: NONE, LOW, MEDIUM, HIGH, or CRITICAL
- confidence: 0.0 to 1.0 (lower if article is vague or source is uncertain)
- reasoning: Must include the exact quote or phrase from the article that mentions the drug

EXAMPLES:
- Article: "Epinephrine shortage hits hospitals nationwide" → Valid signal for Epinephrine
- Article: "FDA updates on drug shortage list" → NO SIGNAL (too generic, no specific drug named)
- Article: "Medical supply chain disruptions" → NO SIGNAL (no drug named)

If no articles explicitly name monitored drugs, return an empty risk_signals array. Quality over quantity.
"""


def generate_fallback_analysis(articles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generates a simple, keyword-based analysis if the LLM call fails."""
    print("  WARNING: LLM call failed. Generating fallback analysis.")
    risk_signals = []
    keywords = {'shortage', 'recall', 'disruption', 'shutdown', 'fda warning', 'supply'}

    for article in articles:
        text_to_search = (
            (article.get('title', '') or '') +
            ' ' +
            (article.get('description', '') or '')
        ).lower()

        found_keywords = {kw for kw in keywords if kw in text_to_search}

        if found_keywords:
            affected_drug = "Unknown"
            # Check drugs_mentioned field first
            drugs_mentioned = article.get('drugs_mentioned', [])
            if drugs_mentioned and isinstance(drugs_mentioned, list):
                for drug in drugs_mentioned:
                    if drug in MONITORED_DRUG_NAMES:
                        affected_drug = drug
                        break

            # Fall back to text search
            if affected_drug == "Unknown":
                for drug_name in MONITORED_DRUG_NAMES:
                    if drug_name.lower() in text_to_search:
                        affected_drug = drug_name
                        break

            if affected_drug != "Unknown":
                risk_signals.append({
                    "drug_name": affected_drug,
                    "headline": article.get('title', 'No title'),
                    "source": article.get('source', 'Unknown'),
                    "url": article.get('url', ''),
                    "sentiment": "NEGATIVE",
                    "supply_chain_impact": "MEDIUM",
                    "confidence": 0.6,
                    "reasoning": f"Fallback: Detected keywords: {', '.join(found_keywords)}."
                })

    return {
        "articles_analyzed": len(articles),
        "risk_signals": risk_signals,
        "emerging_risks": [],
        "summary": f"Fallback analysis found {len(risk_signals)} potential risk signals."
    }


def filter_recent_articles(articles: List[Dict[str, Any]], max_days: int = 365) -> List[Dict[str, Any]]:
    """Drop articles older than max_days or missing a parseable date."""
    cutoff = datetime.now() - timedelta(days=max_days)
    filtered = []
    for a in articles:
        raw_date = a.get("published_date") or a.get("publishedAt") or a.get("date")
        if not raw_date:
            continue
        try:
            # Accept YYYY-MM-DD or full ISO timestamps
            date_str = str(raw_date)[:10]
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except Exception:
            continue
        if dt >= cutoff:
            filtered.append(a)
    return filtered


def filter_location_articles(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Prefer US/local relevance; drop clearly non‑US articles."""
    us_keywords = ["united states", "u.s.", "usa", "fda", "cdc"]
    # Basic location hints from hospital location (city/state)
    location_hint = (HOSPITAL_LOCATION or "").lower()
    non_us_markers = [
        "india", "china", "europe", "uk", "england", "australia", "canada",
        "germany", "france", "spain", "italy", "brazil", "mexico", "japan"
    ]

    def is_us_relevant(text: str, url: str) -> bool:
        t = text.lower()
        u = (url or "").lower()
        has_us = any(k in t for k in us_keywords) or any(k in u for k in us_keywords)
        if location_hint:
            city = location_hint.split(",")[0].strip()
            if city:
                has_us = has_us or (city in t)
        has_non_us = any(k in t for k in non_us_markers) or any(k in u for k in non_us_markers)
        return has_us and not (has_non_us and not has_us)

    filtered = []
    for a in articles:
        text = f"{a.get('title','')} {a.get('description','')} {a.get('source','')}"
        if is_us_relevant(text, a.get("url", "")):
            filtered.append(a)
    return filtered


def deduplicate_signals_by_url(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure each URL only appears once in risk_signals.
    If the same URL is assigned to multiple drugs, keep only the first one
    (typically the most critical drug based on LLM ordering).
    This prevents generic articles from being cited for multiple drugs.
    """
    signals = payload.get("risk_signals", []) if isinstance(payload, dict) else []
    seen_urls: set = set()
    filtered = []

    for s in signals:
        url = s.get("url")
        if not url:
            # No URL - keep the signal but it won't be deduplicated
            filtered.append(s)
            continue

        # Normalize URL for comparison
        normalized_url = url.strip().lower().rstrip('/')

        if normalized_url in seen_urls:
            drug_name = s.get("drug_name", "Unknown")
            print(f"  Skipping duplicate URL for {drug_name}: {url[:60]}...")
            continue

        seen_urls.add(normalized_url)
        filtered.append(s)

    if isinstance(payload, dict):
        original_count = len(signals)
        payload["risk_signals"] = filtered
        if original_count != len(filtered):
            print(f"  Deduplicated: {original_count} → {len(filtered)} signals (removed {original_count - len(filtered)} duplicates)")

    return payload


def filter_recent_signals(payload: Dict[str, Any], max_days: int = 365) -> Dict[str, Any]:
    """Drop risk_signals older than max_days or missing a parseable date."""
    cutoff = datetime.now() - timedelta(days=max_days)
    signals = payload.get("risk_signals", []) if isinstance(payload, dict) else []
    filtered = []
    for s in signals:
        raw_date = s.get("published_date") or s.get("publishedAt") or s.get("date")
        if not raw_date:
            continue
        try:
            date_str = str(raw_date)[:10]
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except Exception:
            continue
        if dt >= cutoff:
            filtered.append(s)
    if isinstance(payload, dict):
        payload["risk_signals"] = filtered
    return payload


def run(run_id: UUID):
    """Executes the full workflow for Agent 2."""
    print(f"\n----- Running Agent 2: News Analyzer for run_id: {run_id} -----")

    try:
        # 1. Fetch news via web agent
        articles = fetch_news_articles()
        if not articles:
            print("  No news articles found.")
            log_agent_output(AGENT_NAME, run_id, {"articles_analyzed": 0}, "No news articles found.")
            print("----- Agent 2 finished -----")
            return

        # 2. Call LLM for analysis
        system_prompt = build_system_prompt()
        prompt_articles = [{
            "title": a.get("title"),
            "description": a.get("description"),
            "source": a.get("source"),
            "url": a.get("url"),
            "drugs_mentioned": a.get("drugs_mentioned", []),
            "published_date": a.get("published_date") or a.get("publishedAt") or a.get("date")
        } for a in articles[:25]]

        user_prompt = json.dumps(prompt_articles, default=str)

        llm_analysis = call_dedalus(system_prompt, user_prompt, API_KEY_INDEX, EXPECTED_JSON_SCHEMA)

        analysis_payload = llm_analysis or generate_fallback_analysis(articles)
        analysis_payload = filter_recent_signals(analysis_payload, max_days=365)
        analysis_payload = deduplicate_signals_by_url(analysis_payload)

        # 3. Process Results (Upsert logic for shortages)
        if supabase and 'risk_signals' in analysis_payload:
            existing_news_shortages = supabase.table('shortages').select('*').eq('type', 'NEWS_INFERRED').eq('resolved', False).execute().data or []

            processed_count = 0
            for signal in analysis_payload.get('risk_signals', []):
                drug_name = signal.get('drug_name')
                if not drug_name or drug_name == "Unknown":
                    continue

                # Drop non‑US/non‑local signals (extra safety)
                if not filter_location_articles([{
                    "title": signal.get("headline"),
                    "description": signal.get("reasoning"),
                    "source": signal.get("source"),
                    "url": signal.get("url")
                }]):
                    continue

                is_high_risk = (
                    signal.get('supply_chain_impact') in ['HIGH', 'CRITICAL'] and
                    signal.get('confidence', 0.0) >= 0.7
                )
                if not is_high_risk:
                    continue

                existing_record = next(
                    (s for s in existing_news_shortages if s['drug_name'] == drug_name),
                    None
                )

                reported_date = signal.get('published_date') or datetime.now().date().isoformat()
                record_data = {
                    'drug_name': drug_name,
                    'type': 'NEWS_INFERRED',
                    'source': signal.get('source', 'Web Search'),
                    'impact_severity': signal.get('supply_chain_impact'),
                    'description': f"{signal.get('headline')} - {signal.get('reasoning')}",
                    'reported_date': reported_date,
                    'resolved': False,
                    'source_url': signal.get('url')
                }

                if existing_record:
                    print(f"  Updating existing news signal for {drug_name}...")
                    supabase.table('shortages').update(record_data).eq('id', existing_record['id']).execute()
                else:
                    print(f"  Inserting new news signal for {drug_name}...")
                    supabase.table('shortages').insert(record_data).execute()

                processed_count += 1

            if processed_count > 0:
                print(f"  ✓ Processed {processed_count} high-confidence news shortage signals.")
            else:
                print("  No high-confidence shortage signals found in news.")

        # 4. Log final output
        analysis_payload['articles_analyzed'] = len(articles)
        summary = analysis_payload.get('summary', 'News analysis completed.')
        log_agent_output(AGENT_NAME, run_id, analysis_payload, summary)

    except Exception as e:
        error_summary = f"Agent 2 failed: {e}"
        print(f"  ERROR: {error_summary}")
        traceback.print_exc()
        log_agent_output(AGENT_NAME, run_id, {"error": str(e), "trace": traceback.format_exc()}, error_summary)

    finally:
        print("----- Agent 2 finished -----")


if __name__ == '__main__':
    test_run_id = UUID('00000000-0000-0000-0000-000000000003')
    run(test_run_id)
