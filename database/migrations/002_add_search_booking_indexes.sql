-- Issue #41: add indexes for high-volume passenger searches and booking history.
-- Target: MySQL 8.0+. Safe to run more than once; existing indexes are skipped.
USE railway_reservation;

DELIMITER $$

DROP PROCEDURE IF EXISTS apply_index_if_missing$$
CREATE PROCEDURE apply_index_if_missing(
    IN target_table VARCHAR(64),
    IN target_index VARCHAR(64),
    IN index_ddl TEXT
)
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.statistics
        WHERE table_schema = DATABASE()
          AND table_name = target_table
          AND index_name = target_index
    ) THEN
        SET @performance_index_ddl = index_ddl;
        PREPARE performance_index_statement FROM @performance_index_ddl;
        EXECUTE performance_index_statement;
        DEALLOCATE PREPARE performance_index_statement;
    END IF;
END$$

DELIMITER ;

CALL apply_index_if_missing(
    'stations',
    'idx_stations_active_city',
    'CREATE INDEX idx_stations_active_city ON stations (station_status, city, station_name, station_code)'
);

CALL apply_index_if_missing(
    'schedule_stops',
    'idx_schedule_stops_station_departure',
    'CREATE INDEX idx_schedule_stops_station_departure ON schedule_stops (station_id, departure_at, schedule_id, stop_sequence)'
);

CALL apply_index_if_missing(
    'schedule_stops',
    'idx_schedule_stops_station_arrival',
    'CREATE INDEX idx_schedule_stops_station_arrival ON schedule_stops (station_id, schedule_id, stop_sequence, arrival_at)'
);

CALL apply_index_if_missing(
    'route_fares',
    'idx_route_fares_segment_price',
    'CREATE INDEX idx_route_fares_segment_price ON route_fares (route_id, from_route_stop_id, to_route_stop_id, fare_amount, class_id)'
);

CALL apply_index_if_missing(
    'bookings',
    'idx_bookings_user_departure_created',
    'CREATE INDEX idx_bookings_user_departure_created ON bookings (user_id, departure_at_snapshot, created_at DESC, booking_id)'
);

CALL apply_index_if_missing(
    'seat_allocations',
    'idx_seat_allocations_booking_passenger',
    'CREATE INDEX idx_seat_allocations_booking_passenger ON seat_allocations (booking_id, booking_passenger_id)'
);

DROP PROCEDURE apply_index_if_missing;
