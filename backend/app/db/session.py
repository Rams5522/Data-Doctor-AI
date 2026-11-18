from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from sqlalchemy import text

# Create engine


def _ensure_dataset_versions_columns(engine):
    """Best-effort SQLite schema upgrade for format-preserving repair.

    This is non-destructive: it only adds missing columns.
    """
    try:
        with engine.connect() as conn:
            cols = set()
            try:
                rows = conn.execute(text("PRAGMA table_info(dataset_versions)")).fetchall()
                for r in rows:
                    # r layout: (cid, name, type, notnull, dflt_value, pk)
                    cols.add(r[1])
            except Exception:
                # Table might not exist yet; let normal startup/create logic handle it.
                return

            missing = []
            if "file_format" not in cols:
                missing.append("file_format")
            if "format_metadata" not in cols:
                missing.append("format_metadata")
            if "artifact_status" not in cols:
                missing.append("artifact_status")

            for col in missing:
                if col == "file_format":
                    conn.execute(text("ALTER TABLE dataset_versions ADD COLUMN file_format VARCHAR"))
                elif col == "format_metadata":
                    conn.execute(text("ALTER TABLE dataset_versions ADD COLUMN format_metadata TEXT"))
                elif col == "artifact_status":
                    conn.execute(text("ALTER TABLE dataset_versions ADD COLUMN artifact_status VARCHAR DEFAULT 'committed'"))

            if missing:
                conn.commit()
    except Exception:
        # Fail open: app may still run with legacy DB, but new features might be unavailable.
        pass


# Create engine

# Ensure schema compatibility at import time
# (safe because it only adds missing columns).

engine = create_engine(
    settings.DATABASE_URL, connect_args={"check_same_thread": False}
)

_ensure_dataset_versions_columns(engine)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()