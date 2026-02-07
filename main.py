"""
PharmaSentinel Main Entry Point

Runs the pipeline orchestrator in a continuous loop with configurable interval.
This is the production entry point for the PharmaSentinel system.

Usage:
    python main.py                    # Run continuously with default 60-minute interval
    python main.py --once             # Run once and exit
    python main.py --interval 30      # Run with custom interval (minutes)
"""

import os
import sys
import time
import argparse
from datetime import datetime
from agents.pipeline import run_pipeline, run_quick_pipeline
from agents.shared import validate_environment

def main():
    """Main entry point for PharmaSentinel."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='PharmaSentinel Pipeline Runner')
    parser.add_argument(
        '--once',
        action='store_true',
        help='Run pipeline once and exit (default: run continuously)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=int(os.getenv('PIPELINE_INTERVAL_MINUTES', 60)),
        help='Interval between pipeline runs in minutes (default: 60)'
    )
    args = parser.parse_args()

    print("\n" + "="*80)
    print("PHARMASENTINEL - Hospital Pharmacy Supply Chain Intelligence")
    print("="*80 + "\n")

    # Validate environment
    print("Validating environment configuration...")
    env_valid = validate_environment()

    if not env_valid:
        print("\n⚠️  WARNING: Some environment variables are missing or using placeholders.")
        print("The system will continue but some features may not work correctly.")
        print("Please update your .env file with actual values.\n")

        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Exiting. Please configure environment variables and try again.")
            sys.exit(1)
    else:
        print("✓ Environment validated\n")

    # Run mode
    if args.once:
        print(f"Mode: Single execution")
        print(f"Starting pipeline at {datetime.now().isoformat()}\n")

        try:
            result = run_pipeline()
            print(f"\n✓ Pipeline completed successfully")
            print(f"Status: {result.get('status')}")
            print(f"Run ID: {result.get('run_id')}")
            print(f"Duration: {result.get('total_duration_seconds', 0):.2f}s")

            if result.get('errors'):
                print(f"\n⚠️  Errors encountered:")
                for error in result['errors']:
                    print(f"  - {error}")
                sys.exit(1)
            else:
                sys.exit(0)

        except Exception as e:
            print(f"\n✗ Pipeline failed: {e}")
            sys.exit(1)

    else:
        # Continuous mode - Async Realtime Listener
        import asyncio
        from supabase import create_async_client
        from agents.shared import SUPABASE_URL, SUPABASE_SERVICE_KEY

        if not (SUPABASE_URL and SUPABASE_SERVICE_KEY):
            print("Error: Supabase credentials missing.")
            sys.exit(1)

        async def run_pipeline_async():
            """Wrapper to run synchronous pipeline in thread executor"""
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = await loop.run_in_executor(pool, run_pipeline)
            return result

        async def periodic_runner(interval_minutes):
            """Runs the full pipeline periodically"""
            while True:
                # Wait first (since we run once at startup)
                await asyncio.sleep(interval_minutes * 60)
                print(f"\n[Periodic] Starting scheduled pipeline run...")
                try:
                    result = await run_pipeline_async()
                    print(f"✓ Periodic run completed. Status: {result.get('status')}")
                except Exception as e:
                    print(f"✗ Periodic run failed: {e}")

        async def listen_for_changes():
            """Listens for Realtime changes on 'drugs' table"""
            print(f"Mode: Continuous execution (Realtime Trigger + Periodic {args.interval}m)")
            
            # Initialize Async Client
            async_supabase = await create_async_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
            print(f"Listening for changes on 'drugs' table...")
            
            # Smart Loop Prevention
            last_run_time = 0
            min_interval = 2  # Seconds - debounce quick clicks

            def handle_db_change(payload):
                nonlocal last_run_time
                current_time = time.time()

                # Inspect Payload Structure (Debug)
                try:
                    data = payload.get('data', {}) if isinstance(payload, dict) else payload
                    table_name = data.get('table')
                    event_type_raw = data.get('type')
                    if hasattr(event_type_raw, 'value'):
                        event_type = event_type_raw.value
                    else:
                        event_type = str(event_type_raw) if event_type_raw else None
                    
                    print(f"\n[Realtime] Event: {event_type} on table '{table_name}'", flush=True)
                    
                except Exception as e:
                    print(f"[Realtime Error] Failed to parse payload: {e}", flush=True)
                    return

                # Only process valid database events
                if event_type not in ('UPDATE', 'INSERT', 'DELETE'):
                    return
                
                if table_name != 'drugs':
                    return

                # Check Debounce (too fast user clicks)
                if current_time - last_run_time < min_interval:
                    print(f"  -> Skipping (debounced)")
                    return

                print(f"[Realtime] Triggering QUICK pipeline (Agent 0 Quick Mode + Overseer)...", flush=True)
                last_run_time = time.time()
                
                # Run quick pipeline in separate thread (Overseer only)
                # Note: We use run_quick_pipeline directly here as it's fire-and-forget for the callback
                # But callback is sync, so we must not block.
                # However, supabase-py callbacks run in a thread?
                # We'll use a thread executor to be safe.
                import concurrent.futures
                try:
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(run_quick_pipeline)
                        # We don't wait for result here to avoid blocking the callback thread
                        # But actually, we want to see output?
                        # Let's wait briefly or just log start
                        pass
                    print(f"✓ Quick pipeline triggered.", flush=True)
                except Exception as e:
                    print(f"✗ Quick pipeline trigger failed: {e}")


            try:
                # client.channel is synchronous
                channel = async_supabase.channel('drug-updates')
                
                await channel.on_postgres_changes(
                    event='*',
                    schema='public',
                    table='drugs',
                    callback=handle_db_change
                ).subscribe()

                print("✓ Subscribed to Realtime events on 'drugs' table.")
                
                # Run periodic task concurrently
                await periodic_runner(args.interval)

            except Exception as e:
                print(f"Realtime error: {e}")
                # Don't try to close the client as it doesn't have a close method exposed here


        async def main_async():
            # 1. Run initial pipeline SYNCHRONOUSLY (await it) before starting listener
            # This ensures state is fresh and we don't need complex skip logic
            print("\n[Startup] Running initial pipeline analysis...")
            try:
                result = await run_pipeline_async()
                print(f"✓ Initial pipeline run completed. Status: {result.get('status')}")
            except Exception as e:
                print(f"✗ Initial pipeline run failed: {e}")

            # 2. Start Listener + Periodic Loop
            # The periodic loop is inside listen_for_changes (calls periodic_runner)
            # await listen_for_changes()
            
            # Actually, separating them is cleaner
            await listen_for_changes()

        try:
            asyncio.run(main_async())
        except KeyboardInterrupt:
            print("\nShutting down...")
            sys.exit(0)

if __name__ == '__main__':
    # Imports are handled inside main functions or at top
    pass
    main()
