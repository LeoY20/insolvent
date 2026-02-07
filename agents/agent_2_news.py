import json
import asyncio
import os
from typing import Dict, Any, List
from datetime import datetime
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

# The JSON schema Agent 2 expects the LLM to return
EXPECTED_JSON_SCHEMA = {
    "articles_analyzed": 0,
    "risk_signals": [
        {
            "drug_name": "string (must match a monitored drug exactly)",
            "headline": "string",
            "source": "string",
            "url": "string (valid URL to the article)",
            "published_date": "YYYY-MM-DD (prefer last 30 days; allow older if long-term shortage)",
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
    from datetime import datetime, timedelta
    today = datetime.now()
    recent_days = 30
    max_days = 180
    recent_start = (today - timedelta(days=recent_days)).strftime('%Y-%m-%d')
    max_start = (today - timedelta(days=max_days)).strftime('%Y-%m-%d')
    today_str = today.strftime('%Y-%m-%d')

    search_prompt = f"""Search for RECENT news (prefer last {recent_days} days, between {recent_start} and {today_str}) about pharmaceutical drug shortages.
If necessary, you may include older articles (as far back as {max_start}) ONLY if they clearly describe long-term or upcoming shortages.

CRITICAL REQUIREMENTS:
- STRONGLY prefer articles published in the last {recent_days} days
- You may include older articles up to {max_days} days old ONLY if they indicate long-term or future shortages
- If you cannot find recent or clearly long-term actionable articles, return an empty array

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

    try:
        print("  Searching web for drug shortage news via Dedalus agent...")

        client = AsyncDedalus(api_key=api_key)
        runner = DedalusRunner(client)

        result = await runner.run(
            input=search_prompt,
            model="openai/gpt-4o-mini",
            mcp_servers=[
                "tsion/exa",                 # Semantic search engine
                "windsor/brave-search-mcp"   # Privacy-focused web search
            ]
        )

        # Parse the agent's output
        output_text = result.final_output if hasattr(result, 'final_output') else str(result)

        # Try to extract JSON from the response
        articles = []
        try:
            # Look for JSON array in the output
            if "```json" in output_text:
                import re
                match = re.search(r"```json\s*([\s\S]*?)\s*```", output_text)
                if match:
                    articles = json.loads(match.group(1))
            elif output_text.strip().startswith("["):
                articles = json.loads(output_text)
            else:
                # Try to find any JSON array
                import re
                match = re.search(r"\[[\s\S]*\]", output_text)
                if match:
                    articles = json.loads(match.group(0))
        except json.JSONDecodeError:
            print(f"  WARNING: Could not parse JSON from web agent response")
            # Create a single article from the text response
            articles = [{
                "title": "Web Search Results",
                "source": "Dedalus Web Agent",
                "url": "",
                "description": output_text[:1000] if output_text else "No results"
            }]

        print(f"  ✓ Found {len(articles)} articles via web search")
        return articles

    except Exception as e:
        print(f"  ERROR: Web search failed: {e}")
        return []


def fetch_news_articles() -> List[Dict[str, Any]]:
    """Wrapper to run async web search from sync context."""
    return asyncio.run(fetch_news_via_web_agent())


def build_system_prompt() -> str:
    """Builds the system prompt for Agent 2."""
    drug_ranking_info = "\n".join([f"- Rank {d['rank']}: {d['name']}" for d in MONITORED_DRUGS])

    from datetime import datetime, timedelta
    today = datetime.now()
    recent_days = 30
    max_days = 180
    recent_start = (today - timedelta(days=recent_days)).strftime('%Y-%m-%d')

    return f"""You are an expert pharmaceutical supply chain analyst. Your task is to analyze news articles for early warning signals of drug shortages.

The hospital monitors these critical drugs:
{drug_ranking_info}

CRITICAL REQUIREMENTS FOR RISK SIGNALS:
1. **RECENCY**: Strongly prefer articles published in the LAST {recent_days} DAYS (after {recent_start}). 
   You may include older articles (up to {max_days} days) ONLY if they clearly indicate long-term or upcoming shortages.
2. **SPECIFICITY**: The article must specifically mention one of the monitored drugs listed above.
3. **CREDIBILITY**: Only include signals from credible sources with working URLs.
4. **RELEVANCE**: The article must indicate an actual or imminent supply issue, not general industry news.

For each VALID signal, determine:
- drug_name: Must EXACTLY match one of the monitored drug names above
- published_date: The article's publication date (YYYY-MM-DD format)
- sentiment: POSITIVE, NEUTRAL, NEGATIVE, or CRITICAL
- supply_chain_impact: NONE, LOW, MEDIUM, HIGH, or CRITICAL
- confidence: 0.0 to 1.0 (lower if article is vague or source is uncertain)
- reasoning: Brief explanation of why this is a credible, recent signal

IMPORTANT: If no articles meet the recency or long-term relevance criteria, return an empty risk_signals array.
Quality over quantity - only include genuinely actionable intelligence.
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
            "drugs_mentioned": a.get("drugs_mentioned", [])
        } for a in articles[:25]]

        user_prompt = json.dumps(prompt_articles, default=str)

        llm_analysis = call_dedalus(system_prompt, user_prompt, API_KEY_INDEX, EXPECTED_JSON_SCHEMA)

        analysis_payload = llm_analysis or generate_fallback_analysis(articles)

        # 3. Process Results (Upsert logic for shortages)
        if supabase and 'risk_signals' in analysis_payload:
            existing_news_shortages = supabase.table('shortages').select('*').eq('type', 'NEWS_INFERRED').eq('resolved', False).execute().data or []

            processed_count = 0
            for signal in analysis_payload.get('risk_signals', []):
                drug_name = signal.get('drug_name')
                if not drug_name or drug_name == "Unknown":
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

                record_data = {
                    'drug_name': drug_name,
                    'type': 'NEWS_INFERRED',
                    'source': signal.get('source', 'Web Search'),
                    'impact_severity': signal.get('supply_chain_impact'),
                    'description': f"{signal.get('headline')} - {signal.get('reasoning')}",
                    'reported_date': datetime.now().date().isoformat(),
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
