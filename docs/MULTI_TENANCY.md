# Institutional configurability and multi-tenancy

## Status in one line

**Institution-configurable: implemented and tested. Multi-tenant isolation: architected for, not yet proven.**
No second institution's data has been created and no cross-institution isolation test exists, so
this project must not be described as multi-tenant.

## What exists today

- An `institutions` table with one row. It holds the institution's profile (name, short name,
  support email, logo URL, primary colour) and its OD policy (hours per semester, term dates,
  minimum attendance, approval chain, HOD threshold, per-request limit).
- Every rule in the OD workflow reads that policy at run time; nothing is hard-coded. Changing
  the policy in the admin screen changes eligibility, routing and balances immediately
  (covered by tests).
- Every table added from the OD workflow onward carries `institution_id` from day one:
  `od_requests` (new column), `advisor_assignments`, `department_heads`, `od_documents`,
  `od_audit_logs`, `od_attendance_credits`, `stored_files`.
- Department-level scoping is real and tested: a department head sees and acts on only their
  department's requests, analytics and assistant answers.

## How deep the single-institution assumption runs

Evaluated against the schema and every query in `backend/app/routers`:

| Area | Finding |
|---|---|
| Original 26 tables | None has an institution column. `users`, `departments`, `students`, `faculty`, `courses`, `subjects`, `clubs`, `companies`, `announcements`, `events`, `hostels` are all global. |
| Uniqueness | `users.username`, `students.register_number`, `faculty.employee_code` and `clubs.name` are unique across the whole database, so two institutions could not both have `admin` or a "Coding Club". |
| Queries | About 60 queries in the original routers aggregate with no tenant filter at all (for example "count all students", "all open drives", "all announcements"). Each would need a filter added and tested. |
| Authentication | The login token carries a username and role only; there is no institution claim and no institution-selection step. |
| Roles | "Admin" means institution-wide by default. There is no platform-level super-admin distinct from an institution admin. |
| Seed and fixtures | Generate exactly one institution. |

### Is true row-level isolation realistic now?

No. It would mean adding `institution_id` to 11 root tables on a live 142,000-row database,
changing four unique constraints, adding an institution claim to authentication, and rewriting
and re-testing roughly 60 queries — with a silent data leak as the failure mode of any one that
is missed. That is a multi-week change that deserves its own test suite; attempting it alongside
the OD work would have risked the working application. It was deliberately not attempted.

## Expansion path

Because the new tables are already institution-scoped, onboarding a second institution is
**additive for everything built in this phase** and a bounded migration for the legacy tables:

1. Insert a second `institutions` row with its own policy.
2. Migration: add nullable `institution_id` to the 11 legacy root tables, backfill `1`, then make
   it `NOT NULL`. Child tables inherit scope through their parent (attendance through student,
   and so on) and need no column.
3. Replace the four global unique constraints with per-institution ones
   (`(institution_id, username)` and so on).
4. Put `institution_id` in the login token and resolve it once per request in a dependency;
   add it to every root query (or enforce it centrally with a SQLAlchemy `with_loader_criteria`
   session hook so a forgotten filter cannot leak).
5. **Prove it:** seed a second institution and add tests asserting that every list, detail,
   analytics and assistant endpoint returns zero rows from the other institution. Only after
   those tests pass may the product be called multi-tenant.

On PostgreSQL, row-level security policies keyed on a per-connection setting are a strong
second line of defence for step 4.
