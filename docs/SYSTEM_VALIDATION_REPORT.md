# System Validation Report — Railway Reservation System

**Date:** 19 November 2026  
**Result:** Conditional — further checks required  
**Reference:** `Documents/VERIFICATION_2026-11-19.md`  
**Systems covered:** Django backend, React frontend, booking and simulated payment, and a separate MariaDB test database.

This report is based on the verification notes already recorded in the repository. I have kept the results from those notes separate from checks that still need to be run after the latest payment changes.

## 1. Purpose and acceptance criteria

The aim was to check whether the reservation system meets the main requirements in the Software Requirements Specification (SRS) and the test plan. The report covers account access, train search, seat booking, payment, and the checks around data consistency.

A test is marked **PASS** only when an actual result is mentioned in the verification notes. **NOT IMPLEMENTED** means the tested version did not have that feature. **BLOCKED** means the test could not be completed, and **NOT VERIFIED** means there is no recorded result to support a pass.

## 2. Environment and method

The earlier tests were carried out using a separate MariaDB database on port 13316. The Django backend and Vite frontend were started on ports 8001 and 5175, and the browser checks used Chromium. The existing schema was imported without changes. Demo data included 36 stations, 180 trains, and 5,400 schedules for November.

The verification notes also mention a frontend running on port 5173, which was used to check login and logout with an existing account. These environment details come from the recorded test session; they have not been recreated for this revision of the report.

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

According to the earlier verification notes, **101 unit tests passed** after the reported issues were corrected. The first run had one failure and three errors. The notes also record a successful React production build and Django system check.

The full test output was saved locally as `/tmp/railway-tests-after.log`, but that file is not included in the repository. Because of that, the 101-test result is reported as earlier evidence, not as a fresh result for the current branch. The report also does not have a measured code-coverage percentage. The payment changes made later still need their own test run.

## 5. Security validation

The verification notes cover request-origin and Cross-Site Request Forgery (CSRF) checks, access to passenger-owned bookings, duplicate booking requests, and database rollback after a failed operation. These checks are useful for basic access control and data consistency.

They do not amount to a complete security audit. Session-cookie replay, penetration testing, and wider security testing were not recorded.

## 6. Defects, deviations and outstanding work

1. **High:** Live DB role lacks UPDATE privileges. Apply and verify the minimal grants in `database/app_permissions.sql` with an authorized database administrator, then repeat the live payment/fare checks. Do not apply schema reset to a personal database.
2. **High:** Cancellation, refunds and several admin management flows required by the SRS are not implemented. Either implement and validate them or formally reconcile the approved scope and SRS.
3. **Medium:** Backend search accepts past ISO dates although the HTML field restricts them; server-side validation is pending.
4. **Medium:** Passenger age zero is accepted by the validator but rejected by the test-plan requirement; reconcile and test.
5. **Medium:** Historical booking grouping and the simulated-payment user interface lack dedicated end-to-end UI execution evidence.
6. **Evidence:** Attach CI run URLs, retained test logs, browser screenshots, database verification output, measured coverage, and final reviewer sign-off.
7. **Compatibility:** MariaDB was used; MySQL 8 production compatibility was not independently validated.

## 7. Final assessment

**Overall result: Conditional.** The recorded tests show that core registration, train search, and booking operations worked in the isolated test setup. They also provide evidence for some access-control and database-consistency checks. However, the simulated payment flow was restored after that testing, so its current behaviour still needs to be checked. The earlier notes also identify gaps in cancellation, refunds, administration, database permissions, and nonfunctional testing.

For these reasons, the system cannot yet be marked as fully validated against the complete SRS.

**Prepared from:** `Documents/VERIFICATION_2026-11-19.md` (19 November 2026).  
**Reviewer sign-off:** Pending.  
**Independent rerun by report author:** Not performed.


## Payment workflow change (2026-11-19)

The project briefly used an administrator approval step in place of payment. That approach has now been removed, and the earlier simulated payment flow has been restored. In the restored flow, a passenger can confirm a booking through a demo payment action. It does not connect to Razorpay or transfer actual money.

The previous approval tests are not evidence that the restored payment flow works. Payment confirmation, repeat requests, access control, and the frontend payment button should be checked again once the merge is complete.
