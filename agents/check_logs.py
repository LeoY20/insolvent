
from agents.shared import get_agent_logs
from uuid import UUID
import json

# The run_id we just used
run_id = UUID('00000000-0000-0000-0000-000000000003')
logs = get_agent_logs(run_id, 'agent_2')

if logs:
    print(f"Found {len(logs)} logs.")
    for log in logs:
        payload = log.get('payload', {})
        print("Summary:", payload.get('summary'))
        print("Articles Analyzed:", payload.get('articles_analyzed'))
        print("Risk Signals Found:", len(payload.get('risk_signals', [])))
        for signal in payload.get('risk_signals', []):
            print(f" - {signal.get('headline')} ({signal.get('confidence')}): {signal.get('reasoning')}")
else:
    print("No logs found for this run ID.")
