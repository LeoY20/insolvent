"""
PharmaSentinel Backend Server

- Exposes interactive API for Order Analysis and Confirmation.
- Runs the main pipeline in a background thread for continuous monitoring (FDA/News/Inventory).
"""

import threading
import time
import os
import uuid
import uvicorn
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents.pipeline import run_pipeline
from agents.agent_4_orders import run_analysis

app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global flag to control pipeline loop
PIPELINE_RUNNING = False # TODO: Make this configurable
PIPELINE_INTERVAL_MINUTES = int(os.getenv('PIPELINE_INTERVAL_MINUTES', 60))

def pipeline_loop():
    """Background thread to run the monitoring pipeline."""
    print(f"Starting pipeline background loop (Interval: {PIPELINE_INTERVAL_MINUTES}m)")
    while PIPELINE_RUNNING:
        try:
            print("\n--- Scheduled Pipeline Run Starting ---")
            run_pipeline()
            print("--- Scheduled Pipeline Run Finished ---")
        except Exception as e:
            print(f"Pipeline Loop Error: {e}")
        
        # Sleep for interval
        time.sleep(PIPELINE_INTERVAL_MINUTES * 60)

@app.on_event("startup")
def startup_event():
    # Start the pipeline in a daemon thread
    t = threading.Thread(target=pipeline_loop, daemon=True)
    t.start()

@app.get("/")
def health_check():
    return {"status": "ok", "service": "PharmaSentinel Backend"}

class TriggerResponse(BaseModel):
    status: str
    message: str
    data: dict = {}

@app.post("/api/analyze-order/{order_id}", response_model=TriggerResponse)
async def analyze_order(order_id: str, background_tasks: BackgroundTasks):
    """
    Triggers the Order Agent to ANALYZE a specific order.
    The agent will update the status to 'ANALYZING' then 'SUGGESTED'.
    """
    run_id = uuid.uuid4()
    
    def task():
        print(f"--- Manual Trigger: Analyze Order {order_id} (RunID: {run_id}) ---")
        run_analysis(order_id, run_id)
        print("--- Manual Analysis Finished ---")

    background_tasks.add_task(task)
    
    return {
        "status": "success",
        "message": "Order Analysis triggered successfully",
        "data": {"run_id": str(run_id), "order_id": order_id}
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"Starting server on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
