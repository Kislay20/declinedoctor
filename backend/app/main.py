from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base
from .routes import dashboard, incidents, simulate

# Ensure tables are created (fallback)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="DeclineDoctor API")

# Allow React frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(incidents.router, prefix="/api/incidents", tags=["Incidents"])
app.include_router(simulate.router, prefix="/api/simulate", tags=["Simulation"])

@app.get("/api/health")
def health_check():
    return {"status": "ok", "system": "DeclineDoctor API running"}