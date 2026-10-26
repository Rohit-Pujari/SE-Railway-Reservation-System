-- Small, repeatable demo dataset for the passenger station and train search.
-- The sample schedules are created for the day after this script is run.
USE railway_reservation;

INSERT IGNORE INTO stations (station_code, station_name, city, state) VALUES
  ('SBC', 'KSR Bengaluru City Junction', 'Bengaluru', 'Karnataka'),
  ('MYS', 'Mysuru Junction', 'Mysuru', 'Karnataka'),
  ('CBE', 'Coimbatore Junction', 'Coimbatore', 'Tamil Nadu'),
  ('MAS', 'MGR Chennai Central', 'Chennai', 'Tamil Nadu'),
  ('HYB', 'Hyderabad Deccan', 'Hyderabad', 'Telangana'),
  ('PUNE', 'Pune Junction', 'Pune', 'Maharashtra'),
  ('CSMT', 'Chhatrapati Shivaji Maharaj Terminus', 'Mumbai', 'Maharashtra');

SET @demo_sbc = (SELECT station_id FROM stations WHERE station_code = 'SBC');
SET @demo_mys = (SELECT station_id FROM stations WHERE station_code = 'MYS');
SET @demo_cbe = (SELECT station_id FROM stations WHERE station_code = 'CBE');
SET @demo_mas = (SELECT station_id FROM stations WHERE station_code = 'MAS');
SET @demo_hyb = (SELECT station_id FROM stations WHERE station_code = 'HYB');
SET @demo_pune = (SELECT station_id FROM stations WHERE station_code = 'PUNE');
SET @demo_csmt = (SELECT station_id FROM stations WHERE station_code = 'CSMT');

INSERT IGNORE INTO trains (train_number, train_name) VALUES
  ('90001', 'Demo Southern Daylight'),
  ('90002', 'Demo Garden City Express'),
  ('90003', 'Demo Deccan Connector'),
  ('90004', 'Demo Mysuru Intercity');

SET @demo_train_90001 = (SELECT train_id FROM trains WHERE train_number = '90001');
SET @demo_train_90002 = (SELECT train_id FROM trains WHERE train_number = '90002');
SET @demo_train_90003 = (SELECT train_id FROM trains WHERE train_number = '90003');
SET @demo_train_90004 = (SELECT train_id FROM trains WHERE train_number = '90004');

INSERT INTO routes (route_name)
SELECT 'Demo: Bengaluru to Chennai via Mysuru and Coimbatore'
WHERE NOT EXISTS (
  SELECT 1 FROM routes WHERE route_name = 'Demo: Bengaluru to Chennai via Mysuru and Coimbatore'
);
INSERT INTO routes (route_name)
SELECT 'Demo: Bengaluru to Mumbai via Hyderabad and Pune'
WHERE NOT EXISTS (
  SELECT 1 FROM routes WHERE route_name = 'Demo: Bengaluru to Mumbai via Hyderabad and Pune'
);
INSERT INTO routes (route_name)
SELECT 'Demo: Chennai to Bengaluru via Coimbatore and Mysuru'
WHERE NOT EXISTS (
  SELECT 1 FROM routes WHERE route_name = 'Demo: Chennai to Bengaluru via Coimbatore and Mysuru'
);

SET @demo_route_blr_maa = (
  SELECT route_id FROM routes
  WHERE route_name = 'Demo: Bengaluru to Chennai via Mysuru and Coimbatore'
  ORDER BY route_id LIMIT 1
);
SET @demo_route_blr_bom = (
  SELECT route_id FROM routes
  WHERE route_name = 'Demo: Bengaluru to Mumbai via Hyderabad and Pune'
  ORDER BY route_id LIMIT 1
);
SET @demo_route_maa_blr = (
  SELECT route_id FROM routes
  WHERE route_name = 'Demo: Chennai to Bengaluru via Coimbatore and Mysuru'
  ORDER BY route_id LIMIT 1
);

INSERT IGNORE INTO route_stops (route_id, station_id, stop_sequence, distance_from_origin_km) VALUES
  (@demo_route_blr_maa, @demo_sbc, 1, 0),
  (@demo_route_blr_maa, @demo_mys, 2, 139),
  (@demo_route_blr_maa, @demo_cbe, 3, 328),
  (@demo_route_blr_maa, @demo_mas, 4, 497),
  (@demo_route_blr_bom, @demo_sbc, 1, 0),
  (@demo_route_blr_bom, @demo_hyb, 2, 570),
  (@demo_route_blr_bom, @demo_pune, 3, 1020),
  (@demo_route_blr_bom, @demo_csmt, 4, 1190),
  (@demo_route_maa_blr, @demo_mas, 1, 0),
  (@demo_route_maa_blr, @demo_cbe, 2, 500),
  (@demo_route_maa_blr, @demo_mys, 3, 690),
  (@demo_route_maa_blr, @demo_sbc, 4, 830);

SET @demo_day = DATE_ADD(CURRENT_DATE(), INTERVAL 1 DAY);

INSERT IGNORE INTO train_schedules (train_id, route_id, departure_at, arrival_at)
VALUES
  (@demo_train_90001, @demo_route_blr_maa,
   CAST(CONCAT(@demo_day, ' 06:15:00') AS DATETIME),
   CAST(CONCAT(@demo_day, ' 17:40:00') AS DATETIME)),
  (@demo_train_90002, @demo_route_blr_maa,
   CAST(CONCAT(@demo_day, ' 10:00:00') AS DATETIME),
   CAST(CONCAT(@demo_day, ' 21:25:00') AS DATETIME)),
  (@demo_train_90003, @demo_route_blr_bom,
   CAST(CONCAT(@demo_day, ' 05:45:00') AS DATETIME),
   CAST(CONCAT(@demo_day, ' 21:15:00') AS DATETIME)),
  (@demo_train_90004, @demo_route_maa_blr,
   CAST(CONCAT(@demo_day, ' 07:10:00') AS DATETIME),
   CAST(CONCAT(@demo_day, ' 18:30:00') AS DATETIME));

-- Snapshot the route stops and sample times onto each scheduled train run.
INSERT IGNORE INTO schedule_stops (
  schedule_id, route_id, route_stop_id, station_id, stop_sequence, arrival_at, departure_at
)
SELECT
  schedule.schedule_id,
  schedule.route_id,
  route_stop.route_stop_id,
  route_stop.station_id,
  route_stop.stop_sequence,
  CASE
    WHEN route_stop.stop_sequence = 1 THEN NULL
    WHEN train.train_number = '90001' AND route_stop.stop_sequence = 2 THEN CAST(CONCAT(@demo_day, ' 08:50:00') AS DATETIME)
    WHEN train.train_number = '90001' AND route_stop.stop_sequence = 3 THEN CAST(CONCAT(@demo_day, ' 13:00:00') AS DATETIME)
    WHEN train.train_number = '90001' AND route_stop.stop_sequence = 4 THEN CAST(CONCAT(@demo_day, ' 17:40:00') AS DATETIME)
    WHEN train.train_number = '90002' AND route_stop.stop_sequence = 2 THEN CAST(CONCAT(@demo_day, ' 12:25:00') AS DATETIME)
    WHEN train.train_number = '90002' AND route_stop.stop_sequence = 3 THEN CAST(CONCAT(@demo_day, ' 16:35:00') AS DATETIME)
    WHEN train.train_number = '90002' AND route_stop.stop_sequence = 4 THEN CAST(CONCAT(@demo_day, ' 21:25:00') AS DATETIME)
    WHEN train.train_number = '90003' AND route_stop.stop_sequence = 2 THEN CAST(CONCAT(@demo_day, ' 10:30:00') AS DATETIME)
    WHEN train.train_number = '90003' AND route_stop.stop_sequence = 3 THEN CAST(CONCAT(@demo_day, ' 17:45:00') AS DATETIME)
    WHEN train.train_number = '90003' AND route_stop.stop_sequence = 4 THEN CAST(CONCAT(@demo_day, ' 21:15:00') AS DATETIME)
    WHEN train.train_number = '90004' AND route_stop.stop_sequence = 2 THEN CAST(CONCAT(@demo_day, ' 11:20:00') AS DATETIME)
    WHEN train.train_number = '90004' AND route_stop.stop_sequence = 3 THEN CAST(CONCAT(@demo_day, ' 15:50:00') AS DATETIME)
    WHEN train.train_number = '90004' AND route_stop.stop_sequence = 4 THEN CAST(CONCAT(@demo_day, ' 18:30:00') AS DATETIME)
  END AS arrival_at,
  CASE
    WHEN route_stop.stop_sequence = 1 AND train.train_number = '90001' THEN CAST(CONCAT(@demo_day, ' 06:15:00') AS DATETIME)
    WHEN route_stop.stop_sequence = 1 AND train.train_number = '90002' THEN CAST(CONCAT(@demo_day, ' 10:00:00') AS DATETIME)
    WHEN route_stop.stop_sequence = 1 AND train.train_number = '90003' THEN CAST(CONCAT(@demo_day, ' 05:45:00') AS DATETIME)
    WHEN route_stop.stop_sequence = 1 AND train.train_number = '90004' THEN CAST(CONCAT(@demo_day, ' 07:10:00') AS DATETIME)
    WHEN train.train_number = '90001' AND route_stop.stop_sequence = 2 THEN CAST(CONCAT(@demo_day, ' 09:00:00') AS DATETIME)
    WHEN train.train_number = '90001' AND route_stop.stop_sequence = 3 THEN CAST(CONCAT(@demo_day, ' 13:10:00') AS DATETIME)
    WHEN train.train_number = '90002' AND route_stop.stop_sequence = 2 THEN CAST(CONCAT(@demo_day, ' 12:35:00') AS DATETIME)
    WHEN train.train_number = '90002' AND route_stop.stop_sequence = 3 THEN CAST(CONCAT(@demo_day, ' 16:45:00') AS DATETIME)
    WHEN train.train_number = '90003' AND route_stop.stop_sequence = 2 THEN CAST(CONCAT(@demo_day, ' 10:45:00') AS DATETIME)
    WHEN train.train_number = '90003' AND route_stop.stop_sequence = 3 THEN CAST(CONCAT(@demo_day, ' 17:55:00') AS DATETIME)
    WHEN train.train_number = '90004' AND route_stop.stop_sequence = 2 THEN CAST(CONCAT(@demo_day, ' 11:30:00') AS DATETIME)
    WHEN train.train_number = '90004' AND route_stop.stop_sequence = 3 THEN CAST(CONCAT(@demo_day, ' 16:00:00') AS DATETIME)
  END AS departure_at
FROM train_schedules AS schedule
JOIN trains AS train ON train.train_id = schedule.train_id
JOIN route_stops AS route_stop ON route_stop.route_id = schedule.route_id
WHERE DATE(schedule.departure_at) = @demo_day
  AND train.train_number IN ('90001', '90002', '90003', '90004');
