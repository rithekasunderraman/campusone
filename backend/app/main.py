from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from . import config, llm
from .database import engine
from .db_setup import prepare_database
from .routers import auth, student, faculty, admin, common, placement, ai_assistant, campus_life, od

app = FastAPI(title="CampusOne AI", version="2.0.0",
              description="Integrated University Campus Management & Student Success Portal API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(student.router)
app.include_router(faculty.router)
app.include_router(admin.router)
app.include_router(common.router)
app.include_router(placement.router)
app.include_router(ai_assistant.router)
app.include_router(campus_life.router)
app.include_router(od.student_router)
app.include_router(od.faculty_router)
app.include_router(od.admin_router)
app.include_router(od.shared_router)


@app.get("/api/health")
def health():
    """Liveness + database check, used by the host's uptime monitoring."""
    try:
        with engine.connect() as conn:
            conn.execute(text("select 1"))
    except Exception:
        return JSONResponse(status_code=503, content={
            "status": "degraded", "service": "CampusOne AI backend", "database": "unreachable"})
    return {"status": "ok", "service": "CampusOne AI backend", "database": "ok", "environment": config.APP_ENV,
            "instance": config.APP_INSTANCE,
            "llm": (f"{llm.provider()} ({config.GEMINI_MODEL if llm.provider() == 'gemini' else config.LLM_MODEL})"
                    if llm.available() else None)}


@app.on_event("startup")
def check_seed():
    # Schema is managed by Alembic (see db_setup). Seeding only ever happens on a
    # database with zero users, and never in production.
    prepare_database()
