-- Railway Reservation System database schema
-- Target: MySQL 8.0.16+ with InnoDB and utf8mb4.
-- Segment-based seat allocations allow the same physical seat to be reused on
-- non-overlapping journey segments of a scheduled train run.
-- Cross-row booking, segment-overlap, payment, and cancellation rules must be
-- enforced in service-layer transactions; see database/SCHEMA_REVIEW.md.

CREATE DATABASE IF NOT EXISTS railway_reservation
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE railway_reservation;

CREATE TABLE users (
  user_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  full_name VARCHAR(120) NOT NULL,
  email VARCHAR(254) NOT NULL,
  phone_number VARCHAR(25) NULL,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('PASSENGER','ADMIN') NOT NULL DEFAULT 'PASSENGER',
  account_status ENUM('ACTIVE','DISABLED') NOT NULL DEFAULT 'ACTIVE',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id),
  UNIQUE KEY uq_users_email (email),
  KEY idx_users_role_status (role, account_status),
  CONSTRAINT chk_users_name CHECK (CHAR_LENGTH(TRIM(full_name)) > 0)
) ENGINE=InnoDB;

CREATE TABLE stations (
  station_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  station_code VARCHAR(10) NOT NULL,
  station_name VARCHAR(120) NOT NULL,
  city VARCHAR(100) NOT NULL,
  state VARCHAR(100) NULL,
  station_status ENUM('ACTIVE','INACTIVE') NOT NULL DEFAULT 'ACTIVE',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (station_id),
  UNIQUE KEY uq_stations_code (station_code),
  KEY idx_stations_name_city (station_name, city),
  CONSTRAINT chk_stations_code CHECK (CHAR_LENGTH(TRIM(station_code)) > 0),
  CONSTRAINT chk_stations_name CHECK (CHAR_LENGTH(TRIM(station_name)) > 0)
) ENGINE=InnoDB;

CREATE TABLE trains (
  train_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  train_number VARCHAR(20) NOT NULL,
  train_name VARCHAR(150) NOT NULL,
  train_status ENUM('ACTIVE','INACTIVE') NOT NULL DEFAULT 'ACTIVE',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (train_id),
  UNIQUE KEY uq_trains_number (train_number),
  KEY idx_trains_status_name (train_status, train_name),
  CONSTRAINT chk_trains_number CHECK (CHAR_LENGTH(TRIM(train_number)) > 0),
  CONSTRAINT chk_trains_name CHECK (CHAR_LENGTH(TRIM(train_name)) > 0)
) ENGINE=InnoDB;

CREATE TABLE routes (
  route_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  route_name VARCHAR(150) NOT NULL,
  route_status ENUM('ACTIVE','INACTIVE') NOT NULL DEFAULT 'ACTIVE',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (route_id),
  KEY idx_routes_status_name (route_status, route_name),
  CONSTRAINT chk_routes_name CHECK (CHAR_LENGTH(TRIM(route_name)) > 0)
) ENGINE=InnoDB;

CREATE TABLE route_stops (
  route_stop_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  route_id BIGINT UNSIGNED NOT NULL,
  station_id BIGINT UNSIGNED NOT NULL,
  stop_sequence SMALLINT UNSIGNED NOT NULL,
  distance_from_origin_km DECIMAL(8,2) NOT NULL DEFAULT 0.00,
  PRIMARY KEY (route_stop_id),
  UNIQUE KEY uq_route_stop_sequence (route_id, stop_sequence),
  UNIQUE KEY uq_route_stop_route_id (route_id, route_stop_id),
  UNIQUE KEY uq_route_stop_snapshot (route_id, route_stop_id, station_id, stop_sequence),
  KEY idx_route_stops_station (station_id, route_id),
  CONSTRAINT fk_route_stops_route FOREIGN KEY (route_id)
    REFERENCES routes (route_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_route_stops_station FOREIGN KEY (station_id)
    REFERENCES stations (station_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_route_stop_sequence CHECK (stop_sequence >= 1),
  CONSTRAINT chk_route_stop_distance CHECK (distance_from_origin_km >= 0)
) ENGINE=InnoDB;

CREATE TABLE train_schedules (
  schedule_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  train_id BIGINT UNSIGNED NOT NULL,
  route_id BIGINT UNSIGNED NOT NULL,
  departure_at DATETIME NOT NULL COMMENT 'Departure from route origin',
  arrival_at DATETIME NOT NULL COMMENT 'Arrival at route terminus',
  schedule_status ENUM('SCHEDULED','CANCELLED','COMPLETED') NOT NULL DEFAULT 'SCHEDULED',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (schedule_id),
  UNIQUE KEY uq_train_schedule_departure (train_id, departure_at),
  UNIQUE KEY uq_schedule_route (schedule_id, route_id),
  UNIQUE KEY uq_schedule_train (schedule_id, train_id),
  KEY idx_schedules_departure_status (departure_at, schedule_status),
  KEY idx_schedules_route_departure (route_id, departure_at),
  CONSTRAINT fk_schedules_train FOREIGN KEY (train_id)
    REFERENCES trains (train_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_schedules_route FOREIGN KEY (route_id)
    REFERENCES routes (route_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_schedule_datetimes CHECK (arrival_at > departure_at)
) ENGINE=InnoDB;

CREATE TABLE schedule_stops (
  schedule_stop_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  schedule_id BIGINT UNSIGNED NOT NULL,
  route_id BIGINT UNSIGNED NOT NULL,
  route_stop_id BIGINT UNSIGNED NOT NULL,
  station_id BIGINT UNSIGNED NOT NULL COMMENT 'Station snapshot for this run',
  stop_sequence SMALLINT UNSIGNED NOT NULL COMMENT 'Sequence snapshot for this run',
  arrival_at DATETIME NULL COMMENT 'May be NULL at the origin',
  departure_at DATETIME NULL COMMENT 'May be NULL at the terminus',
  PRIMARY KEY (schedule_stop_id),
  UNIQUE KEY uq_schedule_route_stop (schedule_id, route_stop_id),
  UNIQUE KEY uq_schedule_stop_sequence (schedule_id, stop_sequence),
  UNIQUE KEY uq_schedule_stop_id (schedule_id, schedule_stop_id),
  KEY idx_schedule_stops_station (station_id, schedule_id, stop_sequence),
  KEY idx_schedule_stops_route_stop (route_id, route_stop_id, schedule_id),
  KEY idx_schedule_stops_arrival (arrival_at),
  KEY idx_schedule_stops_departure (departure_at),
  CONSTRAINT fk_schedule_stops_schedule_route FOREIGN KEY (schedule_id, route_id)
    REFERENCES train_schedules (schedule_id, route_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_schedule_stops_route_stop FOREIGN KEY (route_id, route_stop_id, station_id, stop_sequence)
    REFERENCES route_stops (route_id, route_stop_id, station_id, stop_sequence) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_schedule_stops_station FOREIGN KEY (station_id)
    REFERENCES stations (station_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_schedule_stop_sequence CHECK (stop_sequence >= 1),
  CONSTRAINT chk_schedule_stop_time CHECK (arrival_at IS NOT NULL OR departure_at IS NOT NULL),
  CONSTRAINT chk_schedule_stop_order CHECK (arrival_at IS NULL OR departure_at IS NULL OR departure_at >= arrival_at)
) ENGINE=InnoDB;

CREATE TABLE travel_classes (
  class_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  class_code VARCHAR(12) NOT NULL,
  class_name VARCHAR(80) NOT NULL,
  class_status ENUM('ACTIVE','INACTIVE') NOT NULL DEFAULT 'ACTIVE',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (class_id),
  UNIQUE KEY uq_travel_classes_code (class_code),
  CONSTRAINT chk_class_code CHECK (CHAR_LENGTH(TRIM(class_code)) > 0),
  CONSTRAINT chk_class_name CHECK (CHAR_LENGTH(TRIM(class_name)) > 0)
) ENGINE=InnoDB;

CREATE TABLE route_fares (
  route_fare_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  route_id BIGINT UNSIGNED NOT NULL,
  from_route_stop_id BIGINT UNSIGNED NOT NULL,
  to_route_stop_id BIGINT UNSIGNED NOT NULL,
  class_id BIGINT UNSIGNED NOT NULL,
  fare_amount DECIMAL(10,2) NOT NULL,
  currency_code CHAR(3) NOT NULL DEFAULT 'INR',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (route_fare_id),
  UNIQUE KEY uq_route_fare_segment_class (route_id, from_route_stop_id, to_route_stop_id, class_id),
  CONSTRAINT fk_route_fares_from_stop FOREIGN KEY (route_id, from_route_stop_id)
    REFERENCES route_stops (route_id, route_stop_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_route_fares_to_stop FOREIGN KEY (route_id, to_route_stop_id)
    REFERENCES route_stops (route_id, route_stop_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_route_fares_class FOREIGN KEY (class_id)
    REFERENCES travel_classes (class_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_route_fare_distinct_stops CHECK (from_route_stop_id <> to_route_stop_id),
  CONSTRAINT chk_route_fare_nonnegative CHECK (fare_amount >= 0),
  CONSTRAINT chk_route_fare_currency CHECK (currency_code = UPPER(currency_code))
) ENGINE=InnoDB;

CREATE TABLE seats (
  seat_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  train_id BIGINT UNSIGNED NOT NULL,
  class_id BIGINT UNSIGNED NOT NULL,
  coach_number VARCHAR(12) NOT NULL,
  seat_number VARCHAR(12) NOT NULL,
  berth_type ENUM('LOWER','MIDDLE','UPPER','SIDE_LOWER','SIDE_UPPER','SEAT','NOT_APPLICABLE') NOT NULL DEFAULT 'NOT_APPLICABLE',
  seat_status ENUM('ACTIVE','INACTIVE') NOT NULL DEFAULT 'ACTIVE',
  PRIMARY KEY (seat_id),
  UNIQUE KEY uq_train_coach_seat (train_id, coach_number, seat_number),
  UNIQUE KEY uq_train_seat_class (train_id, seat_id, class_id),
  KEY idx_seats_train_class_status (train_id, class_id, seat_status),
  CONSTRAINT fk_seats_train FOREIGN KEY (train_id)
    REFERENCES trains (train_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_seats_class FOREIGN KEY (class_id)
    REFERENCES travel_classes (class_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_seat_coach CHECK (CHAR_LENGTH(TRIM(coach_number)) > 0),
  CONSTRAINT chk_seat_number CHECK (CHAR_LENGTH(TRIM(seat_number)) > 0)
) ENGINE=InnoDB;

CREATE TABLE schedule_seats (
  schedule_seat_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  schedule_id BIGINT UNSIGNED NOT NULL,
  train_id BIGINT UNSIGNED NOT NULL,
  seat_id BIGINT UNSIGNED NOT NULL,
  class_id BIGINT UNSIGNED NOT NULL,
  operational_status ENUM('IN_SERVICE','OUT_OF_SERVICE') NOT NULL DEFAULT 'IN_SERVICE',
  PRIMARY KEY (schedule_seat_id),
  UNIQUE KEY uq_schedule_physical_seat (schedule_id, seat_id),
  UNIQUE KEY uq_schedule_seat_class (schedule_id, schedule_seat_id, class_id),
  KEY idx_schedule_seat_lookup (schedule_id, class_id, operational_status),
  CONSTRAINT fk_schedule_seats_schedule_train FOREIGN KEY (schedule_id, train_id)
    REFERENCES train_schedules (schedule_id, train_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_schedule_seats_train_seat_class FOREIGN KEY (train_id, seat_id, class_id)
    REFERENCES seats (train_id, seat_id, class_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE bookings (
  booking_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  pnr VARCHAR(20) NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  schedule_id BIGINT UNSIGNED NOT NULL,
  boarding_schedule_stop_id BIGINT UNSIGNED NOT NULL,
  alighting_schedule_stop_id BIGINT UNSIGNED NOT NULL,
  class_id BIGINT UNSIGNED NOT NULL,
  booking_status ENUM('PENDING_PAYMENT','CONFIRMED','PARTIALLY_CANCELLED','CANCELLED','PAYMENT_FAILED','EXPIRED') NOT NULL DEFAULT 'PENDING_PAYMENT',
  train_number_snapshot VARCHAR(20) NOT NULL,
  train_name_snapshot VARCHAR(150) NOT NULL,
  boarding_station_code_snapshot VARCHAR(10) NOT NULL,
  boarding_station_name_snapshot VARCHAR(120) NOT NULL,
  alighting_station_code_snapshot VARCHAR(10) NOT NULL,
  alighting_station_name_snapshot VARCHAR(120) NOT NULL,
  departure_at_snapshot DATETIME NOT NULL,
  arrival_at_snapshot DATETIME NOT NULL,
  class_code_snapshot VARCHAR(12) NOT NULL,
  base_fare_total DECIMAL(10,2) NOT NULL,
  other_charges DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  total_fare DECIMAL(10,2) NOT NULL,
  currency_code CHAR(3) NOT NULL DEFAULT 'INR',
  idempotency_key VARCHAR(128) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  confirmed_at DATETIME NULL,
  PRIMARY KEY (booking_id),
  UNIQUE KEY uq_bookings_pnr (pnr),
  UNIQUE KEY uq_bookings_id_schedule_class (booking_id, schedule_id, class_id),
  KEY idx_bookings_user_created (user_id, created_at),
  KEY idx_bookings_schedule_status (schedule_id, booking_status),
  KEY idx_bookings_boarding_stops (schedule_id, boarding_schedule_stop_id, alighting_schedule_stop_id),
  UNIQUE KEY uq_bookings_user_idempotency (user_id, idempotency_key),
  CONSTRAINT fk_bookings_user FOREIGN KEY (user_id)
    REFERENCES users (user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_bookings_schedule FOREIGN KEY (schedule_id)
    REFERENCES train_schedules (schedule_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_bookings_class FOREIGN KEY (class_id)
    REFERENCES travel_classes (class_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_bookings_boarding_stop FOREIGN KEY (schedule_id, boarding_schedule_stop_id)
    REFERENCES schedule_stops (schedule_id, schedule_stop_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_bookings_alighting_stop FOREIGN KEY (schedule_id, alighting_schedule_stop_id)
    REFERENCES schedule_stops (schedule_id, schedule_stop_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_booking_fare_nonnegative CHECK (base_fare_total >= 0 AND other_charges >= 0 AND total_fare >= 0),
  CONSTRAINT chk_booking_total_matches CHECK (total_fare = base_fare_total + other_charges),
  CONSTRAINT chk_booking_currency CHECK (currency_code = UPPER(currency_code)),
  CONSTRAINT chk_booking_distinct_stops CHECK (boarding_schedule_stop_id <> alighting_schedule_stop_id),
  CONSTRAINT chk_booking_times CHECK (arrival_at_snapshot > departure_at_snapshot)
) ENGINE=InnoDB;

CREATE TABLE booking_passengers (
  booking_passenger_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  booking_id BIGINT UNSIGNED NOT NULL,
  passenger_name VARCHAR(120) NOT NULL,
  age TINYINT UNSIGNED NOT NULL,
  gender VARCHAR(30) NULL,
  berth_preference ENUM('LOWER','MIDDLE','UPPER','SIDE_LOWER','SIDE_UPPER','NO_PREFERENCE') NOT NULL DEFAULT 'NO_PREFERENCE',
  passenger_fare DECIMAL(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (booking_passenger_id),
  UNIQUE KEY uq_booking_passenger_id (booking_id, booking_passenger_id),
  KEY idx_booking_passengers_booking (booking_id),
  CONSTRAINT fk_booking_passengers_booking FOREIGN KEY (booking_id)
    REFERENCES bookings (booking_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_booking_passenger_age CHECK (age <= 120),
  CONSTRAINT chk_booking_passenger_fare CHECK (passenger_fare >= 0),
  CONSTRAINT chk_booking_passenger_name CHECK (CHAR_LENGTH(TRIM(passenger_name)) > 0)
) ENGINE=InnoDB;

-- Current allocation state per booking passenger. The application locks the
-- schedule_seats row before checking active allocations for overlapping segments.
CREATE TABLE seat_allocations (
  allocation_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  booking_id BIGINT UNSIGNED NOT NULL,
  schedule_id BIGINT UNSIGNED NOT NULL,
  class_id BIGINT UNSIGNED NOT NULL,
  booking_passenger_id BIGINT UNSIGNED NOT NULL,
  schedule_seat_id BIGINT UNSIGNED NOT NULL,
  allocation_status ENUM('HELD','CONFIRMED','RELEASED','EXPIRED') NOT NULL DEFAULT 'HELD',
  hold_expires_at DATETIME NULL,
  allocated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  released_at DATETIME NULL,
  PRIMARY KEY (allocation_id),
  UNIQUE KEY uq_seat_allocation_passenger (booking_passenger_id),
  KEY idx_seat_allocation_conflicts (schedule_id, schedule_seat_id, allocation_status, hold_expires_at),
  KEY idx_seat_allocations_booking (booking_id, allocation_status),
  CONSTRAINT fk_seat_alloc_booking_schedule_class FOREIGN KEY (booking_id, schedule_id, class_id)
    REFERENCES bookings (booking_id, schedule_id, class_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_seat_alloc_booking_passenger FOREIGN KEY (booking_id, booking_passenger_id)
    REFERENCES booking_passengers (booking_id, booking_passenger_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_seat_alloc_schedule_seat_class FOREIGN KEY (schedule_id, schedule_seat_id, class_id)
    REFERENCES schedule_seats (schedule_id, schedule_seat_id, class_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_held_allocation_expiry CHECK (allocation_status <> 'HELD' OR hold_expires_at IS NOT NULL)
) ENGINE=InnoDB;

CREATE TABLE payments (
  payment_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  booking_id BIGINT UNSIGNED NOT NULL,
  payment_provider VARCHAR(60) NOT NULL DEFAULT 'SIMULATED',
  payment_method ENUM('CARD','UPI','WALLET','NET_BANKING','SIMULATED') NOT NULL DEFAULT 'SIMULATED',
  amount DECIMAL(10,2) NOT NULL,
  currency_code CHAR(3) NOT NULL DEFAULT 'INR',
  payment_status ENUM('INITIATED','SUCCEEDED','FAILED','CANCELLED') NOT NULL DEFAULT 'INITIATED',
  provider_transaction_id VARCHAR(160) NULL,
  idempotency_key VARCHAR(128) NULL,
  failure_code VARCHAR(80) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  completed_at DATETIME NULL,
  PRIMARY KEY (payment_id),
  KEY idx_payments_booking_status (booking_id, payment_status, created_at),
  UNIQUE KEY uq_payment_provider_transaction (payment_provider, provider_transaction_id),
  UNIQUE KEY uq_payment_idempotency (payment_provider, idempotency_key),
  CONSTRAINT fk_payments_booking FOREIGN KEY (booking_id)
    REFERENCES bookings (booking_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_payment_amount CHECK (amount >= 0),
  CONSTRAINT chk_payment_currency CHECK (currency_code = UPPER(currency_code))
) ENGINE=InnoDB;

CREATE TABLE cancellations (
  cancellation_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  booking_id BIGINT UNSIGNED NOT NULL,
  requested_by_user_id BIGINT UNSIGNED NOT NULL,
  cancellation_status ENUM('REQUESTED','COMPLETED','FAILED') NOT NULL DEFAULT 'REQUESTED',
  reason VARCHAR(255) NULL,
  requested_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at DATETIME NULL,
  PRIMARY KEY (cancellation_id),
  UNIQUE KEY uq_cancellation_booking_pair (cancellation_id, booking_id),
  KEY idx_cancellations_booking_status (booking_id, cancellation_status, requested_at),
  CONSTRAINT fk_cancellations_booking FOREIGN KEY (booking_id)
    REFERENCES bookings (booking_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_cancellations_requester FOREIGN KEY (requested_by_user_id)
    REFERENCES users (user_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE cancellation_items (
  cancellation_item_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  cancellation_id BIGINT UNSIGNED NOT NULL,
  booking_id BIGINT UNSIGNED NOT NULL,
  booking_passenger_id BIGINT UNSIGNED NOT NULL,
  item_status ENUM('REQUESTED','COMPLETED','FAILED') NOT NULL DEFAULT 'REQUESTED',
  cancellation_charge DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  refund_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at DATETIME NULL,
  PRIMARY KEY (cancellation_item_id),
  UNIQUE KEY uq_cancellation_item_pair (cancellation_id, booking_passenger_id),
  UNIQUE KEY uq_cancellation_item_booking (cancellation_item_id, booking_id),
  KEY idx_cancellation_items_passenger (booking_passenger_id, item_status),
  CONSTRAINT fk_cancellation_items_header FOREIGN KEY (cancellation_id, booking_id)
    REFERENCES cancellations (cancellation_id, booking_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_cancellation_items_passenger FOREIGN KEY (booking_id, booking_passenger_id)
    REFERENCES booking_passengers (booking_id, booking_passenger_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_cancellation_amounts CHECK (cancellation_charge >= 0 AND refund_amount >= 0)
) ENGINE=InnoDB;

CREATE TABLE refunds (
  refund_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  cancellation_item_id BIGINT UNSIGNED NOT NULL,
  refund_provider VARCHAR(60) NOT NULL DEFAULT 'SIMULATED',
  amount DECIMAL(10,2) NOT NULL,
  currency_code CHAR(3) NOT NULL DEFAULT 'INR',
  refund_status ENUM('PENDING','PROCESSING','SUCCEEDED','FAILED') NOT NULL DEFAULT 'PENDING',
  provider_refund_id VARCHAR(160) NULL,
  idempotency_key VARCHAR(128) NULL,
  failure_code VARCHAR(80) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  completed_at DATETIME NULL,
  PRIMARY KEY (refund_id),
  KEY idx_refunds_item_status (cancellation_item_id, refund_status, created_at),
  UNIQUE KEY uq_refund_provider_reference (refund_provider, provider_refund_id),
  UNIQUE KEY uq_refund_idempotency (refund_provider, idempotency_key),
  CONSTRAINT fk_refunds_cancellation_item FOREIGN KEY (cancellation_item_id)
    REFERENCES cancellation_items (cancellation_item_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_refund_amount CHECK (amount >= 0),
  CONSTRAINT chk_refund_currency CHECK (currency_code = UPPER(currency_code))
) ENGINE=InnoDB;

CREATE TABLE notifications (
  notification_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NOT NULL,
  booking_id BIGINT UNSIGNED NULL,
  channel ENUM('EMAIL','SMS') NOT NULL,
  notification_type ENUM('BOOKING_CONFIRMATION','CANCELLATION_CONFIRMATION','REFUND_UPDATE','GENERAL') NOT NULL,
  delivery_status ENUM('QUEUED','SENT','FAILED') NOT NULL DEFAULT 'QUEUED',
  provider_reference VARCHAR(160) NULL,
  failure_code VARCHAR(80) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  sent_at DATETIME NULL,
  PRIMARY KEY (notification_id),
  KEY idx_notifications_user_created (user_id, created_at),
  KEY idx_notifications_booking_type (booking_id, notification_type, delivery_status),
  CONSTRAINT fk_notifications_user FOREIGN KEY (user_id)
    REFERENCES users (user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_notifications_booking FOREIGN KEY (booking_id)
    REFERENCES bookings (booking_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;
