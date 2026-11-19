# SE mini-project final evaluation tracker
**Project:** Railway Reservation System | **Evidence status:** audit checklist; unchecked means not verified, not necessarily absent.

The supplied evaluation checklist and FAQ prioritize SDLC traceability, individual contributions, diagrams, test execution, final reports and sprint videos. The supplied ATM templates are examples only; railway-specific SRS, SAD and STP baselines are linked below.

## Part 1 — Requirements and design
- [x] Railway-specific SRS baseline: [SE_SRS.md](SE_SRS.md) (20 FRs, 5 NFRs, 2 security objectives, 5 security requirements, 2 use-case diagrams and RTM).
- [x] Railway-specific SAD baseline: [SE_SAD.md](SE_SAD.md) (component diagram, security architecture, 2 sequence diagrams and API interfaces).
- [x] Railway-specific Test Plan: [SE_TEST_PLAN.md](SE_TEST_PLAN.md) (14 planned test cases, security validation and SRS traceability).
- [ ] Confirm baseline documents against the **originally submitted** SRS/SAD/Test Plan, and log any deviations. These files are a current-state baseline, not proof the original submissions matched.
- [ ] Review/approve final document versions and capture actual sign-off.

## Part 2 — GitHub Agile and sprint evidence
- [ ] Verify linked GitHub Project board and Sprint 1 / Sprint 2 fields.
- [ ] Verify all stories have story points, assignees and sprint assignments.
- [ ] Verify PR author matches assigned contributor; repository owner reviews and merges are recorded. A merged PR is not automatically evidence of formal review.
- [ ] Verify GitHub Actions result for the **final** main commit.
- [ ] Add Sprint 1 one-minute demonstration video (recorded by the team).
- [ ] Add Sprint 2 two-minute demonstration video (recorded by the team).
- [ ] Record development freeze commit SHA and freeze decision.
- [ ] Document requirement/design changes between baseline and final implementation.

## Part 3 — Testing and reports
- [ ] Execute the final backend unit test suite and preserve full log.
- [ ] Execute frontend build and cross-browser suite and preserve full log.
- [ ] Execute real MySQL integration/system scenarios on a disposable database.
- [ ] Execute performance benchmark with representative data and record P95.
- [ ] Generate **Unit Test Report**: commit, environment, command, counts, failures and CI link.
- [ ] Generate **System Validation Report**: test case IDs, actual outcomes, screenshots and defect IDs.
- [ ] Generate **Code Coverage Report**: coverage tool output and source revision.
- [ ] Generate **Branch Coverage Report**: run coverage.py with `--branch` and record measured branch coverage.
- [ ] Finalize defect log, test summary and RTM statuses.

### Evidence record template
| Item | Commit SHA | Environment / command | Observed result | Evidence link | Owner |
|---|---|---|---|---|---|
| Backend unit tests | TBD | `uv run --active python -m unittest discover -s backend/tests -v` | NOT YET RECORDED | TBD | TBD |
| Browser tests | TBD | `cd frontend && npx playwright test` | NOT YET RECORDED | TBD | TBD |
| Database system tests | TBD | Disposable MySQL environment | NOT YET RECORDED | TBD | TBD |
| Line/branch coverage | TBD | `coverage run --branch ...` | NOT YET RECORDED | TBD | TBD |
| Train search performance | TBD | `scripts/benchmark_train_search.py` | NOT YET RECORDED | TBD | TBD |

## Part 4 — Final demonstration and viva
- [ ] Demonstrate passenger search → booking → simulated payment → status → cancellation.
- [ ] Demonstrate administrator management and authorization rejection.
- [ ] Explain transactions, row locks, idempotency, session security, layered architecture and test limitations.
- [ ] Each team member identifies assigned stories, commits, PRs, reviews and story points.
- [ ] Explain Sprint 1/Sprint 2 planning and documented scope changes.

## Explicit project limitations
Payment confirmation is simulated; refunds are tracked as pending obligations, not paid through a bank; notifications are queued but not sent through an external provider. Availability is a target, not a measured SLA. Mocked unit tests do not prove live database correctness. Do not fabricate test metrics, video evidence, review records or approvals.

## References
- [SRS](SE_SRS.md)
- [SAD](SE_SAD.md)
- [Test Plan](SE_TEST_PLAN.md)
- [Existing project documentation](PROJECT_DOCUMENTATION.md)
- [Architecture decisions](ARCHITECTURE_DECISIONS.md)

## Verification notes (2026-11-18)
- Checked PR review submissions for #72, #79, #80, #81, #87, #88 and #89 using GitHub. PRs #72, #80, #81, #87, #88 and #89 had **zero formal review submissions** in the returned review records. PR #79 had one `CHANGES_REQUESTED` review; this is not an approval. Existing merges must not be presented as formally approved unless separate review evidence exists.
- GitHub Actions workflow `.github/workflows/tests.yml` was updated in the evaluation PR to run `coverage run --branch`, save the verbose unit-test log, generate text/JSON/XML coverage reports, and upload them as a GitHub Actions artifact named `unit-and-coverage-reports`. The workflow must execute successfully before the results can be marked complete.
- The GitHub connector did not return a pull-request workflow run for the current documentation branch during this check. No coverage percentage, test count or pass result is asserted.
- Local checkout of the repository was blocked by unavailable DNS resolution for `github.com`. Therefore no local test suite or real MySQL system validation was executed in this session.
- GitHub Project board fields and story-point coverage remain unverified. Sprint videos require an actual recording of the working application and cannot be generated from source code alone.

### CI report retrieval after PR execution
1. Open the **Actions** tab and select the run for this PR's head commit.
2. Confirm all steps passed, including the coverage command.
3. Download the `unit-and-coverage-reports` artifact.
4. Inspect `unit-test.log`, `coverage-summary.txt`, `coverage.json` and `coverage.xml`.
5. Copy the measured counts and coverage percentages into the final test summary; attach the exact run URL and commit SHA.
