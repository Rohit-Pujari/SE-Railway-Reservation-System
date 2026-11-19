# Architecture and maintenance decisions

This document records the current module boundaries and the rules to follow when extending the Railway Reservation System.

## Feature ownership

| Area | Module | Responsibility |
|---|---|---|
| Database connection | `backend/app/db.py` | Build configured MySQL connections; no feature rules |
| Shared validation | `backend/app/validation.py` | Small input primitives reused by feature services |
| Booking | `backend/app/booking.py` | Validate booking requests, lock inventory, allocate seats, create PNR and pending booking |
| Fare calculation | `backend/app/fare_calculation.py` | Calculate and persist fare snapshots for a pending booking |
| Payment | `backend/app/booking_payment.py` | Confirm an existing booking using the simulated payment workflow |
| Cancellation | `backend/app/booking_cancellation.py` | Cancel passenger allocations and create refund records atomically |
| Refund policy | `backend/app/booking_refunds.py` | Pure cancellation-refund calculation rules |
| Search and availability | `backend/app/train_search.py`, `backend/app/seat_availability.py` | Read train options and availability |
| HTTP/API layer | `backend/app/django_views.py` | Parse requests, enforce session/role rules, call feature services, map domain errors to HTTP responses |
| Routing/configuration | `backend/config/` | Django settings, URL routing and deployment entry points |
| User interface | `frontend/src/` | React screens and browser interactions; business rules remain on the API |
| Database definition | `database/schema.sql` and `database/migrations/` | Source-controlled MySQL schema and versioned SQL changes |

## Design rules

1. Keep database access and SQL in backend feature services. HTTP views should orchestrate requests and translate known domain exceptions, not duplicate transaction logic.
2. Keep one owner for each business operation. Booking creates a pending reservation and seat holds; payment confirms it; cancellation releases allocations and records refund obligations. Do not reimplement these workflows in views or other services.
3. Put genuinely shared, domain-neutral primitives in small modules. For example, `positive_int` in `validation.py` centralizes strict positive-ID parsing while each service supplies its own domain exception and user-facing wording.
4. Preserve feature-specific exceptions at service boundaries so the API can return useful responses without coupling the shared helper to a particular feature.
5. Use parameterized SQL for every database value. Keep multi-row booking, payment, fare, and cancellation changes inside their existing database transactions.
6. Avoid circular imports. Shared modules must not import feature services; feature services may depend on shared modules.
7. Add or update focused service tests when changing a feature, then run the full backend test suite and frontend production build.
8. Update this document and `docs/PROJECT_DOCUMENTATION.md` when adding a module, changing a module boundary, or introducing a consequential design decision.

## Decision: shared positive-integer validation

Booking creation, payment confirmation, and cancellation all require canonical positive integer IDs and must reject booleans, zero, negative values, malformed strings, and non-canonical representations. This rule now lives in `backend/app/validation.py`. Each caller passes its own exception class and optional wording, preserving the public behavior of each feature while removing three copies of the parsing algorithm.

## Transaction and schema constraints

- Booking, payment, and cancellation operations must retain their existing transaction boundaries and deterministic seat-lock ordering.
- Do not use Django ORM migrations to mutate the existing MySQL schema. Review `database/SCHEMA_REVIEW.md` and add a versioned SQL migration for schema changes.
- Never claim real payment, email, or SMS delivery: these integrations are simulated/queued in the current coursework implementation.
