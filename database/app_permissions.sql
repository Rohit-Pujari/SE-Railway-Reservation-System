-- Run as a database administrator against the local development database:
-- sudo mariadb < database/app_permissions.sql
-- The existing app account has SELECT/INSERT but payment/fare updates need UPDATE.
-- This grants no schema administration, deletion, or user-management privileges.
GRANT UPDATE ON railway_reservation.bookings TO 'railway_app'@'127.0.0.1';
GRANT UPDATE ON railway_reservation.booking_passengers TO 'railway_app'@'127.0.0.1';
GRANT UPDATE ON railway_reservation.seat_allocations TO 'railway_app'@'127.0.0.1';
GRANT UPDATE ON railway_reservation.payments TO 'railway_app'@'127.0.0.1';
