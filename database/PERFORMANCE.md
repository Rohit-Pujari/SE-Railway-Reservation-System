# Search and booking-history performance (Issue #41)

## Query review

The passenger train search is a single parameterized SQL statement. It joins the two requested schedule stops, uses one lateral fare lookup, and calculates seat availability with an indexed anti-join. The API caps the result set at 100 schedules. Booking history is also one SQL statement: passenger and seat details are joined in the database and grouped in memory, so it does not issue one query per booking or passenger.

The schema already had useful primary/unique keys and indexes for seat inventory and active allocations. This change adds only indexes for access patterns that were not covered well:

| Index | Workload it supports |
|---|---|
| `idx_stations_active_city` | Active station dropdown filtered and sorted by city/name |
| `idx_schedule_stops_station_departure` | Origin station + departure-day range used by train search |
| `idx_schedule_stops_station_arrival` | Destination station/schedule/stop lookup, including arrival value |
| `idx_route_fares_segment_price` | Lowest fare lookup for a route segment when no class is selected |
| `idx_bookings_user_departure_created` | Passenger booking history filtered by owner and ordered by trip date |
| `idx_seat_allocations_booking_passenger` | Booking/passenger join when loading seat allocation details |

The existing `idx_seat_allocation_conflicts` and `idx_schedule_seat_lookup` continue to support seat-conflict and schedule inventory lookups. No redundant index was added for those paths.

## Applying the indexes to an existing database

The updated `database/schema.sql` creates these indexes for new installations. Existing installations must apply the repeatable migration once:

```powershell
mysql -u root -p < database/migrations/002_add_search_booking_indexes.sql
```

Run it against the same MySQL 8 database configured in `.env`. The migration checks `information_schema.statistics` and skips indexes that already exist. Take the normal database backup before applying schema changes in a shared or production environment.

## Scale regression tests

The CI suite now exercises:
- A train-search result set at the configured maximum of 100 schedules, asserting one database query and one result fetch.
- Booking history containing 1,000 bookings and 2,000 passenger rows, asserting correct grouping into upcoming/previous sections and exactly one database query (no N+1 query pattern).

These are deterministic service-layer scale tests using synthetic database rows. They validate result shaping, bounded search responses, and database round-trip count; they are not a substitute for measuring a live MySQL query plan or production throughput.

## Checking real MySQL query plans

After loading representative data into a disposable/staging MySQL 8 database and applying the migration, inspect actual plans with `EXPLAIN ANALYZE`:

```sql
EXPLAIN ANALYZE
SELECT schedule_stop_id
FROM schedule_stops
WHERE station_id = 1
  AND departure_at >= '2026-11-15 00:00:00'
  AND departure_at <  '2026-11-16 00:00:00';

EXPLAIN ANALYZE
SELECT booking_id
FROM bookings
WHERE user_id = 1
ORDER BY departure_at_snapshot ASC, created_at DESC, booking_id
LIMIT 1000;

EXPLAIN ANALYZE
SELECT allocation_id
FROM seat_allocations
WHERE booking_id = 1
  AND booking_passenger_id = 1001;
```

Check that MySQL chooses the new composite indexes for the relevant access paths and compare actual rows examined and execution time against a pre-migration baseline. Index selection depends on table size and data distribution; do not force an index without evidence from the plan.
