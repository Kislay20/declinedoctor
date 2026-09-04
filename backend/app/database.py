from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DB_DIR, exist_ok=True)

# Configurable database URL: PostgreSQL or SQLite
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = f"sqlite:///{os.path.join(DB_DIR, 'declinedoctor.db')}"
elif DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(
        DATABASE_URL, pool_size=10, max_overflow=20, pool_pre_ping=True
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def ensure_schema_updated():
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            res = conn.execute(text("PRAGMA table_info(diagnoses)")).fetchall()
            cols = [r[1] for r in res]
            if cols and "counterfactuals_json" not in cols:
                conn.execute(text("ALTER TABLE diagnoses ADD COLUMN counterfactuals_json TEXT"))

            res_tx = conn.execute(text("PRAGMA table_info(transactions)")).fetchall()
            cols_tx = [r[1] for r in res_tx]
            if cols_tx and "card_bin" not in cols_tx:
                conn.execute(text("ALTER TABLE transactions ADD COLUMN card_bin TEXT"))
    except Exception:
        pass


ensure_schema_updated()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()