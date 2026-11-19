# Application verification — 19 November 2026

Overall verdict: **CHANGES REQUIRED for the complete SRS; authentication defect fixed and verified.**

## Requirements consulted

- `Documents/SRS_RAILWAY_RESERVATION_SYSTEM.pdf`, Functional Requirements 1–24 and nonfunctional requirements.
- `Documents/Test_Plan_Railway_Reservation_System.pdf`, UC1–UC7 and its unit/integration/system cases.
- `Documents/Railway reservation system _Use_Case_Flow.pdf`, booking, cancellation and administrator flows.
- `database/schema.sql`, `database/SCHEMA_REVIEW.md`, README, active Django routes and React screens.

The PDFs describe a larger product than the current implementation. Earlier user instructions narrowed the feature scope and replaced a gateway with manual admin approval. Those intentional differences are recorded here; PDF “Pass/As expected” entries are not execution evidence.

## Confirmed defects and corrections

1. **High — browser POSTs were rejected by CSRF.** Requests through Vite on 5173 with a real Origin header returned HTTP 403 for registration. Direct API checks without Origin misleadingly passed. `run-dev.sh` now supplies explicit local frontend trusted origins and starts Vite with `--strictPort`, preventing an unnoticed port change. CSRF stays enabled. Regression checks require a valid token and reject untrusted origins. The live launcher was restarted and actual Chromium login/logout checks passed on 5173.
2. **High — payment request SQL failed on MariaDB.** `payment_approval.py` used the reserved SQL identifier `current_time` as an unquoted alias. Actual payment requests returned HTTP 503 even with valid inventory. Renamed the alias to `db_now`; full payment/rejection/retry/approval integration passed afterwards.
3. **High — live application account lacks UPDATE privileges.** Read-only inspection confirmed `railway_app`@`127.0.0.1` has SELECT and INSERT only. Admin approval/rejection and fare updates require UPDATE. Prepared `database/app_permissions.sql` with grants on four runtime tables only. Applying it remains **blocked by sudo requiring the user's password**. No live grants were changed. Registration has the INSERT privilege it needs.
4. **Medium — payment screen did not refresh an admin's decision.** Added “Check payment status” to fetch owned ticket history and expose a rejected request for retry or display confirmation. API retry and history checks passed; the new refresh button itself has build verification only.
5. **Medium — tests described the old simulated payment endpoint.** Three tests patched a removed symbol and the architecture test assumed an obsolete fixed route count. Updated them to assert request-for-review semantics, server ownership of amount/outcome, and admin authorization. Legacy payment-service tests remain in the suite but do not prove the active admin-review API works; that path was also exercised on MariaDB.

## Execution evidence

Personal database was not used for write tests. A separate MariaDB server ran on port 13316 with its own `/tmp/railway-verification-db` data directory; the repository schema was imported unchanged. The seeder created 36 stations, 180 generated trains and 5,400 November schedules there. A separate Django/Vite launcher ran on ports 8001/5175. These checks used committed transactions, not mocks or rollback substitutions for successful registration/booking.

| Check | Actual result |
| --- | --- |
| `uv run --active python -m unittest discover -s backend/tests -v` | 101 passed after fixes; initial run had 1 failure and 3 errors |
| Chromium through Vite, isolated DB | Registration 201 and committed account; passenger login/logout 200; unified admin login/logout 200 |
| Chromium booking screens | Source excluded from destination; results stay below search; traveler form submitted; booking 201; payment request 202; admin approval 200 |
| Chromium on restarted live 5173 | Existing passenger/admin login and logout 200; duplicate registration 409; no new personal DB records |
| Search/classes/fare/availability against MariaDB | Matching services and fares returned; a seat hold decreased available inventory by one |
| Booking idempotency | Repeating identical key returned same booking/PNR, no extra allocation |
| Payment ownership and authorization | Other passenger's payment request rejected; passenger could not approve payment or access admin queue |
| Rejection then retry | Failed request kept booking pending; subsequent request approved and booking confirmed |
| Repeated approval | Rejected with 409 |
| Ticket history | Confirmed ticket includes seats; another account cannot see it |
| Concurrent booking | Two requests for six seats each on eight-seat service: one 201, one 409, two seats remain |
| Expired hold | Availability restored; payment submission rejected |
| Partial-write failure | Injected failure at seat-allocation insert rolled back earlier booking/passenger inserts; no booking remained for that key |
| Build / Django checks | React production build and Django system check passed |

Temporary executable checks used during this session: `/tmp/railway-browser.mjs`, `/tmp/railway-live-browser.mjs`, `/tmp/railway-workflows.py`, `/tmp/railway-rollback.py`. They are session artifacts and use the dedicated verification ports. Test output is in `/tmp/railway-tests-after.log`. Chromium used a separate temporary profile, not the user's cookies.

## Requirements coverage and remaining gaps

| Requirement | Verdict / evidence |
| --- | --- |
| FR1–2 registration/login/logout | PASS in isolated browser + committed DB; existing-account login/logout also passed on live app after restart |
| FR3–7 search/results/seats/class | PASS within tested route/date/class scope; arbitrary statewide timetable correctness not claimed |
| FR8–9 passengers/fare | Valid multi-passenger flow passed and validation/unit tests passed; live fare recalculation needs UPDATE grant |
| FR10–12 booking/PNR/confirmation | PASS in isolated DB including concurrent allocation; live payment confirmation blocked by UPDATE grant |
| FR13 previous/upcoming bookings | Upcoming confirmed records and owner isolation verified; historical grouping code reviewed, not a separate past-journey UI test |
| FR14–16 cancellation, release, refunds | NOT IMPLEMENTED in active API/UI; tables alone do not implement these requirements |
| FR17 booking/cancellation status | Booking/payment status available; cancellation status missing |
| FR18–21 train CRUD, route/schedule management | NOT IMPLEMENTED in active API/UI; seeding is not administrator management |
| FR22 administrator booking view | Pending payment queue only; comprehensive booking administration missing |
| FR23 administrator seat management | NOT IMPLEMENTED |
| FR24 booking/cancellation records | Booking persistence verified; cancellation flow missing |
| Gateway/card/UPI cases in UC4 | Replaced by manual admin approval at user's request; no real or sandbox gateway tested |
| Test plan UT_01 username format | Docs expect 5–20 character username, current schema/UI uses full name and email; requirement conflict needs reconciliation |
| Test plan UT_05 past journey date | HTML date field prevents past dates, but backend search validator accepts a valid ISO date in the past; server-side requirement gap |
| Test plan ST_08 age zero | Plan rejects zero; current passenger validator accepts 0–120. Requirement conflict remains |
| Nonfunctional performance/scale/recovery | Two-request concurrency tested; broad load, stress, crash recovery and multiple browser engines NOT VERIFIED |

Additional limitations: real MySQL 8 was not available; execution used local MariaDB and the unchanged MySQL-targeted schema. Manual approval must happen before the 15-minute seat hold expires. Synthetic Karnataka connectors are not real official railway services. Changing source account names does not change existing live accounts until the seed migration is run. Signed-cookie sessions support browser logout but have no server-side revocation list for replayed stolen cookies.

## Required local action

Run `sudo mariadb < database/app_permissions.sql` to permit the implemented payment/fare updates. The auth origin fix is already active on the restarted local app; future launches should use `./run-dev.sh`. Do not run `schema.sql` over the existing personal database.
