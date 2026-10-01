"""
One-time data migration: copy every row from the CampusOne SQLite database into
PostgreSQL, preserving primary keys and foreign-key relationships.

Usage (from the backend/ folder, virtualenv active):

    python -m scripts.migrate_sqlite_to_postgres --target postgresql://user:pass@host:5432/dbname

    # or keep the URL out of your shell history:
    set TARGET_DATABASE_URL=postgresql://...        (PowerShell: $env:TARGET_DATABASE_URL="...")
    python -m scripts.migrate_sqlite_to_postgres

Options:
    --source PATH     SQLite file to read (default: backend/campusone.db)
    --replace         Empty the target tables first. Without this flag the script
                      refuses to touch a target that already contains data.
    --verify-only     Do not copy; only compare source and target.

What it does:
    1. Brings the target schema to the same Alembic revision as the source.
    2. Copies all tables in foreign-key dependency order, in batches, inside one
       transaction (any failure rolls the whole copy back).
    3. Resets PostgreSQL id sequences so new inserts continue after the copied ids.
    4. Verifies: per-table row counts, a full row-by-row content comparison, and
       relationship spot checks for a specific student.

The source database is opened read-only and is never modified.
"""
import argparse
import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, func, select, text

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

BATCH = 2000


def normalise(url: str) -> str:
    return "postgresql://" + url[len("postgres://"):] if url.startswith("postgres://") else url


def revision_of(engine):
    with engine.connect() as c:
        try:
            return c.execute(text("select version_num from alembic_version")).scalar()
        except Exception:
            return None


def cell(v):
    """Normalise a value so SQLite and PostgreSQL representations compare equal."""
    if isinstance(v, float):
        return round(v, 6)
    if isinstance(v, dt.datetime):
        return v.replace(tzinfo=None).isoformat(timespec="microseconds")
    if isinstance(v, (dt.date, dt.time)):
        return v.isoformat()
    if isinstance(v, memoryview):
        return bytes(v)
    return v


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", default=str(BACKEND_DIR / "campusone.db"))
    ap.add_argument("--target", default=os.getenv("TARGET_DATABASE_URL", ""))
    ap.add_argument("--replace", action="store_true")
    ap.add_argument("--verify-only", action="store_true")
    args = ap.parse_args()

    if not args.target:
        print("ERROR: give the PostgreSQL URL with --target or TARGET_DATABASE_URL.")
        return 2
    target_url = normalise(args.target)
    if not target_url.startswith("postgresql"):
        print("ERROR: the target must be a PostgreSQL URL.")
        return 2
    source_path = Path(args.source).resolve()
    if not source_path.exists():
        print(f"ERROR: source database not found: {source_path}")
        return 2

    # Import the models only after sys.path is set; they define the table list.
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{source_path.as_posix()}")
    from app.database import Base
    from app import models  # noqa: F401

    src = create_engine(f"sqlite:///file:{source_path.as_posix()}?mode=ro&uri=true")
    dst = create_engine(target_url)
    tables = list(Base.metadata.sorted_tables)  # parents before children

    src_rev = revision_of(src)
    if not src_rev:
        print("ERROR: the source database has no Alembic revision. Run 'alembic stamp 0001' "
              "(or 'alembic upgrade head') on it first.")
        return 2
    print(f"Source: {source_path}  (revision {src_rev})")
    print(f"Target: {dst.url.render_as_string(hide_password=True)}")

    if not args.verify_only:
        # 1. Schema: bring the target to exactly the source's revision.
        env = dict(os.environ, DATABASE_URL=target_url)
        alembic = [sys.executable, "-m", "alembic", "upgrade", src_rev]
        res = subprocess.run(alembic, cwd=BACKEND_DIR, env=env, capture_output=True, text=True)
        if res.returncode != 0:
            print("ERROR: could not create the target schema:\n" + res.stderr[-2000:])
            return 1
        print(f"Target schema is at revision {revision_of(dst)}.")

        # 2. Copy, all-or-nothing.
        with src.connect() as s, dst.begin() as d:
            existing = sum(d.execute(select(func.count()).select_from(t)).scalar() for t in tables)
            if existing and not args.replace:
                print(f"ERROR: the target already holds {existing} rows. Re-run with --replace to "
                      "empty the target tables first (the source is never modified).")
                return 1
            if existing:
                names = ", ".join(f'"{t.name}"' for t in tables)
                d.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
                print(f"Emptied {len(tables)} target tables.")
            total = 0
            for t in tables:
                n = 0
                result = s.execution_options(stream_results=True).execute(select(t))
                while True:
                    rows = result.fetchmany(BATCH)
                    if not rows:
                        break
                    d.execute(t.insert(), [dict(r._mapping) for r in rows])
                    n += len(rows)
                total += n
                print(f"  copied {t.name:<24} {n:>7}")
            # 3. Sequences.
            for t in tables:
                pk = list(t.primary_key.columns)
                if len(pk) == 1 and pk[0].type.python_type is int:
                    d.execute(text(
                        f"SELECT setval(pg_get_serial_sequence('{t.name}', '{pk[0].name}'), "
                        f"COALESCE((SELECT MAX({pk[0].name}) FROM \"{t.name}\"), 0) + 1, false)"))
            print(f"Copied {total} rows in one transaction; sequences reset.")

    # 4. Verify.
    print("\nVerification")
    if revision_of(dst) != src_rev:
        print(f"  FAIL revision mismatch: source {src_rev}, target {revision_of(dst)}")
        return 1
    ok = True
    with src.connect() as s, dst.connect() as d:
        for t in tables:
            order = list(t.primary_key.columns)
            a = s.execute(select(func.count()).select_from(t)).scalar()
            b = d.execute(select(func.count()).select_from(t)).scalar()
            diffs = 0
            if a == b:
                ra = s.execution_options(stream_results=True).execute(select(t).order_by(*order))
                rb = d.execution_options(stream_results=True).execute(select(t).order_by(*order))
                for x, y in zip(ra, rb):
                    if tuple(cell(v) for v in x) != tuple(cell(v) for v in y):
                        diffs += 1
                        if diffs == 1:
                            print(f"    first difference in {t.name}: {tuple(x)} != {tuple(y)}")
            good = a == b and diffs == 0
            ok &= good
            print(f"  {'OK  ' if good else 'FAIL'} {t.name:<24} source={a:>7} target={b:>7} differing_rows={diffs}")

        # Relationship spot checks: identity must be preserved, not just counts.
        spot = {
            "student1 -> student row": "select s.id, s.register_number, s.department_id from students s "
                                       "join users u on u.id = s.user_id where u.username = 'student1'",
            "student1 attendance": "select a.subject_id, a.total_classes, a.attended_classes from attendance a "
                                   "join students s on s.id = a.student_id join users u on u.id = s.user_id "
                                   "where u.username = 'student1' order by a.subject_id",
            "student1 marks": "select m.subject_id, m.grade from marks m join students s on s.id = m.student_id "
                              "join users u on u.id = s.user_id where u.username = 'student1' order by m.subject_id",
            "student id 2 OD requests": "select o.id, o.event_id, o.requested_hours, o.status from od_requests o "
                                        "where o.student_id = 2 order by o.id",
            "student1 club names": "select c.name from clubs c join club_memberships m on m.club_id = c.id "
                                   "join students s on s.id = m.student_id join users u on u.id = s.user_id "
                                   "where u.username = 'student1' order by c.name",
            "faculty1 subjects": "select sub.code from subjects sub join faculty f on f.id = sub.faculty_id "
                                 "join users u on u.id = f.user_id where u.username = 'faculty1' order by sub.code",
            "password hash of admin": "select password_hash from users where username = 'admin'",
        }
        for label, sql in spot.items():
            ra = [tuple(cell(v) for v in r) for r in s.execute(text(sql))]
            rb = [tuple(cell(v) for v in r) for r in d.execute(text(sql))]
            good = ra == rb and len(ra) > 0
            ok &= good
            shown = ra if len(str(ra)) < 110 else f"{len(ra)} rows"
            print(f"  {'OK  ' if good else 'FAIL'} spot check: {label}: {shown}")

        # New inserts must not collide with copied ids.
        nxt = d.execute(text("select nextval(pg_get_serial_sequence('users','id'))")).scalar()
        mx = d.execute(text("select max(id) from users")).scalar()
        good = nxt > mx
        ok &= good
        print(f"  {'OK  ' if good else 'FAIL'} users id sequence continues after max id ({mx} -> next {nxt})")

    print("\nRESULT:", "MIGRATION VERIFIED" if ok else "VERIFICATION FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
