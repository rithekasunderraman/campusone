"""
Backend for browser end-to-end tests.

Runs the real application on port 8001 against a throwaway COPY of the local
database (backend/e2e/e2e.db), so the demo flow can be exercised with realistic
data without ever writing to campusone.db. If no local database exists (e.g. on
a clean checkout) the app starts on an empty database and seeds demo data.

    python -m scripts.e2e_server
"""
import os
import shutil
import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
WORK = BACKEND / "e2e"
PORT = int(os.getenv("E2E_BACKEND_PORT", "8001"))


def main() -> None:
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True)
    target = WORK / "e2e.db"
    live = BACKEND / "campusone.db"
    if live.exists():
        src = sqlite3.connect(f"file:{live.as_posix()}?mode=ro", uri=True)
        dst = sqlite3.connect(target)
        src.backup(dst)   # consistent snapshot even if the dev server is running
        dst.close()
        src.close()

    os.environ.update({
        "APP_ENV": "development",
        "APP_INSTANCE": "e2e",
        "DATABASE_URL": f"sqlite:///{target.as_posix()}",
        "STORAGE_BACKEND": "local",
        "STORAGE_DIR": str(WORK / "storage"),
        "CORS_ORIGINS": "http://localhost:5174,http://127.0.0.1:5174",
        "AUTO_SEED": "true",
    })
    if os.getenv("E2E_LLM") == "1":
        print("e2e backend: LLM ENABLED - provider and key come from backend/.env")
    else:
        # Browser tests assert exact deterministic wording, so no provider may answer.
        os.environ.update({"ANTHROPIC_API_KEY": "", "GEMINI_API_KEY": ""})
    sys.path.insert(0, str(BACKEND))
    os.chdir(BACKEND)
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
