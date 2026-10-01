from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .database import engine, Base
from .routers import auth, student, faculty, admin, common, placement, ai_assistant, campus_life

app = FastAPI(title="CampusOne AI", version="1.0.0",
              description="Integrated University Campus Management & Student Success Portal API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

app.include_router(auth.router)
app.include_router(student.router)
app.include_router(faculty.router)
app.include_router(admin.router)
app.include_router(common.router)
app.include_router(placement.router)
app.include_router(ai_assistant.router)
app.include_router(campus_life.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "CampusOne AI backend"}


@app.on_event("startup")
def check_seed():
    # IMPORTANT: file-size heuristics are unreliable for SQLite - an empty
    # schema (created by Base.metadata.create_all above) is already ~98KB
    # on disk before a single row is inserted, so a size check can never
    # detect an unseeded database. We check actual row counts instead, and
    # this self-heals any previously "seeded" but actually-empty database.
    from .database import SessionLocal
    from . import models

    db = SessionLocal()
    try:
        user_count = db.query(models.User).count()
    except Exception:
        user_count = 0
    finally:
        db.close()

    if user_count == 0:
        print("No users found in the database - running seed script...")
        from . import seed
        try:
            seed.run()
        except Exception as exc:
            print(f"SEED FAILED: {exc}")
            print("Login will not work until this is fixed. "
                  "Common cause: bcrypt/passlib version mismatch - "
                  "run 'pip install bcrypt==4.0.1' and restart.")
            raise
    else:
        print(f"Database already seeded ({user_count} users found). Skipping seed.")
