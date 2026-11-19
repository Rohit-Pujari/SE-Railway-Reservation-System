# Railway Reservation System — Software Test Plan (STP)
**Project:** Railway Reservation System  
**Version:** 2.0 | **Status:** Draft — pending execution and approvals  
**Date:** 19 November 2026  
**Authors:** Railway Reservation System project team

## 1. Introduction
**Purpose:** Define objectives, scope, resources, test methods, schedule, acceptance criteria, and responsibilities for verifying the Railway Reservation System against the approved SRS.

**Scope:** React/Vite passenger and administrator interface, Django REST API, MySQL/InnoDB persistence, train search, seat availability, PNR booking, simulated payment, cancellation, pending refunds, authentication and access control.

**References:** Railway_Reservation_System_SRS.pdf; Railway_Reservation_System_SAD.pdf; Railway_Reservation_System_Detailed_Test_Cases.pdf; `docs/SE_SRS.md`.

**Definitions:** STP = Software Test Plan; SRS = Software Requirements Specification; PNR = Passenger Name Record; RTM = Requirements Traceability Matrix; UAT = User Acceptance Testing; P95 = 95th percentile.

## 2. Test Items
| Item | Scope | Interface |
|---|---|---|
| Passenger authentication | Registration, sign-in, sign-out, session enforcement | React + Django |
| Search and availability | Station lookup, schedules, seat/class inventory | Django + MySQL |
| Booking and PNR | Traveler validation, fare snapshot, seat hold, idempotency | Django + MySQL |
| Simulated payment | Confirm held booking; reject expired or repeated confirmation | Django + MySQL |
| Booking history and cancellation | Ownership, cancellation, seat release, pending refund | React + Django + MySQL |
| Administrator operations | Trains, stations, routes, schedules, inventory and record inspection | React + Django + MySQL |
| Nonfunctional controls | Performance, consistency, authentication, CSRF and input validation | End-to-end |

## 3. Features to Be Tested
**Functional requirements:** RRS-F-001 through RRS-F-020, including registration, authentication, search, availability, booking, idempotency, simulated payment, history, cancellation, pending refunds, notification queue, and administrator operations.

**Nonfunctional requirements:** RRS-NF-001 through RRS-NF-005, subject to measurable targets in the SRS and environment readiness.

**Security requirements:** RRS-SR-001 through RRS-SR-005, including password protection, role and ownership enforcement, request validation, and secure session handling.

**High-risk priority:** Seat allocation consistency, duplicate booking prevention, booking ownership, cancellation atomicity and administrator authorization.

## 4. Features Not to Be Tested
Real bank/payment-gateway settlement, live monetary refunds, delivered SMS/email notifications, third-party railway inventory, and production-scale uptime certification are outside the implemented system boundary. Queue creation and simulated payment states remain in scope.

## 5. Test Approach / Strategy
**Unit testing:** Validate input rules, fare calculation, status transitions, booking validation, ownership checks and service functions with isolated dependencies.

**Integration testing:** Run against disposable MySQL 8 with migrations and seeded data. Verify transactional seat holds, concurrent requests, rollback, payment confirmation, cancellation and refund-record consistency. SQLite-only execution does not substitute for MySQL transaction testing.

**System testing:** Exercise the passenger and administrator flows through browser and HTTP API, including negative inputs, unauthorized access, expired holds, no inventory and duplicate requests.

**Acceptance testing:** Demonstrate an end-to-end booking and cancellation with known expected results and recorded evidence. Do not mark unexecuted manual cases as passed.

**Test types:** Functional, regression, boundary-value, negative, concurrency, security, compatibility, usability and performance.

**Entry criteria:** Versioned release candidate; migrations applied; seeded disposable data; stable backend and frontend; test accounts; traceable cases and reproducible scripts.

**Exit criteria:** All critical and high-priority cases executed; zero open critical defects; no unresolved seat double-booking or cross-user access; all failures documented with disposition; summary and approvals recorded. Any exceptions require explicit sign-off.

### 5.1 Security Validation
Test incorrect credentials, unauthorized API access, passenger/admin role separation, cross-user booking access, CSRF-protected state changes, invalid input and SQL injection attempts. Inspect configuration for secure cookies and HTTPS in production; configuration inspection is not equivalent to deployed penetration testing.

## 6. Test Environment
| Area | Configuration |
|---|---|
| Backend | Python 3.10+, Django / Django REST Framework |
| Frontend | Node.js 20+, React/Vite |
| Database | MySQL 8.0.16+ / InnoDB, disposable test schema |
| Automation | Python unittest / pytest as configured; Playwright browser smoke tests |
| Browsers | Chromium and Firefox; WebKit only when environment supports it |
| Data | Dummy passenger/admin accounts, stations, trains, schedules, inventory, bookings |
| Isolation | Reset database and application state between integration scenarios |

**Environment caveat:** Existing historical evidence includes unit/browser checks but does not establish that all MySQL-backed integration and manual cases were executed.

## 7. Test Schedule
| Phase | Deliverable | Timing / dependency |
|---|---|---|
| Planning | Approved STP and RTM | Before execution |
| Case design | Unit, integration and system cases | After requirement review |
| Environment setup | Disposable MySQL and seeded test data | Before integration tests |
| Unit and regression | Logs and coverage summary | Each reviewed release candidate |
| Integration and system | Execution log, screenshots and defect reports | After stable environment |
| UAT and closure | Summary report and approvals | After exit criteria |

Exact calendar dates and named owners are **to be confirmed**, not invented.

## 8. Test Deliverables
Approved test plan; detailed test cases; RTM; automation scripts; test data; environment configuration; execution logs; screenshots; defect reports; final test summary; approvals.

## 9. Roles and Responsibilities
| Role | Name | Responsibility |
|---|---|---|
| QA lead | To be assigned | Own plan, execution tracking, defect triage and report |
| Test engineer | To be assigned | Design and run unit, integration and system cases |
| Development lead | To be assigned | Fix defects, review changes, maintain testability |
| Project owner / evaluator | To be assigned | Review acceptance criteria and sign off |

## 10. Risks and Mitigation
| Risk | Mitigation |
|---|---|
| MySQL unavailable | Provision disposable local/container database before integration run |
| Inconsistent test data | Use deterministic seed and reset scripts |
| Race conditions in seat booking | Run concurrent booking tests with assertions on final inventory |
| Browser incompatibility | Run Chromium and Firefox; record WebKit limitation separately |
| Misleading coverage or log counts | Re-run tests and capture dated, versioned reports |
| Unavailable external integrations | Test simulated boundaries; mark real delivery out of scope |

## 11. Assumptions & Dependencies
A disposable MySQL instance and dummy test accounts are available; the SRS is the requirements baseline; backend migrations and frontend build can be reproduced. Real payment and messaging integrations are not assumed.

## 12. Suspension & Resumption Criteria
**Suspend:** Broken build, unavailable database, unrepeatable environment, evidence of data corruption, double-booking, or blocking authorization defect.

**Resume:** Environment repaired, critical defect corrected, data reset, smoke tests pass and QA lead records authorization to continue.

## 13. Test Case Management & Traceability
Use the official nine-column test-case format: **Test Case ID, Name of Module, Test Case Description, Pre-conditions, Test Steps, Test Data, Expected Results, Actual Result, Test Result**.

Plan **8–10 cases per implemented use case**, distributed across unit, integration and system levels. IDs use `UT-...`, `IT-...`, and `ST-...`. Include valid, invalid, boundary, unauthorized, duplicate and concurrent cases. Link each case to its RRS-F requirement in the RTM.

**Execution rule:** Actual Result and Pass/Fail must be populated only after a recorded test run. Existing planned cases are not evidence of execution.

## 14. Test Metrics & Reporting
Track total cases, executed, passed, failed, blocked, not run, pass percentage among executed cases, requirements with executed coverage, severity of open defects, defect aging and dated build/test environment. Distinguish automated unit tests from manually executed test cases and from MySQL-backed integration evidence. Record any coverage denominator mismatch before claiming a final figure.

## 15. Approvals
| Role | Name | Signature / Date |
|---|---|---|
| QA lead | Pending | Pending |
| Development lead | Pending | Pending |
| Project owner / evaluator | Pending | Pending |

**Status:** Prepared for review. Manual execution and approval are pending.
