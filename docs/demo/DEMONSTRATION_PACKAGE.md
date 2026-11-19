# Demonstration Package — Railway Reservation System

**Commit SHA:** `167d56e` (branch `se-evaluation-complete`, PR #92)  
**Date:** 19 November 2026

This package contains scripts and materials for demonstrating the system during sprint reviews and viva. All scripts are designed to be executed against a live deployment of the application (Django API + React frontend + MySQL). Database-dependent steps are clearly labeled and require a configured MySQL instance with valid credentials.

---

## 1. Passenger Workflow Script

**Objective:** Demonstrate the complete passenger journey from registration to booking confirmation.

### Prerequisites
- Application running: Django API on port 8000, React frontend on port 5173
- MySQL database running with schema loaded
- Chrome or Firefox browser

### Steps

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Open http://127.0.0.1:5173 in browser | Home page loads with "Trackline" branding |
| 2 | Click "Create account" | Registration form appears |
| 3 | Enter full name, email, password (8+ chars, uppercase, lowercase, digit) | Form accepts input |
| 4 | Click "Create account" | HTTP 201, account created, redirected to login |
| 5 | Log in with email and password | HTTP 200, session established, "Signed in" panel shown |
| 6 | Search trains: select source, destination, date (today or future), class | Matching schedules returned with fares and available seats |
| 7 | Click "Book" on a train | Traveler details form appears |
| 8 | Enter passenger name, age (1-120), gender, berth preference | Form validates input |
| 9 | Click "Book and reserve seats" | HTTP 201, booking created with 12-char PNR, seats held for 15 minutes |
| 10 | Click "Pay (demo)" | HTTP 201 (or 200 for replay), booking status = CONFIRMED, payment = SIMULATED |
| 11 | Click "My bookings" / "Check status" | Booking history shows confirmed ticket with PNR and seat details |
| 12 | Look up by PNR on status page | Same booking details returned (owner-only access) |
| 13 | Click "Cancel ticket" with reason | Booking status = CANCELLED, seats released, refund record created (PENDING) |
| 14 | Log out | Session cleared, redirected to login |

### Negative tests (authorization)
| Step | Action | Expected Result |
|------|--------|-----------------|
| A | Anonymous user attempts to book | HTTP 401 |
| B | Passenger attempts admin endpoint (`/api/admin/dashboard`) | HTTP 403 |
| C | Past date in search form | HTML5 date picker prevents selection; server-side validation rejects past dates |
| D | Age 0 or negative in passenger form | Validation error: "age must be between 1 and 120" |
| E | Untrusted origin CSRF request | HTTP 403 |

---

## 2. Administrator Workflow Script

**Objective:** Demonstrate administrator authentication and management operations.

### Prerequisites
- Admin account exists in `users` table with `role='ADMIN'` and `account_status='ACTIVE'`
- Application running as above

### Steps

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Open http://127.0.0.1:5173/?admin=1 | Admin login form |
| 2 | Log in with admin email and password | HTTP 200, admin session established, "Administrator signed in" |
| 3 | Open admin dashboard | Summary counts (trains, routes, schedules, bookings, cancellations) displayed |
| 4 | Create a train | HTTP 201, train added with train_number, train_name, status |
| 5 | Update a train | HTTP 200, train details updated |
| 6 | Deactivate a train (set status INACTIVE) | HTTP 200, train_status = INACTIVE |
| 7 | Create a station | HTTP 201, station added with unique code |
| 8 | Create a route with 2+ stops | HTTP 201, route and route_stops created |
| 9 | Assign route to train | HTTP 200, train_route assignment created |
| 10 | Create a schedule | HTTP 201, schedule with departure/arrival times created |
| 11 | View seat inventory for a schedule | Seat list with coach/seat numbers and operational status |
| 12 | Update seat operational status | HTTP 200, seat status updated |
| 13 | View booking and cancellation records | All bookings and cancellations listed with passenger details |
| 14 | Log out as admin | Session cleared |

### Negative tests (authorization)
| Step | Action | Expected Result |
|------|--------|-----------------|
| A | Passenger attempts admin login | HTTP 401 (credentials rejected) |
| B | Passenger accesses `/api/admin/dashboard` | HTTP 403 |
| C | Anonymous accesses any admin endpoint | HTTP 401 |
| D | Admin attempts to delete train with existing schedules | HTTP 409 (dependency protection) |

---

## 3. One-Minute Sprint 1 Demonstration Script

**Sprint 1 focus:** Core passenger booking flow (registration, login, search, booking, payment).

**Script (approx. 60 seconds):**

1. **(0-10s)** Open the application at http://127.0.0.1:5173. Show the home page with search form.
2. **(10-20s)** Click "Create account", fill in registration details, submit. Show success message.
3. **(20-30s)** Log in with the new credentials. Show "Signed in" panel.
4. **(30-40s)** Search for trains: pick source, destination, today's date, a class. Show results.
5. **(40-50s)** Click "Book", enter one passenger's details (name, age 25), submit. Show booking created with PNR.
6. **(50-60s)** Click "Pay (demo)". Show confirmation: status = CONFIRMED, payment = SIMULATED.

**Narration points:**
- "This is the core passenger booking flow."
- "Registration creates an account with hashed password storage."
- "Booking creates a PNR and holds seats for 15 minutes."
- "Payment is simulated — no real money is charged."
- "All operations are authenticated and scoped to the signed-in user."

---

## 4. Two-Minute Sprint 2 Demonstration Script

**Sprint 2 focus:** Administrator operations, cancellation, and security.

**Script (approx. 120 seconds):**

1. **(0-20s)** Log in as administrator. Show admin dashboard with operational summary.
2. **(20-40s)** Create a train, station, route, and schedule. Show each creation succeeding.
3. **(40-60s)** View seat inventory for a schedule. Update a seat's operational status.
4. **(60-80s)** Log out as admin, log in as passenger. Book a ticket, then cancel it. Show seats released and refund record created.
5. **(80-100s)** Attempt unauthorized access: passenger tries admin dashboard (403), anonymous tries booking (401). Show rejection.
6. **(100-120s)** Show booking status lookup by PNR. Confirm owner-only access.

**Narration points:**
- "Administrators manage railway inventory: trains, stations, routes, schedules, seats."
- "Cancellation releases seats and creates pending refund records atomically."
- "Role-based access control prevents passengers from accessing admin endpoints."
- "CSRF protection rejects cross-origin requests."
- "Payment remains simulated — no real payment gateway."

---

## 5. Viva Questions and Answers

### Q1: What architecture does this project use?
**A:** Layered modular monolith: React/Vite presentation layer, Django REST Framework API boundary, feature-specific domain services (booking, payment, cancellation, search, admin), and MySQL InnoDB persistence. All database access goes through parameterized `mysql-connector-python` queries in feature services.

### Q2: How does the booking workflow ensure no double-booking?
**A:** `create_booking` locks all in-service seats for a schedule/class in deterministic ID order (`FOR UPDATE`) within a single InnoDB transaction. It checks for overlapping confirmed/held allocations before assigning seats. Booking, passenger rows, and seat allocations commit atomically.

### Q3: How does idempotency work?
**A:** Each booking request includes an idempotency key. Retrying with the same key returns the existing booking with `replayed: true` instead of creating a duplicate. Payment confirmation similarly returns the existing confirmation without creating a duplicate payment.

### Q4: How is payment simulated?
**A:** No Razorpay or real gateway is integrated. `confirm_booking_payment` validates ownership and active seat holds, records a `SIMULATED` payment, confirms held seats, updates booking to `CONFIRMED`, and queues notification records. No real money is charged.

### Q5: How does cancellation work?
**A:** `cancel_booking` verifies ownership and booking eligibility, calculates cancellation charges and refunds using time-based policy bands, creates cancellation items and pending refund records, releases seat allocations, and sets booking to `CANCELLED` — all in one atomic transaction.

### Q6: What security controls are in place?
**A:** Django CSRF middleware on all state-changing endpoints, signed-cookie sessions with HttpOnly/SameSite=Lax, role-based access control (`PASSENGER`/`ADMIN`), parameterized SQL, password hashing with Werkzeug scrypt, and ownership checks on all passenger data access.

### Q7: How are database transactions handled?
**A:** Each feature service (`create_booking`, `confirm_booking_payment`, `cancel_booking`) runs in one InnoDB transaction with `READ COMMITTED` isolation. Any exception triggers rollback. Deterministic lock ordering prevents deadlocks.

### Q8: What are the known limitations?
**A:** Payment is simulated (no real gateway), notifications are queued but not delivered, refunds are pending obligations (no bank settlement), no production failover or high availability, no measured SLA, mocked unit tests don't prove live database correctness.

### Q9: How does CI work?
**A:** GitHub Actions runs on push/PR: Python dependency installation, React build, Playwright browser tests (Chromium, Firefox), Python compilation, Django system checks, backend unit tests with line and branch coverage, and artifact upload. Not continuous deployment.

### Q10: How is requirements traceability maintained?
**A:** The RTM in `docs/SE_SRS.md` §8 maps each functional requirement (F-001–F-020) to modules, APIs, and test cases. The evaluation tracker (`docs/SE_EVALUATION_TRACKER.md`) records execution evidence for each test category.

---

## 6. Architecture Explanation

```
Browser (React/Vite) --> HTTP JSON /api --> Django API Views
                                              |
                                              v
                                  +-------------------------------+
                                  | Session / CSRF / Role Checks  |
                                  +-------------------------------+
                                              |
        +----------------+--------------------+--------------------+
        |                |                    |                    |
   Search            Booking            Payment            Admin
   Service           Service            Service           Service
        |                |                    |                    |
        +----------------+--------------------+--------------------+
                                              |
                                          MySQL InnoDB
```

### Technology Stack
- **Frontend:** React 19, Vite
- **Backend:** Python 3.11, Django 5.2, Django REST Framework
- **Database:** MySQL 8.0.16+, InnoDB
- **Testing:** Python unittest, Playwright, coverage.py
- **CI:** GitHub Actions

---

## 7. CI Explanation

The GitHub Actions workflow (`.github/workflows/tests.yml`) runs on every push and pull request:

1. **Check out repository**
2. **Set up Python** (3.11) with pip caching
3. **Set up Node** (22) with npm caching
4. **Install dependencies** — Python (`requirements.txt` + `coverage`), Node (`npm ci`)
5. **Build React** (`npm run build`)
6. **Install Playwright** — Chromium, Firefox, WebKit, Edge browsers
7. **Run browser tests** — Playwright cross-browser suite
8. **Compile Python** — `compileall -q backend`
9. **Django check** — `python -m backend.manage check`, `bash -n run-dev.sh`
10. **Unit tests with coverage** — `coverage run --branch` + `coverage report/json/xml`
11. **Upload artifacts** — `unit-and-coverage-reports` (test log, coverage reports)

**Not continuous deployment:** There is no automated production deployment step.

---

## 8. Testing Explanation

### Testing levels
| Level | Scope | Tool | Evidence |
|-------|-------|------|----------|
| Unit | Service functions with mocked DB | Python unittest | `docs/test-reports/unit-test.log` |
| Integration | API endpoints with mocked services | Python unittest | `docs/test-reports/unit-test.log` |
| System | Browser flows with mocked API | Playwright | `test-results/` |
| Regression | Full suite on every change | unittest + CI | GitHub Actions |

### Coverage
- Line coverage: **76.2%**
- Branch coverage: **68.9%**
- Measured with `coverage run --branch --source=backend/app,backend/config`

### Key test scenarios
- Registration validation and duplicate rejection
- Login/logout and session management
- Admin vs passenger authorization
- Train search with validation errors
- Booking creation, PNR, seat holds, idempotency
- Simulated payment confirmation and replay
- Booking history and owner-only access
- Cancellation and pending refunds
- Admin dashboard, station/route/train/schedule management
- CSRF protection and untrusted origin rejection
- Database failure rollback
- Past-date rejection and age 1-120 validation

---

## 9. Database Transaction Explanation

### `create_booking` transaction
1. `BEGIN READ COMMITTED`
2. Lock passenger account row (`FOR UPDATE`)
3. Check idempotency key — return existing booking if replay
4. Lock all schedule seats (`FOR UPDATE` in ID order)
5. Check availability, compute fare
6. INSERT booking, passengers, seat allocations
7. `COMMIT` — all or nothing

### `confirm_booking_payment` transaction
1. `BEGIN READ COMMITTED`
2. Lock booking row (`FOR UPDATE`)
3. Lock all schedule seats (`FOR UPDATE` in ID order)
4. Validate hold expiry and ownership
5. INSERT payment record (SIMULATED, SUCCEEDED)
6. UPDATE seat allocations to CONFIRMED
7. UPDATE booking to CONFIRMED with confirmed_at
8. INSERT notification records (QUEUED)
9. `COMMIT`

### `cancel_booking` transaction
1. `BEGIN READ COMMITTED`
2. Lock booking row (`FOR UPDATE`)
3. Validate eligibility and ownership
4. Lock seat allocations (`FOR UPDATE`)
5. Compute cancellation charges and refunds
6. INSERT cancellation, cancellation_items, refunds (PENDING)
7. UPDATE seat allocations to RELEASED
8. UPDATE booking to CANCELLED
9. `COMMIT`

### Row lock ordering
All services lock `schedule_seats` in ascending `schedule_seat_id` order to prevent deadlocks when multiple concurrent bookings compete for the same seats.

---

## 10. Known Limitations

| Limitation | Details |
|------------|---------|
| Simulated payment | No Razorpay or real gateway. `payment_method = SIMULATED`, no real money transfer. |
| Queued notifications | `delivery_status = QUEUED` only. No actual email/SMS sent. |
| Pending refunds | `refund_status = PENDING`. No bank settlement. |
| No production failover | Single Django process, single MySQL instance. No automatic recovery. |
| No measured SLA | 99.5% availability is a target, not measured. |
| Mocked unit tests | Database access is mocked. Does not prove live DB correctness. |
| Safari/WebKit | Blocked by missing system dependencies (libicu74, libxml2). |
| No DB credentials | Live database integration testing excluded from this evaluation. |
