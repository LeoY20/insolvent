"""
Agent 2 — News & Supply Chain Sentiment Analyzer

Responsibilities:
- Queries NewsAPI for drug-related and pharma supply chain articles
- Uses LLM to analyze sentiment and supply chain impact
- Inserts high-confidence shortage signals into shortages table
- Logs analysis to agent_logs

API Key: DEDALUS_API_KEY_2 (index 1)
"""

import json
import requests
from typing import Dict, Any, List
from datetime import datetime, timedelta
from uuid import UUID
import traceback

from agents.shared import (
    supabase,
    call_dedalus,
    log_agent_output,
    MONITORED_DRUGS,
    MONITORED_DRUG_NAMES,
    NEWS_API_KEY
)

AGENT_NAME = "agent_2"
API_KEY_INDEX = 1
NEWS_API_URL = "https://newsapi.org/v2/everything"

# The JSON schema Agent 2 expects the LLM to return
EXPECTED_JSON_SCHEMA = {
    "articles_analyzed": 0,
    "risk_signals": [
        {
            "drug_name": "string",
            "headline": "string",
            "source": "string",
            "url": "string",
            "sentiment": "POSITIVE | NEUTRAL | NEGATIVE | CRITICAL",
            "supply_chain_impact": "NONE | LOW | MEDIUM | HIGH | CRITICAL",
            "confidence": 0.0,
            "reasoning": "string"
        }
    ],
    "emerging_risks": [
        {
            "description": "string",
            "affected_drugs": ["list"],
            "risk_level": "LOW | MEDIUM | HIGH",
            "time_horizon": "string"
        }
    ],
    "summary": "string"
}

def fetch_news_articles() -> List[Dict[str, Any]]:
    """Fetches and deduplicates news articles from NewsAPI."""
    if not NEWS_API_KEY or 'your_' in NEWS_API_KEY:
        print("WARNING: NewsAPI key is not configured. Skipping news fetch.")
        return []

    articles = []
    seen_urls = set()
    from_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    queries = [f'"{name}" AND (shortage OR supply OR recall)' for name in MONITORED_DRUG_NAMES]
    queries.extend(['"pharmaceutical supply chain disruption"', '"drug shortage hospital"'])

    for q in queries:
        params = {
            'q': q,
            'apiKey': NEWS_API_KEY,
            'language': 'en',
            'sortBy': 'relevancy',
            'pageSize': 5,
            'from': from_date
        }
        try:
            response = requests.get(NEWS_API_URL, params=params, timeout=15)
            if response.status_code == 200:
                for article in response.json().get('articles', []):
                    url = article.get('url')
                    if url and url not in seen_urls:
                        articles.append(article)
                        seen_urls.add(url)
            else:
                print(f"WARNING: NewsAPI query for '{q}' failed with status {response.status_code}")
        except requests.RequestException as e:
            print(f"ERROR: NewsAPI request failed for query '{q}': {e}")
            
    print(f"Fetched {len(articles)} unique articles from NewsAPI.")
    return articles

def build_system_prompt() -> str:
    """Builds the system prompt for Agent 2."""
    drug_ranking_info = "\n".join([f"- Rank {d['rank']}: {d['name']}" for d in MONITORED_DRUGS])
    
    return f"""You are an expert pharmaceutical supply chain analyst. Your task is to analyze news articles for early warning signals of drug shortages.

The hospital monitors these critical drugs:
{drug_ranking_info}

You must analyze the provided articles and identify risk signals. For each signal, determine:
- The specific monitored drug affected.
- The sentiment: POSITIVE (supply expanding), NEUTRAL, NEGATIVE (early warning), or CRITICAL (active disruption).
- The supply chain impact: NONE, LOW, MEDIUM, HIGH, or CRITICAL. A CRITICAL impact is an immediate threat to a rank 1-3 drug. A HIGH impact affects a rank 1-6 drug.
- A confidence score (0.0 to 1.0) for your analysis.
- Your reasoning in a brief sentence.

Look for signals like: plant shutdowns, recalls, raw material shortages, geopolitical events affecting pharma, or new regulations.
"""

def generate_fallback_analysis(articles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generates a simple, keyword-based analysis if the LLM call fails."""
    print("WARNING: LLM call failed or is mocked. Generating a fallback analysis.")
    risk_signals = []
    keywords = {'shortage', 'recall', 'disruption', 'shutdown', 'fda warning'}

    for article in articles:
        text_to_search = (article.get('title', '') + article.get('description', '')).lower()
        found_keywords = {kw for kw in keywords if kw in text_to_search}

        if found_keywords:
            # Simple logic: find which drug name is in the text
            affected_drug = "Unknown"
            for drug_name in MONITORED_DRUG_NAMES:
                if drug_name.lower() in text_to_search:
                    affected_drug = drug_name
                    break
            
            risk_signals.append({
                "drug_name": affected_drug,
                "headline": article.get('title'),
                "source": article.get('source', {}).get('name'),
                "url": article.get('url'),
                "sentiment": "NEGATIVE",
                "supply_chain_impact": "MEDIUM",
                "confidence": 0.5,
                "reasoning": f"Fallback analysis: Detected keywords: {', '.join(found_keywords)}."
            })
            
    return {
        "articles_analyzed": len(articles),
        "risk_signals": risk_signals,
        "emerging_risks": [],
        "summary": f"Fallback analysis using keywords found {len(risk_signals)} potential risk signals."
    }

def run(run_id: UUID):
    """Executes the full workflow for Agent 2."""
    print(f"\n----- Running Agent 2: News Analyzer for run_id: {run_id} -----")
    
    try:
        # 1. Fetch news
        articles = fetch_news_articles()
        if not articles:
            print("No articles found. Skipping further analysis.")
            log_agent_output(AGENT_NAME, run_id, {"articles_analyzed": 0}, "No news articles found.")
            return

        # 2. Prepare for LLM
        system_prompt = build_system_prompt()
        # Provide a subset of article data to the LLM to avoid large prompts
        prompt_articles = [{
            "title": a.get("title"),
            "description": a.get("description"),
            "source": a.get("source", {}).get("name"),
            "url": a.get("url"),
        } for a in articles[:20]] # Limit to 20 articles for the prompt
        user_prompt = json.dumps(prompt_articles, default=str)
        
        # 3. Call LLM, with fallback
        llm_analysis = call_dedalus(system_prompt, user_prompt, API_KEY_INDEX, EXPECTED_JSON_SCHEMA)
        
        analysis_payload = llm_analysis
        if not analysis_payload:
            analysis_payload = generate_fallback_analysis(articles)

        # 4. Process and insert high-confidence shortages
        if supabase and 'risk_signals' in analysis_payload:
            new_shortage_count = 0
            for signal in analysis_payload['risk_signals']:
                is_high_impact = signal.get('supply_chain_impact') in ['HIGH', 'CRITICAL']
                is_high_confidence = signal.get('confidence', 0.0) >= 0.7
                
                if is_high_impact and is_high_confidence:
                    supabase.table('shortages').insert({
                        'drug_name': signal.get('drug_name'),
                        'type': 'NEWS_INFERRED',
                        'source': signal.get('source', 'News Media'),
                        'impact_severity': signal.get('supply_chain_impact'),
                        'description': signal.get('reasoning') or signal.get('headline'),
                        'reported_date': datetime.now().date().isoformat(),
                        'resolved': False,
                        'source_url': signal.get('url')
                    }).execute()
                    new_shortage_count += 1
            
            if new_shortage_count > 0:
                print(f"Inserted {new_shortage_count} high-confidence shortage records from news.")
            else:
                print("No new high-confidence shortages found in news to insert.")

        # 5. Log final output
        analysis_payload['articles_analyzed'] = len(articles)
        summary = analysis_payload.get('summary', 'News analysis completed.')
        log_agent_output(AGENT_NAME, run_id, analysis_payload, summary)

    except Exception as e:
        error_summary = f"Agent 2 failed: {e}"
        print(f"ERROR: {error_summary}")
        traceback.print_exc()
        log_agent_output(AGENT_NAME, run_id, {"error": str(e), "trace": traceback.format_exc()}, error_summary)
    
    finally:
        print("----- Agent 2 finished -----")

if __name__ == '__main__':
    test_run_id = UUID('00000000-0000-0000-0000-000000000003')
    run(test_run_id)
