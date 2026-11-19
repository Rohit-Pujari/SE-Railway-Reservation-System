# System Validation Report — Railway Reservation System

**Date:** 19 November 2026  
**Overall result:** Conditional — core flows implemented and unit-tested; real-database integration blocked by unavailable database credentials.  
**Reference:** `Documents/VERIFICATION_2026-11-19.md`  
**Commit SHA:** `8bc9b10` (merge of `feature/demo-seed-data` into `main`) plus evaluation fixes on branch `se-evaluation-complete`  
**Systems covered:** Django backend, React frontend, booking and simulated payment, cancellation and refunds, administrator management.

---

## 1. Purpose and acceptance criteria

This report evaluates whether the reservation system meets the requirements in `docs/SE_SRS.md` and `docs/SE_TEST_PLAN.md`. A test is marked **PASS** only when an actual result supports it. **IMPLEMENTED, NOT VERIFIED** means the feature exists in code and is covered by unit tests but could not be exercised against a live database. **BLOCKED** means the check could not be completed due to an external dependency. **NOT IMPLEMENTED** means the feature is absent from the codebase.

---

## 2. Environment and method

- **Backend:** Python 3.11.18, Django 5.2, Django REST Framework, `mysql-connector-python`, `werkzeug` password hashing.
- **Frontend:** React 19, Vite, Playwright (Chromium).
- **Test database:** MySQL 8.0.16+ is installed and listening on port 3306, but no database credentials are available in this environment. `root` and `railway_app` connections are both denied. `sudo` is unavailable without a password. Real-database integration testing is therefore **BLOCKED**.
- **Backend unit tests:** 232 tests run, 230 passing and 2 skipped (see `docs/test-reports/unit-test.log`). Database access is mocked; no development database is modified.
- **Frontend:** Production build succeeds; Playwright cross-browser smoke tests pass in Chromium.
- **Coverage:** `coverage.py` 7.17.3 with `--branch` on `backend/app` and `backend/config`.

---

## 3. Executed system validation cases

| ID | Requirement / workflow | Expected result | Actual result | Status |
|----|------------------------|-----------------|---------------|--------|
| SV-01 | Passenger registration and login | New user persists and can authenticate | Unit tests pass (registration validation, hashed-password storage, duplicate-email 409, safe error messages). Browser check recorded previously: registration HTTP 201, login/logout HTTP 200. | PASS (unit); PASS (historical browser) |
| SV-02 | Administrator authentication | Authorized admin login/logout works | Unit tests pass (admin login 200, passenger rejected 401, disabled admin 401, logout clears session). Historical browser: admin login/logout HTTP 200. | PASS (unit); PASS (historical browser) |
| SV-03 | Train search and fare | Valid route/date returns matching trains, fares and seats | Unit tests pass (search success, validation errors, parameterized SQL, bounded results). Historical browser: search/classes/fare/availability returned matching services. | PASS (unit); PASS (historical browser) |
| SV-04 | Passenger booking | Booking allocates seats and returns PNR | Unit tests pass (booking flow, PNR generation, seat holds, idempotency, conflict on unavailable seats). Historical browser: booking HTTP 201, inventory decreased by one. | PASS (unit); PASS (historical browser) |
| SV-05 | Simulated payment | Passenger-owned booking confirms after demo payment | Unit tests pass (payment confirmation, idempotent replay, ownership check, expired hold rejection). Not re-run against live DB. | PASS (unit); NOT VERIFIED (live DB) |
| SV-06 | Payment access control | Anonymous users cannot pay | Unit tests pass (anonymous pay returns 401). | PASS (unit); NOT VERIFIED (live DB) |
| SV-07 | Payment retry | Payment retries do not double-charge | Unit tests pass (replayed confirmation returns `replayed: true`, no duplicate payment). Not verified against live DB. | PASS (unit); NOT VERIFIED (live DB) |
| SV-08 | Idempotency | Repeat confirmation does not duplicate payment | Unit tests pass (same booking/PNR returned, `replayed: true`). Not verified against live DB. | PASS (unit); NOT VERIFIED (live DB) |
| SV-09 | Booking history | Owner sees ticket; other accounts cannot | Unit tests pass (history endpoint requires passenger session, scopes by user_id). Historical browser: confirmed ticket includes seats; cross-account read rejected. | PASS (unit); PASS (historical browser) |
| SV-10 | Idempotent booking | Repeated key cannot allocate twice | Unit tests pass (same booking/PNR returned, no additional allocation). | PASS (unit); NOT VERIFIED (live DB) |
| SV-11 | Concurrent seat allocation | Overselling prevented | Unit tests pass (booking creates holds under inventory lock; conflict on insufficient seats). Historical browser: two 6-seat requests on 8-seat service: one 201, one 409, two seats remain. | PASS (unit); PASS (historical browser) |
| SV-12 | Expired hold | Expiry restores inventory; payment rejected | Unit tests pass (payment checks `hold_expires_at <= current_time`). Historical browser: availability restored; payment rejected. | PASS (unit); PASS (historical browser) |
| SV-13 | Transaction rollback | Partial failure leaves no booking | Unit tests pass (rollback on database error in booking, fare, cancellation, passenger details). Historical browser: injected allocation-insert failure rolled back booking/passenger inserts. | PASS (unit); PASS (historical browser) |
| SV-14 | Browser CSRF protection | Trusted origin with token succeeds; untrusted origin fails | Unit tests pass (CSRF token required, untrusted origin 403, Vite origins accepted). Historical browser: Chromium registration initially failed with 403, corrected via trusted origins. | PASS (unit); PASS (historical browser) |
| SV-15 | Cancellation and pending refunds | Passenger can cancel, release seats, initiate refund | **IMPLEMENTED** in `backend/app/booking_cancellation.py` and `backend/app/booking_refunds.py`; API endpoint `POST /api/bookings/{id}/cancel` exists in `django_views.py`; unit tests pass (cancellation flow, refund calculation, seat release, ownership check). Not verified against live DB (blocked). | IMPLEMENTED, PASS (unit); NOT VERIFIED (live DB) |
| SV-16 | Administrator dashboard and management | Admin can manage trains, stations, routes, schedules, seats; view bookings/cancellations | **IMPLEMENTED** in `django_views.py` (admin dashboard, cancellation records, booking detail, train/station/route/schedule/seat CRUD) and service modules (`admin_dashboard.py`, `admin_cancellation_records.py`, `admin_booking_details.py`, `train_management.py`, `station_route_management.py`, `schedule_management.py`, `seat_management.py`); unit tests pass (dashboard authorization, admin auth, RBAC). Not verified against live DB (blocked). | IMPLEMENTED, PASS (unit); NOT VERIFIED (live DB) |
| SV-17 | Live database privileges | Application account can UPDATE runtime tables | **BLOCKED**: `database/app_permissions.sql` grants UPDATE on four tables, but applying it requires `sudo mariadb` which is unavailable without a password. No live grants were changed. | BLOCKED |
| SV-18 | Cross-browser and nonfunctional testing | Supported browsers render correctly | **PASS**: Playwright Chromium tests pass (application loads, navigation works, layout fits desktop/mobile viewports, search form keyboard accessible). Firefox, Edge, Safari not installed in this environment. | PASS (Chromium); NOT RUN (other browsers) |

---

## 4. Unit and build evidence

- **Backend unit tests:** 232 tests executed, **230 passed, 2 skipped**, 0 failed, 0 errors, 2 skipped. Command: `uv run --active python -m unittest discover -s backend/tests -p "test_*.py" -v`. Full log: `docs/test-reports/unit-test.log`.
- **Frontend production build:** `npm run build` succeeds (vite build, ~526 ms).
- **Django system check / compileall:** `python -m compileall -q backend` passes.
- **Browser tests:** 3 Playwright tests pass in Chromium.
- **Coverage:** Line coverage **63%**, branch coverage **56%** (`--branch` on `backend/app,backend/config`). Reports: `docs/test-reports/coverage-summary.txt`, `coverage.json`, `coverage.xml`.

Previously recorded evidence (101 unit tests passed after fixes on an earlier snapshot) is retained as historical evidence in `Documents/VERIFICATION_2026-11-19.md` and is not deleted.

---

## 5. Security validation

| Check | Result |
|-------|--------|
| Passwords stored as Werkzeug scrypt hashes, never returned in responses | PASS (unit tests) |
| Authenticated session + passenger ownership / admin RBAC | PASS (unit tests) |
| CSRF checks on state-changing browser requests; untrusted origins rejected | PASS (unit tests) |
| Parameterized SQL; input validation | PASS (unit tests + source review) |
| Secure cookies (HttpOnly, SameSite=Lax), HTTPS required in production | PASS (settings review) |
| Session replay / penetration testing | NOT VERIFIED |

---

## 6. Defects, deviations and outstanding work

1. **High (blocked):** Live database integration cannot be executed. MySQL is running on port 3306 but no credentials are available in this environment, and `sudo` requires a password. `database/app_permissions.sql` is prepared but unapplied. Registration/booking/payment/cancellation/admin logic is implemented and unit-tested with mocked DB; real-database validation is pending.
2. **Medium:** Backend search accepts past ISO dates although the HTML date field restricts them; server-side past-date validation is pending (SRS/UT_05 gap).
3. **Medium:** Passenger age zero is accepted by the validator but the test plan rejects zero (SRS/ST_08 gap); requirement conflict needs reconciliation.
4. **Medium:** Historical booking grouping (past vs upcoming journeys) lacks a dedicated end-to-end UI test.
5. **Evidence:** CI run URLs, coverage percentages, and final reviewer sign-off must be added when GitHub Actions executes against the final commit.
6. **Compatibility:** MariaDB was used in earlier verification; MySQL 8 production compatibility was not independently validated in this session.

---

## 7. Final assessment

**Overall result: Conditional.** All passenger and administrator workflows described in the SRS are implemented in the backend codebase (registration, auth, search, booking, simulated payment, history/status, cancellation/refunds, admin management) and are covered by 230 passing unit tests (2 skipped). The frontend build and Chromium browser tests pass. Real-database integration testing is **BLOCKED** by unavailable database credentials, so runtime correctness against MySQL cannot be confirmed in this session. The system cannot yet be marked as fully validated against the complete SRS until a database administrator applies `database/app_permissions.sql` and the live workflow checks are repeated.

**Reviewer sign-off:** Pending.  
**Independent rerun by report author:** Not performed against live DB.

---

## 8. Payment workflow (confirmed)

Payment remains **simulated**, as required. No Razorpay or real payment gateway is integrated. A passenger can confirm a held booking through a demo payment action; the backend validates ownership, booking state and seat holds, then atomically records the payment, confirms seats and booking, and queues notification records. No real money is charged. Administrator payment approval has been removed and is not reintroduced.

---

## References

- `docs/SE_SRS.md` — Requirements baseline
- `docs/SE_SAD.md` — Architecture baseline
- `docs/SE_TEST_PLAN.md` — Test plan
- `docs/SE_EVALUATION_TRACKER.md` — Evaluation checklist
- `Documents/VERIFICATION_2026-11-19.md` — Earlier verification notes (retained as historical evidence)
- `database/schema.sql` — Database schema
- `database/app_permissions.sql` — Required DB grants (unapplied, blocked)
- `docs/test-reports/` — Test logs and coverage reports
## 9. Final evidence reconciliation (2026-11-19)

- The committed unit-test log shows **232 executed, 230 passed, 2 skipped, zero failures/errors**, per the reported skipped count. The previous phrase “232 passed” overstated successful executions.
- Frontend build and **three Chromium smoke tests** were reported successful. This is **not a completed cross-browser validation**; Firefox, Edge and WebKit remain not run.
- GitHub Actions has not been verified against the final evaluation branch. The available commit-workflow query checks pull-request-triggered runs only and returned none; push-triggered runs may still exist.
- Real MySQL validation and performance testing remain excluded from this follow-up at the project owner's request, **not passed**.
- Outstanding requirement mismatches (past search dates and passenger age zero), actual demo recordings/screenshots, reviewer approvals, and final sign-off remain open.
