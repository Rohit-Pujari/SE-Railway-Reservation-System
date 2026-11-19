# System Validation Report — Railway Reservation System

**Report date:** 19 November 2026  
**Status:** CONDITIONAL / CHANGES REQUIRED  
**Source of execution evidence:** `Documents/VERIFICATION_2026-11-19.md` on this branch. This report transcribes the recorded execution results; the current reviewer did not independently rerun the browser, MariaDB, or local test commands.  
**Scope:** Django backend, React frontend, booking/simulated payment flow, and an isolated MariaDB test instance.

## 1. Purpose and acceptance criteria

Evaluate the implemented passenger and administrator workflows against the railway SRS and test plan. A feature is **PASS** only when the verification record documents an executed check; **PARTIAL** when only a subset was checked; **FAIL / NOT IMPLEMENTED** where a required workflow is absent; **BLOCKED** where prerequisites prevent execution; and **NOT VERIFIED** without evidence.

## 2. Environment and method

The recorded verification used a separate MariaDB instance on port 13316 with a dedicated temporary data directory, a Django/Vite launcher on ports 8001/5175, and Chromium. The schema was imported unchanged. The demo seeder generated 36 stations, 180 trains and 5,400 November schedules. A restarted live frontend on port 5173 was used for existing-account login/logout checks without inserting personal records. These are claims in the source verification record, not a fresh execution in this report.

## 3. Executed system validation cases

| ID | Requirement / workflow | Expected result | Recorded actual result | Status |
| --- | --- | --- | --- | --- |
| SV-01 | Passenger registration and login | New user persists and can authenticate | Chromium registration HTTP 201, committed account, login/logout HTTP 200 | PASS (recorded) |
| SV-02 | Administrator authentication | Authorized admin login/logout works | Unified admin login/logout HTTP 200 | PASS (recorded) |
| SV-03 | Train search and fare | Valid route/date returns matching trains, fares and seats | Search/classes/fare/availability returned matching services | PASS (recorded scope) |
| SV-04 | Passenger booking | Booking allocates seats and returns PNR | Browser booking HTTP 201; inventory decreased by one | PASS (recorded) |
| SV-05 | Simulated payment | Passenger-owned booking confirms after demo payment | Automated verification pending after workflow restoration | NOT RE-RUN |
| SV-06 | Payment access control | Anonymous users cannot pay | Automated verification pending after workflow restoration | NOT RE-RUN |
| SV-07 | Payment retry | Payment retries do not double-charge | Automated verification pending after workflow restoration | NOT RE-RUN |
| SV-08 | Idempotency | Repeat confirmation does not duplicate payment | Automated verification pending after workflow restoration | NOT RE-RUN |
| SV-09 | Booking history | Owner sees ticket; other accounts cannot | Confirmed ticket included seats; cross-account read rejected | PASS (recorded) |
| SV-10 | Idempotent booking | Repeated key cannot allocate twice | Same booking/PNR returned, no additional allocation | PASS (recorded) |
| SV-11 | Concurrent seat allocation | Overselling prevented | Two 6-seat requests for 8 seats: one HTTP 201, one HTTP 409, two seats remained | PASS (recorded) |
| SV-12 | Expired hold | Expiry restores inventory; payment rejected | Availability restored; payment confirmation rejected | PASS (recorded) |
| SV-13 | Transaction rollback | Partial failure leaves no booking | Injected allocation-insert failure rolled back booking/passenger inserts | PASS (recorded) |
| SV-14 | Browser CSRF protection | Trusted origin with token succeeds; untrusted origin fails | Origin regression tests added; Chromium registration initially failed with 403 and was corrected | PASS (recorded) |
| SV-15 | Cancellation/refunds | Passenger can cancel, release seats and initiate refund | Active API/UI does not implement cancellation/refund workflow | NOT IMPLEMENTED |
| SV-16 | Admin train/route/schedule/seat management | Admin can manage inventory and schedules | CRUD/management endpoints not implemented in active API/UI | NOT IMPLEMENTED |
| SV-17 | Live simulated payment | Live database supports booking confirmation | Runtime DB privileges require verification | BLOCKED |
| SV-18 | Cross-browser and nonfunctional testing | Supported browsers, load/recovery/performance verified | No broad cross-browser, load, stress or crash recovery evidence | NOT VERIFIED |

## 4. Unit and build evidence

The source verification document records **101 unit tests passed after corrections**, with an initial run showing one failure and three errors. It also records a passing React production build and Django system check. The original test output was kept at `/tmp/railway-tests-after.log` and is **not attached to this repository**. Therefore, this report does not independently certify the unit-test count. No measured line or branch coverage percentage is available in the supplied record.

## 5. Security validation

Recorded checks include origin/CSRF protection, payment ownership, payment ownership checks, isolation of booking history, booking idempotency, and transaction rollback. Session-cookie theft/replay, penetration testing, and broader security testing remain outside the recorded execution scope.

## 6. Defects, deviations and outstanding work

1. **High:** Live DB role lacks UPDATE privileges. Apply and verify the minimal grants in `database/app_permissions.sql` with an authorized database administrator, then repeat the live payment/fare checks. Do not apply schema reset to a personal database.
2. **High:** Cancellation, refunds and several admin management flows required by the SRS are not implemented. Either implement and validate them or formally reconcile the approved scope and SRS.
3. **Medium:** Backend search accepts past ISO dates although the HTML field restricts them; server-side validation is pending.
4. **Medium:** Passenger age zero is accepted by the validator but rejected by the test-plan requirement; reconcile and test.
5. **Medium:** Historical booking grouping and the simulated-payment user interface lack dedicated end-to-end UI execution evidence.
6. **Evidence:** Attach CI run URLs, retained test logs, browser screenshots, database verification output, measured coverage, and final reviewer sign-off.
7. **Compatibility:** MariaDB was used; MySQL 8 production compatibility was not independently validated.

## 7. Final assessment

**CONDITIONAL — NOT FULLY VALIDATED AGAINST THE COMPLETE SRS.** The source verification record supports a functioning isolated registration/search/booking/simulated-payment workflow and several integrity/security checks, but it also explicitly identifies missing cancellation/refund and admin-management features, blocked live database permissions, and incomplete nonfunctional coverage. A final unconditional PASS would be unsupported.

**Prepared from:** `Documents/VERIFICATION_2026-11-19.md` (19 November 2026).  
**Reviewer sign-off:** Pending.  
**Independent rerun by report author:** Not performed.


## Payment workflow change (2026-11-19)

The manual administrator payment-approval implementation was removed in favor of the original simulated payment confirmation flow. No real payment provider, Razorpay integration, or money transfer is involved. Payment-related checks above marked NOT RE-RUN must be executed again after integrating the merge; previous manual-approval evidence does not validate this restored workflow.
