"""Cavela Audit — product feedback report generator."""

import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.pipeline import run_pipeline, JobStatus, jobs

app = FastAPI(title="Cavela Audit")
_static_dir = Path(__file__).parent / "static"
_static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=_static_dir), name="static")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

JOBS_DIR = Path("jobs")
JOBS_DIR.mkdir(exist_ok=True)


@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.post("/submit")
async def submit(
    background_tasks: BackgroundTasks,
    brand_url: str = Form(...),
    email: str = Form(...),
):
    job_id = str(uuid.uuid4())[:8]
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    jobs[job_id] = JobStatus(
        job_id=job_id,
        brand_url=brand_url,
        email=email,
        status="queued",
        step="Waiting to start",
        output_dir=str(job_dir),
    )

    background_tasks.add_task(run_pipeline, job_id)

    return JSONResponse({"job_id": job_id})


@app.get("/status/{job_id}")
async def status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    return JSONResponse({
        "job_id": job.job_id,
        "status": job.status,
        "step": job.step,
        "error": job.error,
        "messages": job.messages,
    })


@app.get("/progress/{job_id}", response_class=HTMLResponse)
async def progress_page(request: Request, job_id: str):
    job = jobs.get(job_id)
    if not job:
        return HTMLResponse("Job not found", status_code=404)
    return templates.TemplateResponse(request, "progress.html", context={
        "job_id": job_id,
        "brand_url": job.brand_url,
    })
