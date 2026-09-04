from fastapi import APIRouter
from ..database import SessionLocal
from ..detection import detect_anomalies
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scripts.seed_data import seed_database

router = APIRouter()

@router.post("/inject")
def reset_and_detect():
    seed_database()
    
    demo_time = datetime.now()
    db = SessionLocal()
    try:
        anomalies = detect_anomalies(db, demo_time)
        return {
            "status": "success", 
            "message": "Data seeded and anomalies detected.",
            "incidents_detected": len(anomalies)
        }
    finally:
        db.close()