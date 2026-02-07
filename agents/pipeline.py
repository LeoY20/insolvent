"""
PharmaSentinel Pipeline Orchestrator

Coordinates the execution of all agents in the correct phases:

Phase 1 (Parallel):  Agent 0 (Inventory) + Agent 1 (FDA) + Agent 2 (News)
                     ↓
Phase 2 (Sequential): Overseer (Decision Synthesizer)
                     ↓
Phase 3 (Conditional): Agent 3 (Substitutes) if needed
                     ↓
Phase 4 (Conditional): Agent 4 (Orders) if needed

All agents write to agent_logs with the same run_id for correlation.
"""

import uuid
from uuid import UUID
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, Any

# Import all agents
from . import agent_0_inventory
from . import agent_1_fda
from . import agent_2_news
from . import overseer
from . import agent_3_substitutes
from . import agent_4_orders

def run_pipeline() -> Dict[str, Any]:
    """
    Execute the complete PharmaSentinel pipeline.

    Returns:
        Pipeline execution summary
    """
    run_id = uuid.uuid4()
    start_time = datetime.now()

    print("\n" + "="*80)
    print(f"PHARMASENTINEL PIPELINE EXECUTION")
    print(f"Run ID: {run_id}")
    print(f"Started: {start_time.isoformat()}")
    print("="*80 + "\n")

    results = {
        "run_id": str(run_id),
        "start_time": start_time.isoformat(),
        "phases": {},
        "errors": []
    }

    try:
        # ====================================================================
        # PHASE 1: Parallel execution of data collection agents
        # ====================================================================
        print(f"{'='*80}")
        print(f"PHASE 1: Data Collection (Parallel)")
        print(f"{'='*80}\n")

        phase1_start = datetime.now()
        phase1_results = run_phase_1_parallel(run_id)
        phase1_duration = (datetime.now() - phase1_start).total_seconds()

        results["phases"]["phase_1"] = {
            "duration_seconds": phase1_duration,
            "results": phase1_results
        }

        print(f"\n{'='*80}")
        print(f"PHASE 1 COMPLETED in {phase1_duration:.2f}s")
        print(f"{'='*80}\n")

        # ====================================================================
        # PHASE 2: Overseer decision synthesis
        # ====================================================================
        print(f"{'='*80}")
        print(f"PHASE 2: Decision Synthesis")
        print(f"{'='*80}\n")

        phase2_start = datetime.now()

        try:
            overseer_result = overseer.run(run_id)
            phase2_duration = (datetime.now() - phase2_start).total_seconds()

            results["phases"]["phase_2"] = {
                "duration_seconds": phase2_duration,
                "result": "success",
                "decisions_count": len(overseer_result.get('decisions', [])) if overseer_result else 0
            }

            print(f"\n{'='*80}")
            print(f"PHASE 2 COMPLETED in {phase2_duration:.2f}s")
            print(f"{'='*80}\n")

        except Exception as e:
            print(f"\n✗ PHASE 2 FAILED: {e}")
            results["errors"].append(f"Phase 2 (Overseer): {e}")
            results["phases"]["phase_2"] = {"result": "failed", "error": str(e)}
            # Cannot continue without Overseer
            raise

        if not overseer_result:
            raise ValueError("Overseer failed to return results, cannot proceed to conditional phases.")

        # ====================================================================
        # PHASE 3: Conditional - Agent 3 (Substitutes)
        # ====================================================================
        drugs_needing_substitutes = overseer_result.get('drugs_needing_substitutes', [])

        if drugs_needing_substitutes:
            print(f"{'='*80}")
            print(f"PHASE 3: Substitute Finding (Conditional)")
            print(f"{'='*80}\n")

            phase3_start = datetime.now()

            try:
                agent_3_substitutes.run(run_id, drugs_needing_substitutes)
                phase3_duration = (datetime.now() - phase3_start).total_seconds()

                results["phases"]["phase_3"] = {
                    "duration_seconds": phase3_duration,
                    "result": "success",
                    "drugs_processed": len(drugs_needing_substitutes)
                }

                print(f"\n{'='*80}")
                print(f"PHASE 3 COMPLETED in {phase3_duration:.2f}s")
                print(f"{'='*80}\n")

            except Exception as e:
                print(f"\n✗ PHASE 3 FAILED: {e}")
                results["errors"].append(f"Phase 3 (Substitutes): {e}")
                results["phases"]["phase_3"] = {"result": "failed", "error": str(e)}
                # Continue execution despite failure

        else:
            print(f"{'='*80}")
            print(f"PHASE 3: SKIPPED (No substitutes needed)")
            print(f"{'='*80}\n")
            results["phases"]["phase_3"] = {"result": "skipped"}

        # ====================================================================
        # PHASE 4: Order Management (Data-Driven)
        # ====================================================================
        print(f"{'='*80}")
        print(f"PHASE 4: Order Management (Processing Confirmed Orders)")
        print(f"{'='*80}\n")

        phase4_start = datetime.now()

        try:
            # Run Agent 4 unconditionally to check for confirmed orders in the DB
            agent_4_orders.run(run_id)
            phase4_duration = (datetime.now() - phase4_start).total_seconds()

            results["phases"]["phase_4"] = {
                "duration_seconds": phase4_duration,
                "result": "success"
            }

            print(f"\n{'='*80}")
            print(f"PHASE 4 COMPLETED in {phase4_duration:.2f}s")
            print(f"{'='*80}\n")

        except Exception as e:
            print(f"\n✗ PHASE 4 FAILED: {e}")
            results["errors"].append(f"Phase 4 (Orders): {e}")
            results["phases"]["phase_4"] = {"result": "failed", "error": str(e)}
            # Continue execution despite failure

        # ====================================================================
        # PIPELINE COMPLETE
        # ====================================================================
        end_time = datetime.now()
        total_duration = (end_time - start_time).total_seconds()

        results["end_time"] = end_time.isoformat()
        results["total_duration_seconds"] = total_duration
        results["status"] = "completed_with_errors" if results["errors"] else "success"

        print(f"{'='*80}")
        print(f"PIPELINE EXECUTION COMPLETE")
        print(f"Status: {results['status']}")
        print(f"Total Duration: {total_duration:.2f}s")
        print(f"Errors: {len(results['errors'])}")
        print(f"{'='*80}\n")

        return results

    except Exception as e:
        end_time = datetime.now()
        total_duration = (end_time - start_time).total_seconds()

        results["end_time"] = end_time.isoformat()
        results["total_duration_seconds"] = total_duration
        results["status"] = "failed"
        results["errors"].append(f"Pipeline failure: {e}")

        print(f"\n{'='*80}")
        print(f"PIPELINE FAILED")
        print(f"Error: {e}")
        print(f"Duration: {total_duration:.2f}s")
        print(f"{'='*80}\n")

        raise

def run_phase_1_parallel(run_id: UUID) -> Dict[str, Any]:
    """
    Run Phase 1 agents (0, 1, 2) in parallel using asyncio.
    """
    async def main():
        with ThreadPoolExecutor() as executor:
            loop = asyncio.get_event_loop()
            tasks = [
                loop.run_in_executor(executor, agent_0_inventory.run, run_id),
                loop.run_in_executor(executor, agent_1_fda.run, run_id),
                loop.run_in_executor(executor, agent_2_news.run, run_id)
            ]
            return await asyncio.gather(*tasks, return_exceptions=True)

    agent_results = asyncio.run(main())
    
    results = {}
    agent_names = ["agent_0", "agent_1", "agent_2"]
    for i, result in enumerate(agent_results):
        agent_name = agent_names[i]
        if isinstance(result, Exception):
            print(f"\n✗ {agent_names[i]} failed: {result}")
            results[agent_name] = {"status": "failed", "error": str(result)}
        else:
            print(f"\n✓ {agent_names[i]} completed successfully")
            results[agent_name] = {"status": "success"}
    return results

if __name__ == '__main__':
    # Test the pipeline
    run_pipeline()
