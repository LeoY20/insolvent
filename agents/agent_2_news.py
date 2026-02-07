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

def fetch_news_articles_batched() -> List[Dict[str, Any]]:
    """
    Fetches news articles using batched queries to minimize API calls.
    Combines monitored drugs into a single query.
    """
    if not NEWS_API_KEY or 'your_' in NEWS_API_KEY:
        print("WARNING: NewsAPI key is not configured. Skipping news fetch.")
        return []

    articles = []
    seen_urls = set()
    from_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    # Batch drugs into a single OR query
    # Example: ("Epinephrine" OR "Oxygen" OR "Propofol" ...) AND (shortage OR supply OR recall)
    drugs_query = " OR ".join([f'"{name}"' for name in MONITORED_DRUG_NAMES])
    
    queries = [
        f'({drugs_query}) AND (shortage OR supply OR manufacturing OR recall)',
        '"pharmaceutical supply chain disruption"',
        '"drug shortage hospital"'
    ]

    for q in queries:
        params = {
            'q': q,
            'apiKey': NEWS_API_KEY,
            'language': 'en',
            'sortBy': 'relevancy',
            'pageSize': 20, # Fetch more per query since we batched
            'from': from_date
        }
        try:
            print(f"  Querying NewsAPI for: {q[:50]}...")
            response = requests.get(NEWS_API_URL, params=params, timeout=15)
            if response.status_code == 200:
                new_articles = response.json().get('articles', [])
                for article in new_articles:
                    url = article.get('url')
                    if url and url not in seen_urls:
                        articles.append(article)
                        seen_urls.add(url)
            else:
                print(f"  WARNING: NewsAPI query failed with status {response.status_code}")
        except requests.RequestException as e:
            print(f"  ERROR: NewsAPI request failed: {e}")
            
    print(f"✓ Fetched {len(articles)} unique articles from NewsAPI.")
    return articles

def build_system_prompt() -> str:
    """Builds the system prompt for Agent 2."""
    drug_ranking_info = "\n".join([f"- Rank {d['rank']}: {d['name']}" for d in MONITORED_DRUGS])
    
    return f"""You are an expert pharmaceutical supply chain analyst. Your task is to analyze news articles for early warning signals of drug shortages.

The hospital monitors these critical drugs:
{drug_ranking_info}

You must analyze the provided articles and identify risk signals. For each signal, determine:
- The specific monitored drug affected (must match one of the names above).
- The sentiment: POSITIVE, NEUTRAL, NEGATIVE, or CRITICAL.
- The supply chain impact: NONE, LOW, MEDIUM, HIGH, or CRITICAL.
- A confidence score (0.0 to 1.0).
- Your reasoning in a brief sentence.

Look for signals like: plant shutdowns, recalls, raw material shortages, or regulatory issues.
"""

def generate_fallback_analysis(articles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generates a simple, keyword-based analysis if the LLM call fails."""
    print("WARNING: LLM call failed or is mocked. Generating a fallback analysis.")
    risk_signals = []
    keywords = {'shortage', 'recall', 'disruption', 'shutdown', 'fda warning'}

    for article in articles:
        text_to_search = (article.get('title', '') + (article.get('description') or '')).lower()
        found_keywords = {kw for kw in keywords if kw in text_to_search}

        if found_keywords:
            affected_drug = "Unknown"
            for drug_name in MONITORED_DRUG_NAMES:
                if drug_name.lower() in text_to_search:
                    affected_drug = drug_name
                    break
            
            if affected_drug != "Unknown":
                risk_signals.append({
                    "drug_name": affected_drug,
                    "headline": article.get('title'),
                    "source": article.get('source', {}).get('name'),
                    "url": article.get('url'),
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
        # 1. Fetch news (batched)
        articles = fetch_news_articles_batched()
        if not articles:
            log_agent_output(AGENT_NAME, run_id, {"articles_analyzed": 0}, "No news articles found.")
            return

        # 2. Call LLM
        system_prompt = build_system_prompt()
        prompt_articles = [{
            "title": a.get("title"),
            "description": a.get("description"),
            "source": a.get("source", {}).get("name"),
            "url": a.get("url"),
        } for a in articles[:25]] 
        user_prompt = json.dumps(prompt_articles, default=str)
        
        llm_analysis = call_dedalus(system_prompt, user_prompt, API_KEY_INDEX, EXPECTED_JSON_SCHEMA)
        
        analysis_payload = llm_analysis or generate_fallback_analysis(articles)

        # 3. Process Results (Upsert logic for shortages)
        if supabase and 'risk_signals' in analysis_payload:
            # Fetch existing news-inferred shortages to avoid duplicates
            existing_news_shortages = supabase.table('shortages').select('*').eq('type', 'NEWS_INFERRED').eq('resolved', False).execute().data or []
            
            processed_count = 0
            for signal in analysis_payload['risk_signals']:
                drug_name = signal.get('drug_name')
                if not drug_name or drug_name == "Unknown": continue
                
                is_high_risk = signal.get('supply_chain_impact') in ['HIGH', 'CRITICAL'] and signal.get('confidence', 0.0) >= 0.7
                if not is_high_risk: continue

                # Manual Upsert Pattern
                existing_record = next((s for s in existing_news_shortages if s['drug_name'] == drug_name), None)
                
                record_data = {
                    'drug_name': drug_name,
                    'type': 'NEWS_INFERRED',
                    'source': signal.get('source', 'News Media'),
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
            
            print(f"✓ Processed {processed_count} high-confidence news shortage signals.")

        # 4. Log final output
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
