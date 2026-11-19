# Software Test Plan (STP)

## 1. Introduction
Purpose: verify the SRS functional, non-functional and security requirements through unit, API, system, browser and acceptance testing. Scope: passenger registration, authentication, search, booking, simulated payment, cancellation, admin management and recovery. Exclusions: real payment settlement, real refund transfers, provider email/SMS delivery and production availability certification. Reference: `Documents/Software_Requirements_Specification.md`, `Documents/Software_Architecture_and_Design.md`.

## 2. Test items
React frontend, Django API and services, MySQL schema and transactional behavior, session/CSRF protection, admin controls, CI pipeline and recovery procedures.

## 3. Features to be tested
SRS F-001–020; NF-001–005; SR-001–005. High-priority scenarios: authorization, search and inventory, atomic booking and PNR creation, payment confirmation, cancellation/refund persistence, administrator permissions and safe database outage handling.

## 4. Features not to be tested
Real gateway settlement, actual SMS/email delivery, bank-side refund settlement, hardware devices, production failover and long-term uptime are not implemented or are out of scope. Do not record them as passed.

## 5. Test approach / strategy
- **Unit:** service validation, fare/refund calculations, error branches and rollback behavior using isolated/mocked dependencies.
- **Integration:** run API and database operations on a dedicated disposable MySQL instance to verify schema, constraints and transaction isolation.
- **System:** execute complete passenger and admin journeys via browser/API.
- **Regression:** run backend suite, frontend production build and browser suite on PRs.
- **Performance:** execute train-search benchmark with representative MySQL data and document P95 latency.
- **Acceptance:** demonstrate critical use cases and verify evidence against SRS IDs.

Entry: stable build, configured test database, dummy accounts/trains/schedules and clean test data. Exit: all planned critical cases executed; zero open critical defects; any unexecuted cases explicitly marked; deviations approved. Do not infer test pass from source code alone.

### 5.1 Security validation
Verify password hashing and redaction; passenger ownership and admin RBAC; CSRF rejection; input validation and SQL parameterization; production cookie/HTTPS configuration. Test negative/unauthorized paths without using real customer data.

## 6. Test environment
Python 3.10+, Node.js 20+, MySQL 8.0.16+, React/Vite and Django REST Framework. Tools: Python `unittest`, `compileall`, npm build, Playwright, train-search benchmark, GitHub Actions. Test data: dummy users (passenger/admin), stations, routes, schedules, fares, seats, bookings. Automated unit tests use mocked database calls; separately run database integration tests for actual SQL correctness.

## 7. Test schedule
Design and traceability: before freeze. Automated regression: each PR and final release candidate. Integration and performance tests: final evaluation environment. Manual acceptance and video capture: after stable release candidate. Actual dates and assignees are to be recorded by the team.

## 8. Test deliverables
This plan, test cases and scripts, test dataset, CI execution logs, defect log, unit/system validation report, line and branch coverage reports, final test summary and sprint videos. See `docs/SE_EVALUATION_TRACKER.md` for evidence requirements.

## 9. Roles and responsibilities
Developer: implement and unit-test assigned features. Reviewer/repository owner: review PRs and approve merges. Test owner: execute acceptance and collect logs. Team: maintain traceability, defect register, sprint videos and final sign-off. Individual names must be filled from the actual project board.

## 10. Risks and mitigation
Mocked database tests can miss SQL integration failures: use disposable MySQL integration environment. Browser automation may not prove accessibility: supplement manual checks. Concurrent booking races are hard to reproduce: run deterministic lock/rollback tests. CI pass may be stale: attach logs from the exact final commit.

## 11. Assumptions and dependencies
MySQL schema and required migration scripts are installed; dummy data is available; production-like environment is isolated from real users; external providers remain simulated.

## 12. Suspension and resumption
Suspend if test database unavailable, critical booking corruption occurs or a blocking build failure prevents core scenarios. Resume after environment recovery, defect fix and successful smoke test.

## 13. Test cases and requirements traceability
| ID | SRS reference | Test procedure | Expected result | Execution |
|---|---|---|---|---|
| TC-01 | F-001, SR-001 | Register valid and duplicate/invalid passenger accounts | Valid account created with hashed password; invalid rejected | Pending final-run evidence |
| TC-02 | F-002–003, SR-002–003 | Login/logout; access admin API as passenger; mutate without CSRF | Valid session works; forbidden/CSRF requests rejected | Pending final-run evidence |
| TC-03 | F-004–005 | Search by stations/date and invalid input | Matching schedules returned; bad input rejected | Pending final-run evidence |
| TC-04 | F-006, F-010 | Hold seat, query availability, attempt overlapping allocation | Held/confirmed seat unavailable; no double booking | Pending final-run evidence |
| TC-05 | F-007–009, NF-003 | Book travelers and inspect PNR, fare, allocation; inject write failure | All rows commit or all roll back | Pending final-run evidence |
| TC-06 | F-009–010 | Retry identical booking request and conflicting idempotency key | No duplicate booking; conflict rejected | Pending final-run evidence |
| TC-07 | F-011, F-015 | Pay held booking twice; retry expired hold | Single simulated confirmation; expired hold rejected | Pending final-run evidence |
| TC-08 | F-012, SR-002 | Query own and another user's booking history/status | Only authorized records returned | Pending final-run evidence |
| TC-09 | F-013–014 | Cancel confirmed booking and inspect allocations/refund rows | Seats released, cancellation and pending refund recorded atomically | Pending final-run evidence |
| TC-10 | F-016–019 | Use admin train/route/schedule/seat endpoints as admin/passenger | Authorized updates succeed; unauthorized denied | Pending final-run evidence |
| TC-11 | F-020, NF-002 | Stop test database, call health endpoint, restart and retry | 503 during outage; recovery on reconnect | Pending final-run evidence |
| TC-12 | NF-004–005 | Run frontend build and Playwright browser suite | Build and supported browser smoke checks pass | Pending final-run evidence |
| TC-13 | SR-004–005 | Review SQL parameters and production settings | No interpolated user values; secure settings documented | Pending review |
| TC-14 | NF-001 | Benchmark train search with representative data | P95 ≤ 3 seconds | Pending measurement |

## 14. Test metrics and reporting
Record total/planned/executed/passed/failed/skipped test cases, high-priority requirement coverage, open defects by severity, line coverage and branch coverage. Evidence must include commit SHA, command, environment, timestamp, outcome and links to CI artifacts. **No execution counts or coverage percentages are asserted in this plan.**


QA lead: __________  Developer/reviewer: __________  Product owner/evaluator: __________

## 16. Commands
```bash
cd frontend && npm ci && npm run build && cd ..
uv run --active python -m compileall -q backend
uv run --active python -m unittest discover -s backend/tests -v
# From frontend after installing Playwright dependencies:
npx playwright test
# After installing coverage.py into the active test environment:
uv run --active python -m coverage run --branch -m unittest discover -s backend/tests
uv run --active python -m coverage report -m
uv run --active python -m coverage json -o docs/coverage.json
# Against a configured disposable MySQL database with representative records:
uv run python scripts/benchmark_train_search.py --source 1 --destination 2 --date YYYY-MM-DD
```
