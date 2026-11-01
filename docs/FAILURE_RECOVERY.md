# Failure recovery and booking consistency

This guide describes how the booking and simulated-payment workflows recover from database errors, interrupted requests, and lost HTTP responses.

## Transaction boundaries

- `create_booking` runs booking, passenger, and seat-hold inserts in one InnoDB transaction. Any exception before a successful commit triggers rollback, so partial bookings and partial seat holds are not intentionally left behind.
- `confirm_booking_payment` locks the booking and schedule inventory, then records the successful payment, confirms every held seat, updates the booking to `CONFIRMED`, and queues confirmation notifications in one transaction.
- A payment or booking failure before commit rolls back the transaction. A confirmed booking must have a successful payment record; the payment retry path checks this invariant instead of creating another payment.
- Cancellation/refund operations use their own transaction and are outside the scope of this issue.

## Safe retry behavior

### Booking request

1. Generate one idempotency key for a booking attempt and retain it while retrying that same request.
2. If the client times out or loses the response, retry with the same key and identical booking details.
3. `create_booking` looks up the passenger/key pair under a row lock. If the original booking and active seat holds exist, it returns that booking with `replayed: true` rather than inserting another booking.
4. Do not generate a new key just because the response was lost; a new key represents a new booking attempt.

### Payment confirmation

1. Retry payment confirmation for the same booking ID after a timeout; do not create another booking.
2. If the first transaction rolled back, the booking remains pending and the payment workflow can be attempted again while its seat holds remain valid.
3. If the commit succeeded but the response was lost, the retry finds the `CONFIRMED` booking and its `SUCCEEDED` payment, returns the existing confirmation with `replayed: true`, and does not insert another payment.
4. If a booking is marked `CONFIRMED` without a successful payment row, the service returns a consistency error and does not silently repair or charge it again. Investigate the database state before taking manual action.

## Operational checks

- Inspect the booking row, payment rows, passenger rows, and seat allocations together when investigating a reported failure.
- A healthy confirmed booking has `bookings.booking_status = CONFIRMED`, a corresponding `payments.payment_status = SUCCEEDED`, and the expected seat allocations in `CONFIRMED` state.
- A pending booking should have all passenger and seat-hold rows created together; holds expire after the configured 15-minute period.
- Notification rows are queued transactionally with confirmation. The current project uses a simulated payment provider and queued notification records; it does not send real payment requests, email, or SMS.
- Never resolve an uncertain outcome by manually changing a booking status alone. Preserve the payment and allocation relationship and investigate transaction logs first.

## Regression coverage

Automated tests cover rollback after an interrupted booking insert, recovery of a booking after an uncertain commit acknowledgement using the same idempotency key, rollback when payment confirmation is interrupted after payment insertion, and safe replay after a committed confirmation. Run the full backend test suite with:

```bash
python -m unittest discover -s backend/tests -v
```
