# Railway Reservation System — database schema review

**Status:** Pull request open for review. This document describes the schema proposal; it is not evidence of execution against a live MySQL server.

## Scope and assumptions

1. A booking/PNR contains multiple passengers on the same train schedule, class, and journey segment.
2. An individual passenger can be cancelled, leaving the PNR partially cancelled.
3. Seats can be reused for non-overlapping journey segments of one schedule.
4. Payment attempts and refund attempts have separate status and idempotency tracking.
5. MySQL 8.0.16+ and InnoDB are targeted. Money uses DECIMAL; schedule times use DATETIME.
6. Fare records use route + origin stop + destination stop + class. The final purchased train/station/time/class/fare details are stored on the booking as snapshots.
7. Email/SMS notification delivery is logged; actual provider integration is separate work.

## Tables

\`users\`, \`stations\`, \`trains\`, \`routes\`, \`route_stops\`, \`train_schedules\`, \`schedule_stops\`, \`travel_classes\`, \`route_fares\`, \`seats\`, \`schedule_seats\`, \`bookings\`, \`booking_passengers\`, \`seat_allocations\`, \`payments\`, \`cancellations\`, \`cancellation_items\`, \`refunds\`, and \`notifications\`.

## Important service-layer rules

The database constraints provide referential integrity, but cannot enforce every cross-row business rule. Backend code and integration tests must:

1. Verify the boarding stop precedes the alighting stop and both belong to the selected scheduled run.
2. Verify scheduled stop identities and times are complete and ordered; do not mutate stop identity/order after bookings exist.
3. Calculate the correct fare for the selected segment/class, then persist the purchased fare and itinerary snapshots.
4. Lock the matching \`schedule_seats\` row with \`SELECT ... FOR UPDATE\` before checking or allocating a seat.
5. While holding the lock, expire stale holds and reject any active allocation for the same physical seat whose segment overlaps. For half-open journey segments, overlap is \`existing_board < requested_alight AND existing_alight > requested_board\`.
6. Allocate all passengers for a booking atomically; roll back every allocation if one passenger cannot be allocated.
7. Confirm a booking only after a successful payment is persisted. Make payment callbacks/retries idempotent.
8. Release held seats safely after failed/expired payment.
9. Lock cancellation and passenger/allocation rows to prevent duplicate cancellation. Seat release and cancellation-item completion should be committed atomically; refund processing can remain pending afterwards.
10. Verify passenger-fare totals equal the booking's base fare total. Derive booking state from the passenger/cancellation states.
11. Never let self-registration create ADMIN accounts. Do not store raw card data, CVVs, or UPI PINs.

## Remaining decisions and limitations

- This design chooses segment-based seat reuse. This is more realistic than reserving a seat for an entire run but requires careful concurrency and overlap tests.
- Confirm the coursework fare policy. If fares are distance/class based rather than manually maintained per origin/destination stop pair, the fare table can be simplified.
- Passenger attributes currently follow the requirements' name/age needs; DOB or other fields can be added only if specifically required.
- Seed data for classes, stations, trains, schedules, seats, and fares is not included in the DDL.
- Schema changes should be applied using versioned migrations as the project evolves.
- For service disruptions, timetable changes, and train cancellations after tickets have been sold, a later operational-event workflow and user notification policy may be required.

## Validation

The DDL includes primary keys, unique constraints, foreign keys, check constraints, and lookup indexes. It has **not** been executed against a live MySQL 8 server in this environment. Before merging, import it into a disposable MySQL 8.0.16+ database and add integration tests for foreign keys, multi-passenger booking, partial cancellation, failed payment/retry, refund retry, expired holds, same-seat non-overlapping reuse, overlapping-seat rejection, and concurrent booking attempts.
