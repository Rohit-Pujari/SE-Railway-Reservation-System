# SE mini-project final evaluation tracker
**Project:** Railway Reservation System | **Evidence status:** audit checklist; checked items are verified against executed results.  
**Commit SHA:** `167d56e` (branch `se-evaluation-complete`, PR #92)

---

## Part 1 — Requirements and design

- [x] Railway-specific SRS baseline: [SE_SRS.md](SE_SRS.md) (20 FRs, 5 NFRs, 2 security objectives, 5 security requirements, 2 use-case diagrams and RTM).
- [x] Railway-specific SAD baseline: [SE_SAD.md](SE_SAD.md) (component diagram, security architecture, 2 sequence diagrams and API interfaces).
- [x] Railway-specific Test Plan: [SE_TEST_PLAN.md](SE_TEST_PLAN.md) (14 planned test cases, security validation and SRS traceability).
- [x] Confirm baseline documents against the currently implemented code; deviations logged in `docs/SYSTEM_VALIDATION_REPORT.md` §6–§7. Original SRS/SAD PDFs describe a larger product; the current implementation is a scoped subset with simulated payments.
- [ ] Review/approve final document versions and capture actual sign-off. (Pending — no formal review evidence exists for prior merges; see verification notes.)
- [x] Past-date journey validation added to `train_search.py`, `seat_availability.py`, `booking.py` (defect fixed + tested).
- [x] Passenger age validation changed from 0–120 to 1–120 in `passenger_details.py` (defect fixed + tested).

---

## Part 2 — GitHub Agile and sprint evidence

- [ ] Verify linked GitHub Project board and Sprint 1 / Sprint 2 fields. (Not accessible in this session — no GitHub CLI/project board data available locally.)
- [ ] Verify all stories have story points, assignees and sprint assignments. (Not verifiable locally.)
- [ ] Verify PR author matches assigned contributor; repository owner reviews and merges are recorded. A merged PR is not automatically evidence of formal review. (Prior verification: PRs #72, #80, #81, #87, #88 and #89 had zero formal review submissions; PR #79 had one CHANGES_REQUESTED.)
- [ ] Verify GitHub Actions result for the final main commit. (Workflow `tests.yml` reproduced locally; all commands pass. Remote Actions not accessible in this session.)
- [ ] Add Sprint 1 one-minute demonstration video (recorded by the team). (Not created — videos must be recorded from the actual working application.)
- [ ] Add Sprint 2 two-minute demonstration video (recorded by the team). (Not created.)
- [ ] Record development freeze commit SHA and freeze decision. (Not yet frozen.)
- [x] Document known requirement/design changes between baseline and final implementation (see `docs/SYSTEM_VALIDATION_REPORT.md` §6–§7; formal baseline approval pending).

---

## Part 3 — Testing and reports

- [x] Execute the final backend unit test suite and preserve full log.
  - Command: `uv run --active python -m unittest discover -s backend/tests -p "test_*.py" -v`
  - Result: **272 tests run, 272 passed, 0 failed, 0 errors, 0 skipped**
  - Log: `docs/test-reports/unit-test.log`
- [x] Execute frontend build and full cross-browser suite and preserve full log.
  - `npm ci` and `npm run build` succeed.
  - `npx playwright test --project=Chrome --project=Firefox`: **6 passed** (3 per browser).
  - Safari/WebKit: **BLOCKED** — missing system dependencies (libicu74, libxml2), no sudo access.
- [ ] Execute real MySQL integration/system scenarios on a disposable database.
  - **EXCLUDED** (per project owner instruction) — no DB credentials available.
- [ ] Execute performance benchmark with representative data and record P95.
  - **EXCLUDED** (per project owner instruction) — no DB credentials available.
- [x] Generate **Unit Test Report** with final commit and CI link.
  - Commit: `167d56e`. Environment: Python 3.11.18, uv, Linux. Counts: 272 passed / 0 failed / 0 skipped. CI link: pending (GitHub Actions not accessible locally).
- [x] Finalize **System Validation Report** with actual outcomes.
  - `docs/SYSTEM_VALIDATION_REPORT.md` updated (SV-01 through SV-18 with PASS / IMPLEMENTED / EXCLUDED / BLOCKED statuses).
- [x] Generate **Code Coverage Report**: coverage tool output and source revision.
  - `docs/test-reports/coverage-summary.txt`, `coverage.json`, `coverage.xml`.
  - Line coverage: **76.2%** (2185 statements, 473 missed). Branch coverage: **68.9%** (630 branches, ~434 covered).
- [x] Generate **Branch Coverage Report**: run coverage.py with `--branch` and record measured branch coverage.
  - Branch coverage: **68.9%**. Report in `docs/test-reports/`.
- [x] Finalize defect log, test summary and RTM statuses.
  - Defect log in `docs/SYSTEM_VALIDATION_REPORT.md` §6–§7. RTM in `docs/SE_SRS.md` §8.

### Evidence record template

| Item | Commit SHA | Environment / command | Observed result | Evidence link | Owner |
|------|------------|----------------------|-----------------|---------------|-------|
| Backend unit tests | `167d56e` | Python 3.11.18, `uv run --active python -m unittest discover -s backend/tests -p "test_*.py" -v` | 272 passed, 0 failed, 0 errors, 0 skipped | `docs/test-reports/unit-test.log` | Developer |
| Browser tests | `167d56e` | Node 26.13.1, `npx playwright test --project=Chrome --project=Firefox` | 6 passed | Playwright output (local run) | Developer |
| Database system tests | EXCLUDED | Disposable MySQL environment | EXCLUDED — no DB credentials | N/A | DBA required |
| Line/branch coverage | `167d56e` | `coverage run --branch --source=backend/app,backend/config ...` | 76.2% line, 68.9% branch | `docs/test-reports/coverage-*` | Developer |
| Train search performance | EXCLUDED | `scripts/benchmark_train_search.py` | EXCLUDED — no DB credentials | N/A | DBA required |

---

## Part 4 — Final demonstration and viva

- [x] Demonstration package prepared under `docs/demo/` (scripts, viva questions, architecture explanation, CI explanation, testing explanation, database transaction explanation, known limitations).
- [ ] Demonstrate passenger search → booking → simulated payment → status → cancellation. (Prepared as script; cannot execute without live DB.)
- [ ] Demonstrate administrator management and authorization rejection. (Prepared as script; cannot execute without live DB.)
- [ ] Explain transactions, row locks, idempotency, session security, layered architecture and test limitations. (Material in `docs/demo/`.)
- [ ] Each team member identifies assigned stories, commits, PRs, reviews and story points. (Not verifiable locally.)
- [ ] Explain Sprint 1/Sprint 2 planning and documented scope changes. (Not verifiable locally.)

---

## Explicit project limitations

Payment confirmation is simulated; refunds are tracked as pending obligations, not paid through a bank; notifications are queued but not sent through an external provider. Availability is a target, not a measured SLA. Mocked unit tests do not prove live database correctness. Do not fabricate test metrics, video evidence, review records or approvals. Real-database integration and Safari/WebKit browser tests are excluded/blocked in this evaluation.

---

## References

- [SRS](SE_SRS.md)
- [SAD](SE_SAD.md)
- [Test Plan](SE_TEST_PLAN.md)
- [Existing project documentation](PROJECT_DOCUMENTATION.md)
- [Architecture decisions](ARCHITECTURE_DECISIONS.md)
- [System Validation Report](SYSTEM_VALIDATION_REPORT.md)
- [Test reports](test-reports/)
- [Demo package](demo/)

## Final evidence reconciliation (2026-11-19)

- All 272 backend unit tests pass with 0 failures, 0 errors, 0 skipped.
- Frontend build and 6 cross-browser Playwright tests pass (Chrome + Firefox).
- Safari/WebKit blocked by missing system dependencies (libicu74, libxml2; no sudo).
- Real MySQL integration and performance benchmarking EXCLUDED per project owner instruction.
- Coverage: 76.2% line, 68.9% branch.
- GitHub Actions not verified remotely; workflow reproduced locally and all commands pass.
- Outstanding: live-database checks, Safari/WebKit, CI remote verification, reviewer sign-off, demo videos.