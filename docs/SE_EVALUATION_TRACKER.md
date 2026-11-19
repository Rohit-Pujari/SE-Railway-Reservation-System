# SE mini-project final evaluation tracker
**Project:** Railway Reservation System | **Evidence status:** audit checklist; checked items are verified against executed results.  
**Commit SHA:** `8bc9b10` (merge of `feature/demo-seed-data` into `main`) plus evaluation fixes on branch `se-evaluation-complete`.

---

## Part 1 — Requirements and design

- [x] Railway-specific SRS baseline: [SE_SRS.md](SE_SRS.md) (20 FRs, 5 NFRs, 2 security objectives, 5 security requirements, 2 use-case diagrams and RTM).
- [x] Railway-specific SAD baseline: [SE_SAD.md](SE_SAD.md) (component diagram, security architecture, 2 sequence diagrams and API interfaces).
- [x] Railway-specific Test Plan: [SE_TEST_PLAN.md](SE_TEST_PLAN.md) (14 planned test cases, security validation and SRS traceability).
- [x] Confirm baseline documents against the currently implemented code; deviations logged in `docs/SYSTEM_VALIDATION_REPORT.md` §6 and §8 below. Original SRS/SAD PDFs describe a larger product; the current implementation is a scoped subset with simulated payments.
- [ ] Review/approve final document versions and capture actual sign-off. (Pending — no formal review evidence exists for prior merges; see verification notes.)

---

## Part 2 — GitHub Agile and sprint evidence

- [ ] Verify linked GitHub Project board and Sprint 1 / Sprint 2 fields. (Not accessible in this session — no GitHub CLI/project board data available locally.)
- [ ] Verify all stories have story points, assignees and sprint assignments. (Not verifiable locally.)
- [ ] Verify PR author matches assigned contributor; repository owner reviews and merges are recorded. A merged PR is not automatically evidence of formal review. (Prior verification: PRs #72, #80, #81, #87, #88 and #89 had zero formal review submissions; PR #79 had one CHANGES_REQUESTED.)
- [ ] Verify GitHub Actions result for the final main commit. (Workflow `tests.yml` reproduced locally; see Part 3 and CI verification notes below. Remote Actions not accessible in this session.)
- [ ] Add Sprint 1 one-minute demonstration video (recorded by the team). (Not created — videos must be recorded from the actual working application.)
- [ ] Add Sprint 2 two-minute demonstration video (recorded by the team). (Not created.)
- [ ] Record development freeze commit SHA and freeze decision. (Not yet frozen.)
- [x] Document known requirement/design changes between baseline and final implementation (see `docs/SYSTEM_VALIDATION_REPORT.md` §6–§8; formal baseline approval pending).

---

## Part 3 — Testing and reports

- [x] Execute the final backend unit test suite and preserve full log.
  - Command: `uv run --active python -m unittest discover -s backend/tests -p "test_*.py" -v`
  - Result: **232 tests run, 230 passed, 0 failed, 0 errors, 2 skipped**
  - Log: `docs/test-reports/unit-test.log`
  - Fixes applied: `test_architecture.py` URL-pattern count (36→37); `test_booking_flow.py` and `test_booking_cancellation_flow.py` mock user dicts now include `"role": "PASSENGER"` required by the login view.
- [ ] Execute frontend build and full cross-browser suite and preserve full log (frontend build and Chromium smoke tests completed; Firefox, Edge, and WebKit not executed).
  - `npm ci` and `npm run build` succeed.
  - `npx playwright test --project=Chrome`: **3 passed** (application loads, responsive layout, keyboard accessibility).
  - Other browsers (Firefox, Edge, Safari) not installed in this environment.
- [ ] Execute real MySQL integration/system scenarios on a disposable database.
  - **BLOCKED**: MySQL listens on port 3306 but no credentials are available; `root` and `railway_app` both denied; `sudo` unavailable without password. `database/app_permissions.sql` is prepared but unapplied.
- [ ] Execute performance benchmark with representative data and record P95.
  - **BLOCKED**: Requires configured MySQL database with representative records; no credentials available.
- [ ] Generate **Unit Test Report** with final commit and CI link (local test log and counts are recorded; final CI link pending).
  - Commit: `8bc9b10` + fixes on `se-evaluation-complete`. Environment: Python 3.11.18, uv, Linux. Counts: 230 passed / 2 skipped / 0 failed. CI link: pending (GitHub Actions not accessible locally).
- [ ] Finalize **System Validation Report** with live screenshots and final reviewer sign-off (report drafted; actual screenshots/sign-off pending).
  - `docs/SYSTEM_VALIDATION_REPORT.md` updated (SV-01 through SV-18 with PASS / IMPLEMENTED / BLOCKED / NOT VERIFIED statuses).
- [x] Generate **Code Coverage Report**: coverage tool output and source revision.
  - `docs/test-reports/coverage-summary.txt`, `coverage.json`, `coverage.xml`.
  - Line coverage: **63%** (2176 statements, 754 missed). Branch coverage: **56%** (624 branches, 348 covered, 276 missing, 116 partial).
- [x] Generate **Branch Coverage Report**: run coverage.py with `--branch` and record measured branch coverage.
  - Branch coverage: **56%**. Report in `docs/test-reports/`.
- [ ] Finalize defect log, test summary and RTM statuses.
  - Defect log in `docs/SYSTEM_VALIDATION_REPORT.md` §6. RTM in `docs/SE_SRS.md` §8.

### Evidence record template

| Item | Commit SHA | Environment / command | Observed result | Evidence link | Owner |
|------|------------|----------------------|-----------------|---------------|-------|
| Backend unit tests | `8bc9b10` + fixes | Python 3.11.18, `uv run --active python -m unittest discover -s backend/tests -p "test_*.py" -v` | 230 passed, 0 failed, 0 errors, 2 skipped | `docs/test-reports/unit-test.log` | Developer |
| Browser tests | `8bc9b10` + fixes | Node 26.13.1, `npx playwright test --project=Chrome` | 3 passed | Playwright output (local run) | Developer |
| Database system tests | TBD | Disposable MySQL environment | **BLOCKED** — no DB credentials | N/A | DBA required |
| Line/branch coverage | `8bc9b10` + fixes | `coverage run --branch --source=backend/app,backend/config ...` | 63% line, 56% branch | `docs/test-reports/coverage-*` | Developer |
| Train search performance | TBD | `scripts/benchmark_train_search.py` | **BLOCKED** — no DB credentials | N/A | DBA required |

---

## Part 4 — Final demonstration and viva

- [ ] Demonstrate passenger search → booking → simulated payment → status → cancellation. (Prepared as checklist below; cannot execute without live DB.)
- [ ] Demonstrate administrator management and authorization rejection. (Prepared as checklist below; cannot execute without live DB.)
- [ ] Explain transactions, row locks, idempotency, session security, layered architecture and test limitations. (Material prepared below.)
- [ ] Each team member identifies assigned stories, commits, PRs, reviews and story points. (Not verifiable locally.)
- [ ] Explain Sprint 1/Sprint 2 planning and documented scope changes. (Not verifiable locally.)

### Demonstration checklist (to be executed against a live deployment)

1. **Registration and login:** Register a new passenger, log in, verify session, log out.
2. **Train search:** Search by origin, destination, date, class; verify results returned.
3. **Booking and PNR:** Enter passenger details, create booking, verify PNR and seat holds.
4. **Simulated payment:** Confirm payment, verify booking status becomes CONFIRMED.
5. **Booking status/history:** Look up by PNR, verify only owner's bookings appear.
6. **Cancellation:** Cancel a booking, verify seats released and refund records created.
7. **Administrator operations:** Admin login, dashboard, train/station/route/schedule management.
8. **Unauthorized-access rejection:** Passenger attempts admin endpoint (expect 403); anonymous attempts booking (expect 401).

### Viva preparation material

- **Iterative and incremental development:** Features delivered in sprints via branches/issues/PRs; each increment adds tested functionality (registration, auth, search, booking, payment, cancellation, admin).
- **Agile-style workflow:** Issue tracking, story points, sprint assignments, pull requests, code review, regression testing on each PR.
- **Layered modular-monolith architecture:** React presentation → Django API boundary → feature services (booking, payment, cancellation, search, admin) → MySQL InnoDB persistence. One database, transaction boundaries within services.
- **CI using GitHub Actions:** `.github/workflows/tests.yml` runs Python install, React build, Playwright, compileall, Django checks, unit tests with coverage, and artifact upload. Not continuous deployment.
- **Git branching and PRs:** Feature branches merged into main via pull requests; merge commits visible in history.
- **Requirements traceability:** RTM in `docs/SE_SRS.md` §8 maps FRs to modules, APIs and test cases.
- **Testing levels:** Unit (mocked DB), integration (API endpoints), system (browser flows), regression (full suite on each change).
- **Database transactions and row locks:** `create_booking`, `confirm_booking_payment`, `cancel_booking` each run in one InnoDB transaction with deterministic seat-lock ordering (`FOR UPDATE` on schedule_seats in ID order).
- **Idempotency:** Booking idempotency key prevents duplicate bookings on retry; payment replay returns existing confirmation without duplicate charges.
- **CSRF and RBAC:** Django CSRF middleware on all state-changing endpoints; session role checks (`PASSENGER`/`ADMIN`); `_user_id` and `_admin_required` decorators.
- **Known limitations:** Simulated payments (no real gateway), queued notifications (no delivery), pending refunds (no bank settlement), no production failover, no measured SLA, mocked unit tests don't prove live DB correctness.

---

## Explicit project limitations

Payment confirmation is simulated; refunds are tracked as pending obligations, not paid through a bank; notifications are queued but not sent through an external provider. Availability is a target, not a measured SLA. Mocked unit tests do not prove live database correctness. Do not fabricate test metrics, video evidence, review records or approvals.

---

## References

- [SRS](SE_SRS.md)
- [SAD](SE_SAD.md)
- [Test Plan](SE_TEST_PLAN.md)
- [Existing project documentation](PROJECT_DOCUMENTATION.md)
- [Architecture decisions](ARCHITECTURE_DECISIONS.md)
- [System Validation Report](SYSTEM_VALIDATION_REPORT.md)
- [Test reports](test-reports/)
## Final evidence reconciliation (2026-11-19)
- The saved `unit-test.log` ends with `Ran 232 tests` and `OK`; the evaluation report identifies two skips. Report as **230 passed, 2 skipped**, not 232 passed.
- The React build and three Chromium Playwright checks were reported locally. This does **not** establish Firefox, Edge, or WebKit compatibility.
- The GitHub connector returned no pull-request-triggered workflow runs for commits `167d56e` or `8bc9b10`. This is **not proof that no push-triggered runs exist**, because that query excludes them. A GitHub Actions run URL and outcome are still required.
- A merged pull request, sprint board, actual sprint recordings, reviewer approvals, live browser screenshots, and final sign-off are distinct evidence items; do not mark them complete without records.
- Outstanding code/requirements discrepancies: server-side past-date search validation and passenger age-zero handling. The current branch did not fix either; resolve them in a separate verified implementation change.
