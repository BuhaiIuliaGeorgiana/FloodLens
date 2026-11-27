import uuid
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .orchestrator import run_event_pipeline

from .config import FRONTEND_ORIGIN
from .supabase_client import get_event, create_pipeline_run 

app = FastAPI(title = "FloodLens pipeline service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/events/{event_id}/process")
def trigger_event_processing(event_id: str, background_tasks: BackgroundTasks):
    event = get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    run_id = create_pipeline_run(event_id)
    background_tasks.add_task(run_event_pipeline, event_id, run_id)
    return {"run_id": run_id, "status": "queued"} 