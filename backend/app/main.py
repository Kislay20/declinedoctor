import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base
from .routes import dashboard, incidents, simulate, segments, evaluation, observability, providers
from .observability import record_request_latency

# Ensure tables are created (fallback)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="DeclineDoctor API",
    description="Autonomous Agentic Payment Recovery Engine with Strict Backend Safety Guardrails",
    version="2.0.0",
)

# Latency and telemetry middleware
@app.middleware("http")
async def add_telemetry_middleware(request: Request, call_next):
    start_time = time.time()
    is_error = False
    try:
        response = await call_next(request)
        if response.status_code >= 500:
            is_error = True
        return response
    except Exception:
        is_error = True
        raise
    finally:
        latency_ms = (time.time() - start_time) * 1000.0
        record_request_latency(latency_ms, is_error=is_error)

# Allow React frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from .routes import dashboard, incidents, simulate, segments, evaluation, observability, providers, learning, experiments, webhooks

# Register routes
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(incidents.router, prefix="/api/incidents", tags=["Incidents"])
app.include_router(simulate.router, prefix="/api/simulate", tags=["Simulation"])
app.include_router(segments.router, tags=["Segments"])
app.include_router(evaluation.router, tags=["Evaluation"])
app.include_router(observability.router, tags=["Observability"])
app.include_router(providers.router, tags=["Providers"])
app.include_router(learning.router, tags=["Learning"])
app.include_router(experiments.router, tags=["Experiments"])
app.include_router(webhooks.router)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "system": "DeclineDoctor API running", "version": "2.0.0"}