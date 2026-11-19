"""Populate a local railway_reservation database with a month of demo service.

The script renames earlier demo-prefixed rows, seeds a Karnataka station
network with five connecting services from each origin, and schedules every
service on each date in the current month. Past services are marked COMPLETED.
It creates two reserved local demo accounts and does not alter existing
bookings, payments, cancellations, or refunds.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, time, timedelta
from getpass import getpass
from pathlib import Path
import sys

import mysql.connector
from werkzeug.security import check_password_hash, generate_password_hash

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import DatabaseConfig  # noqa: E402


STATION_RENAMES = (
    ("DMUM", "MMCT", "Mumbai Central", "Mumbai", "Maharashtra"),
    ("DPUN", "SVJR", "Pune Shivajinagar", "Pune", "Maharashtra"),
    ("DSOL", "SUR", "Solapur Junction", "Solapur", "Maharashtra"),
    ("DHYD", "KCG", "Hyderabad Kacheguda", "Hyderabad", "Telangana"),
    ("DCHN", "MS", "Chennai Egmore", "Chennai", "Tamil Nadu"),
)

ADDITIONAL_STATIONS = (
    ("NDLS", "New Delhi Railway Station", "New Delhi", "Delhi"),
    ("JP", "Jaipur Junction", "Jaipur", "Rajasthan"),
    ("ADI", "Ahmedabad Junction", "Ahmedabad", "Gujarat"),
    ("ST", "Surat Railway Station", "Surat", "Gujarat"),
    ("LKO", "Lucknow Charbagh", "Lucknow", "Uttar Pradesh"),
    ("BSB", "Varanasi Junction", "Varanasi", "Uttar Pradesh"),
    ("HWH", "Howrah Junction", "Kolkata", "West Bengal"),
    ("BBS", "Bhubaneswar Railway Station", "Bhubaneswar", "Odisha"),
    ("NGP", "Nagpur Junction", "Nagpur", "Maharashtra"),
    ("BPL", "Bhopal Junction", "Bhopal", "Madhya Pradesh"),
    ("MAQ", "Mangaluru Central", "Mangaluru", "Karnataka"),
    ("MAO", "Madgaon Junction", "Madgaon", "Goa"),
    ("ERS", "Ernakulam Junction", "Kochi", "Kerala"),
)

CLASS_RENAMES = (
    ("DEMO-SL", "SL", "Sleeper"),
    ("DEMO-3A", "3A", "AC 3 Tier"),
)

ROUTE_DEFINITIONS = {
    "Bengaluru to Chennai via Mysuru and Coimbatore": (
        "Bengaluru to Chennai via Mysuru and Coimbatore",
        (("SBC", 0), ("MYS", 139), ("CBE", 328), ("MAS", 497)),
    ),
    "Bengaluru to Mumbai via Hyderabad and Pune": (
        "Bengaluru to Mumbai via Hyderabad and Pune",
        (("SBC", 0), ("HYB", 570), ("PUNE", 1020), ("CSMT", 1190)),
    ),
    "Chennai to Bengaluru via Coimbatore and Mysuru": (
        "Chennai to Bengaluru via Coimbatore and Mysuru",
        (("MAS", 0), ("CBE", 500), ("MYS", 690), ("SBC", 830)),
    ),
    "Mumbai Central to Chennai Egmore via Pune and Hyderabad": (
        "Mumbai Central to Chennai Egmore via Pune and Hyderabad",
        (("MMCT", 0), ("SVJR", 150), ("SUR", 400), ("KCG", 600), ("MS", 1200)),
    ),
    "Mumbai to New Delhi via Surat, Ahmedabad, and Jaipur": (
        "Mumbai to New Delhi via Surat, Ahmedabad, and Jaipur",
        (("MMCT", 0), ("ST", 250), ("ADI", 500), ("JP", 900), ("NDLS", 1375)),
    ),
    "New Delhi to Kolkata via Lucknow and Varanasi": (
        "New Delhi to Kolkata via Lucknow and Varanasi",
        (("NDLS", 0), ("LKO", 510), ("BSB", 760), ("HWH", 1450)),
    ),
    "Kolkata to Mumbai via Bhubaneswar, Nagpur, and Bhopal": (
        "Kolkata to Mumbai via Bhubaneswar, Nagpur, and Bhopal",
        (("HWH", 0), ("BBS", 440), ("NGP", 1150), ("BPL", 1450), ("MMCT", 1950)),
    ),
    "Mumbai to Kochi via Madgaon and Mangaluru": (
        "Mumbai to Kochi via Madgaon and Mangaluru",
        (("MMCT", 0), ("MAO", 580), ("MAQ", 780), ("ERS", 1160)),
    ),
}

# Four trains per route. Existing records are renamed into the first entries.
FLEET = {
    "Bengaluru to Chennai via Mysuru and Coimbatore": (
        ("12611", "Southern Daylight", "90001"),
        ("12612", "Mysuru Intercity", "90004"),
        ("12613", "Kaveri Express", None),
        ("12614", "Nilgiri Link", None),
    ),
    "Bengaluru to Mumbai via Hyderabad and Pune": (
        ("12701", "Garden City Express", "90002"),
        ("12702", "Hyderabad Intercity", None),
        ("12703", "Deccan Mail", None),
        ("12704", "Pune Superfast", None),
    ),
    "Chennai to Bengaluru via Coimbatore and Mysuru": (
        ("12615", "Deccan Connector", "90003"),
        ("12616", "Coromandel Link", None),
        ("12617", "Kovai Night Express", None),
        ("12618", "Southern Cross Express", None),
    ),
    "Mumbai Central to Chennai Egmore via Pune and Hyderabad": (
        ("12051", "Deccan Express", "DEMO-101"),
        ("12052", "Southern Express", "DEMO-102"),
        ("12053", "Solapur Intercity", None),
        ("12054", "Chennai Link", None),
    ),
    "Mumbai to New Delhi via Surat, Ahmedabad, and Jaipur": (
        ("12901", "Western Coast Express", None),
        ("12902", "Sabarmati Mail", None),
        ("12903", "Jaipur Superfast", None),
        ("12904", "Aravali Express", None),
    ),
    "New Delhi to Kolkata via Lucknow and Varanasi": (
        ("12401", "Lucknow Mail", None),
        ("12402", "Kashi Express", None),
        ("12403", "Ganga Intercity", None),
        ("12404", "Awadh Express", None),
    ),
    "Kolkata to Mumbai via Bhubaneswar, Nagpur, and Bhopal": (
        ("12801", "Eastern Coast Express", None),
        ("12802", "Kalinga Intercity", None),
        ("12803", "Central India Express", None),
        ("12804", "Bhopal Link", None),
    ),
    "Mumbai to Kochi via Madgaon and Mangaluru": (
        ("16501", "Malabar Express", None),
        ("16502", "Mangaluru Intercity", None),
        ("16503", "Konkan Coast Express", None),
        ("16504", "Ernakulam Link", None),
    ),
}

LEGACY_ROUTE_RENAMES = {
    "Demo: Bengaluru to Chennai via Mysuru and Coimbatore": "Bengaluru to Chennai via Mysuru and Coimbatore",
    "Demo: Bengaluru to Mumbai via Hyderabad and Pune": "Bengaluru to Mumbai via Hyderabad and Pune",
    "Demo: Chennai to Bengaluru via Coimbatore and Mysuru": "Chennai to Bengaluru via Coimbatore and Mysuru",
    "DEMO: Mumbai - Pune - Solapur - Hyderabad - Chennai": "Mumbai Central to Chennai Egmore via Pune and Hyderabad",
}

# Major operating stations identified on South Western Railway's 2026 map and
# division station lists. This is a local demo network, not a complete official
# timetable. A route is generated from each origin so every ordered station
# pair has five daily searchable demo services.
KARNATAKA_STATIONS = (
    ("SBC", "KSR Bengaluru City Junction", "Bengaluru", "Karnataka", 12.977, 77.571),
    ("BNC", "Bengaluru Cantonment", "Bengaluru", "Karnataka", 12.998, 77.618),
    ("YPR", "Yesvantpur Junction", "Bengaluru", "Karnataka", 13.028, 77.551),
    ("SMVB", "Sir M. Visvesvaraya Terminal", "Bengaluru", "Karnataka", 13.007, 77.692),
    ("KGI", "Kengeri", "Bengaluru", "Karnataka", 12.916, 77.483),
    ("TK", "Tumakuru", "Tumakuru", "Karnataka", 13.338, 77.102),
    ("MYA", "Mandya", "Mandya", "Karnataka", 12.522, 76.897),
    ("MYS", "Mysuru Junction", "Mysuru", "Karnataka", 12.296, 76.640),
    ("CMNR", "Chamarajanagar", "Chamarajanagar", "Karnataka", 11.926, 76.943),
    ("ASK", "Arsikere Junction", "Arsikere", "Karnataka", 13.313, 76.257),
    ("HAS", "Hassan", "Hassan", "Karnataka", 13.007, 76.102),
    ("SKLR", "Sakleshpur", "Sakleshpur", "Karnataka", 12.941, 75.790),
    ("CMGR", "Chikkamagaluru", "Chikkamagaluru", "Karnataka", 13.315, 75.775),
    ("SMET", "Shivamogga Town", "Shivamogga", "Karnataka", 13.929, 75.568),
    ("RRB", "Birur Junction", "Birur", "Karnataka", 13.599, 76.060),
    ("DVG", "Davangere", "Davangere", "Karnataka", 14.466, 75.922),
    ("HRR", "Harihar", "Harihar", "Karnataka", 14.512, 75.807),
    ("CTA", "Chitradurga", "Chitradurga", "Karnataka", 14.227, 76.398),
    ("HVR", "Haveri", "Haveri", "Karnataka", 14.795, 75.399),
    ("UBL", "Hubballi Junction", "Hubballi", "Karnataka", 15.365, 75.124),
    ("DWR", "Dharwad", "Dharwad", "Karnataka", 15.459, 75.008),
    ("GDG", "Gadag Junction", "Gadag", "Karnataka", 15.416, 75.629),
    ("BGK", "Bagalkot", "Bagalkot", "Karnataka", 16.186, 75.696),
    ("BJP", "Vijayapura", "Vijayapura", "Karnataka", 16.830, 75.710),
    ("BGM", "Belagavi", "Belagavi", "Karnataka", 15.850, 74.498),
    ("LWR", "Londa Junction", "Londa", "Karnataka", 15.467, 74.521),
    ("BAY", "Ballari Junction", "Ballari", "Karnataka", 15.140, 76.920),
    ("HPT", "Hosapete Junction", "Hosapete", "Karnataka", 15.270, 76.390),
    ("KBL", "Koppal", "Koppal", "Karnataka", 15.350, 76.150),
    ("RC", "Raichur", "Raichur", "Karnataka", 16.210, 77.350),
    ("WADI", "Wadi Junction", "Wadi", "Karnataka", 16.870, 76.970),
    ("KLBG", "Kalaburagi Junction", "Kalaburagi", "Karnataka", 17.330, 76.830),
    ("MAQ", "Mangaluru Central", "Mangaluru", "Karnataka", 12.863, 74.843),
    ("MAJN", "Mangaluru Junction", "Mangaluru", "Karnataka", 12.871, 74.872),
    ("UD", "Udupi", "Udupi", "Karnataka", 13.340, 74.750),
    ("KAWR", "Karwar", "Karwar", "Karnataka", 14.810, 74.130),
)


def build_karnataka_network():
    stations = tuple(row[:4] for row in KARNATAKA_STATIONS)
    routes = {}
    fleet = {}
    for source_index, source in enumerate(KARNATAKA_STATIONS, start=1):
        source_code, source_name, *_metadata, source_lat, source_lon = source
        others = sorted(
            (row for row in KARNATAKA_STATIONS if row[0] != source_code),
            key=lambda row: ((row[4] - source_lat) ** 2 + (row[5] - source_lon) ** 2, row[0]),
        )
        ordered = [source, *others]
        stops = [(source_code, 0)]
        previous_distance = 0
        for station in ordered[1:]:
            lat_delta = (station[4] - source_lat) * 111
            lon_delta = (station[5] - source_lon) * 111 * 0.85
            distance = max(previous_distance + 1, round((lat_delta**2 + lon_delta**2) ** 0.5 * 1.15))
            stops.append((station[0], distance))
            previous_distance = distance
        route_name = f"Karnataka network from {source_name}"
        routes[route_name] = (route_name, tuple(stops))
        fleet[route_name] = tuple(
            (f"KA{source_index:02d}{service_index:02d}",
             f"Karnataka Connector {source_code} {service_index}", None)
            for service_index in range(1, 6)
        )
    return stations, routes, fleet


ADDITIONAL_STATIONS, ROUTE_DEFINITIONS, FLEET = build_karnataka_network()
STATION_RENAMES = ()
LEGACY_ROUTE_RENAMES = {}


def scalar(cursor, sql, params=()):
    cursor.execute(sql, params)
    row = cursor.fetchone()
    return None if row is None else row[0]


def ensure_station(cursor, code, name, city, state):
    cursor.execute(
        "INSERT IGNORE INTO stations (station_code, station_name, city, state, station_status) "
        "VALUES (%s, %s, %s, %s, 'ACTIVE')",
        (code, name, city, state),
    )
    station_id = scalar(cursor, "SELECT station_id FROM stations WHERE station_code = %s", (code,))
    if station_id is None:
        raise RuntimeError(f"Could not find station {code} after inserting it.")
    cursor.execute(
        "UPDATE stations SET station_name = %s, city = %s, state = %s, station_status = 'ACTIVE' "
        "WHERE station_id = %s",
        (name, city, state, station_id),
    )
    return int(station_id)


def ensure_route(cursor, route_name, stops):
    route_id = scalar(cursor, "SELECT route_id FROM routes WHERE route_name = %s ORDER BY route_id LIMIT 1", (route_name,))
    if route_id is None:
        old_name = next((old for old, new in LEGACY_ROUTE_RENAMES.items() if new == route_name), None)
        if old_name is not None:
            route_id = scalar(cursor, "SELECT route_id FROM routes WHERE route_name = %s ORDER BY route_id LIMIT 1", (old_name,))
            if route_id is not None:
                cursor.execute("UPDATE routes SET route_name = %s, route_status = 'ACTIVE' WHERE route_id = %s", (route_name, route_id))
    if route_id is None:
        cursor.execute("INSERT INTO routes (route_name, route_status) VALUES (%s, 'ACTIVE')", (route_name,))
        route_id = cursor.lastrowid
    else:
        cursor.execute("UPDATE routes SET route_status = 'ACTIVE' WHERE route_id = %s", (route_id,))

    for sequence, (station_code, distance_km) in enumerate(stops, start=1):
        station_id = scalar(cursor, "SELECT station_id FROM stations WHERE station_code = %s", (station_code,))
        if station_id is None:
            raise RuntimeError(f"Route {route_name} references missing station {station_code}.")
        cursor.execute(
            "INSERT INTO route_stops (route_id, station_id, stop_sequence, distance_from_origin_km) "
            "VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE station_id = VALUES(station_id), "
            "distance_from_origin_km = VALUES(distance_from_origin_km)",
            (route_id, station_id, sequence, distance_km),
        )
    cursor.execute(
        "SELECT route_stop_id, station_id, stop_sequence, distance_from_origin_km "
        "FROM route_stops WHERE route_id = %s ORDER BY stop_sequence",
        (route_id,),
    )
    route_stops = cursor.fetchall()
    if len(route_stops) != len(stops):
        raise RuntimeError(f"Route {route_name} has unexpected stop rows; refusing to schedule it.")
    return int(route_id), route_stops


def rename_legacy_rows(cursor):
    for old_code, new_code, name, city, state in STATION_RENAMES:
        old_id = scalar(cursor, "SELECT station_id FROM stations WHERE station_code = %s", (old_code,))
        if old_id is None:
            continue
        conflict = scalar(cursor, "SELECT station_id FROM stations WHERE station_code = %s", (new_code,))
        if conflict is not None and int(conflict) != int(old_id):
            raise RuntimeError(f"Cannot rename {old_code} to {new_code}: that code already exists.")
        cursor.execute(
            "UPDATE stations SET station_code = %s, station_name = %s, city = %s, state = %s, "
            "station_status = 'ACTIVE' WHERE station_id = %s",
            (new_code, name, city, state, old_id),
        )

    for old_code, new_code, name in CLASS_RENAMES:
        old_id = scalar(cursor, "SELECT class_id FROM travel_classes WHERE class_code = %s", (old_code,))
        if old_id is None:
            continue
        conflict = scalar(cursor, "SELECT class_id FROM travel_classes WHERE class_code = %s", (new_code,))
        if conflict is not None and int(conflict) != int(old_id):
            raise RuntimeError(f"Cannot rename class {old_code} to {new_code}: that code already exists.")
        cursor.execute(
            "UPDATE travel_classes SET class_code = %s, class_name = %s, class_status = 'ACTIVE' "
            "WHERE class_id = %s",
            (new_code, name, old_id),
        )

    for old_name, target_name in LEGACY_ROUTE_RENAMES.items():
        cursor.execute("SELECT route_id FROM routes WHERE route_name = %s ORDER BY route_id LIMIT 1", (old_name,))
        found = cursor.fetchone()
        if found:
            route_id = int(found[0])
            cursor.execute("UPDATE routes SET route_name = %s, route_status = 'ACTIVE' WHERE route_id = %s", (target_name, route_id))

    old_trains = {
        "90001": ("12611", "Southern Daylight"),
        "90002": ("12701", "Garden City Express"),
        "90003": ("12615", "Deccan Connector"),
        "90004": ("12612", "Mysuru Intercity"),
        "DEMO-101": ("12051", "Deccan Express"),
        "DEMO-102": ("12052", "Southern Express"),
    }
    for old_number, (new_number, name) in old_trains.items():
        train_id = scalar(cursor, "SELECT train_id FROM trains WHERE train_number = %s", (old_number,))
        if train_id is not None:
            collision = scalar(cursor, "SELECT train_id FROM trains WHERE train_number = %s", (new_number,))
            if collision is not None and int(collision) != int(train_id):
                raise RuntimeError(f"Cannot rename train {old_number} to {new_number}: that number exists.")
            cursor.execute(
                "UPDATE trains SET train_number = %s, train_name = %s, train_status = 'ACTIVE' WHERE train_id = %s",
                (new_number, name, train_id),
            )


def ensure_class_ids(cursor):
    cursor.execute("SELECT class_id, class_code FROM travel_classes WHERE class_status = 'ACTIVE'")
    active = {row[1]: int(row[0]) for row in cursor.fetchall()}
    expected = {"SL", "3A"}
    if not expected.issubset(active):
        raise RuntimeError("Sleeper and AC 3 Tier classes were not available after renaming.")
    return {code: active[code] for code in expected}


DEMO_ACCOUNTS = (
    ("Trackline Administrator", "admin@trackline.local", "demo.admin@trackline.local", "RailDemoAdmin#26", "ADMIN"),
    ("Trackline Passenger", "passenger@trackline.local", "demo.passenger@trackline.local", "RailDemoUser#26", "PASSENGER"),
)


def ensure_demo_accounts(cursor):
    for full_name, email, old_email, password, role in DEMO_ACCOUNTS:
        cursor.execute(
            "SELECT user_id, password_hash, role FROM users WHERE email = %s LIMIT 1",
            (email,),
        )
        existing = cursor.fetchone()
        cursor.execute(
            "SELECT user_id, password_hash, role FROM users WHERE email = %s LIMIT 1",
            (old_email,),
        )
        legacy = cursor.fetchone()
        if existing and legacy:
            raise RuntimeError(
                f"Both {email} and legacy account {old_email} exist. Resolve the duplicate accounts manually."
            )
        if not existing and legacy:
            if legacy[2] != role or not check_password_hash(legacy[1], password):
                raise RuntimeError(
                    f"Legacy account {old_email} does not match the reserved local account. "
                    "Rename it manually before running the demo seed."
                )
            cursor.execute(
                "UPDATE users SET full_name = %s, email = %s, account_status = 'ACTIVE' WHERE user_id = %s",
                (full_name, email, legacy[0]),
            )
            continue
        if existing:
            if existing[2] != role or not check_password_hash(existing[1], password):
                raise RuntimeError(
                    f"Reserved local account {email} already exists with different credentials. "
                    "Change that account manually before running the demo seed."
                )
            cursor.execute(
                "UPDATE users SET full_name = %s, account_status = 'ACTIVE' WHERE user_id = %s",
                (full_name, existing[0]),
            )
            continue
        cursor.execute(
            "INSERT INTO users (full_name, email, password_hash, role, account_status) "
            "VALUES (%s, %s, %s, %s, 'ACTIVE')",
            (full_name, email, generate_password_hash(password), role),
        )


def ensure_fleet(cursor):
    train_routes = {}
    for route_name, trains in FLEET.items():
        for slot, (number, name, _old_number) in enumerate(trains):
            existing = scalar(cursor, "SELECT train_id FROM trains WHERE train_number = %s", (number,))
            if existing is None:
                cursor.execute(
                    "INSERT INTO trains (train_number, train_name, train_status) VALUES (%s, %s, 'ACTIVE')",
                    (number, name),
                )
                train_id = cursor.lastrowid
            else:
                train_id = int(existing)
                actual_name = scalar(cursor, "SELECT train_name FROM trains WHERE train_id = %s", (train_id,))
                if actual_name != name and not actual_name.startswith("Demo "):
                    raise RuntimeError(f"Train number {number} already belongs to {actual_name!r}.")
                cursor.execute(
                    "UPDATE trains SET train_name = %s, train_status = 'ACTIVE' WHERE train_id = %s",
                    (name, train_id),
                )
            train_routes[int(train_id)] = (route_name, slot, number)
    return train_routes


def ensure_seats(cursor, train_routes, class_ids):
    berth_types = ("LOWER", "MIDDLE", "UPPER", "SIDE_LOWER")
    for train_id in train_routes:
        for class_code, class_id in class_ids.items():
            coach = "S1" if class_code == "SL" else "B1"
            for seat in range(1, 9):
                cursor.execute(
                    "INSERT INTO seats (train_id, class_id, coach_number, seat_number, berth_type, seat_status) "
                    "VALUES (%s, %s, %s, %s, %s, 'ACTIVE') ON DUPLICATE KEY UPDATE "
                    "class_id = VALUES(class_id), berth_type = VALUES(berth_type), seat_status = 'ACTIVE'",
                    (train_id, class_id, coach, f"{seat:02d}", berth_types[(seat - 1) % len(berth_types)]),
                )


def calculate_stop_times(departure, route_stops):
    times = []
    previous_departure = departure
    previous_distance = float(route_stops[0][3])
    for index, stop in enumerate(route_stops):
        _stop_id, _station_id, sequence, distance = stop
        distance = float(distance)
        if index == 0:
            times.append((None, departure))
            continue
        segment_minutes = max(25, round((distance - previous_distance) / 90 * 60))
        arrival = previous_departure + timedelta(minutes=segment_minutes)
        if index == len(route_stops) - 1:
            times.append((arrival, None))
        else:
            leave = arrival + timedelta(minutes=10)
            times.append((arrival, leave))
            previous_departure = leave
        previous_distance = distance
    return times


def ensure_fares(cursor, route_stops, class_ids):
    for _route_name, (route_id, stops) in route_stops.items():
        for origin_index, origin in enumerate(stops):
            for destination in stops[origin_index + 1:]:
                distance = float(destination[3]) - float(origin[3])
                for class_code, class_id in class_ids.items():
                    rate = 1.35 if class_code == "SL" else 2.15
                    fare = round(distance * rate, 2)
                    cursor.execute(
                        "INSERT INTO route_fares (route_id, from_route_stop_id, to_route_stop_id, "
                        "class_id, fare_amount, currency_code) VALUES (%s, %s, %s, %s, %s, 'INR') "
                        "ON DUPLICATE KEY UPDATE fare_amount = VALUES(fare_amount), currency_code = 'INR'",
                        (route_id, origin[0], destination[0], class_id, fare),
                    )


def month_dates(today):
    first = today.replace(day=1)
    if first.month == 12:
        next_month = first.replace(year=first.year + 1, month=1)
    else:
        next_month = first.replace(month=first.month + 1)
    day = first
    while day < next_month:
        yield day
        day += timedelta(days=1)


def adjusted_departure_slots(db_now):
    usual = [time(5, 0), time(8, 0), time(11, 0), time(14, 0), time(17, 0)]
    if db_now.time() < usual[0]:
        return usual
    base = (db_now + timedelta(minutes=30)).replace(second=0, microsecond=0)
    remainder = base.minute % 15
    if remainder:
        base += timedelta(minutes=15 - remainder)
    slots = [base + timedelta(minutes=60 * slot) for slot in range(5)]
    if any(slot.date() != db_now.date() for slot in slots):
        return usual
    return [slot.time() for slot in slots]


def ensure_month_schedules(cursor, train_routes, route_stops, class_ids, db_now):
    today = db_now.date()
    month_days = list(month_dates(today))
    current_slots = adjusted_departure_slots(db_now)
    count = 0

    # Mark only this demo fleet's older services complete; leave other schedules alone.
    train_ids = tuple(train_routes)
    placeholders = ",".join(["%s"] * len(train_ids))
    cursor.execute(
        f"UPDATE train_schedules SET schedule_status = 'COMPLETED' "
        f"WHERE train_id IN ({placeholders}) AND departure_at < %s "
        "AND schedule_status = 'SCHEDULED'",
        (*train_ids, month_days[0]),
    )

    for service_day in month_days:
        past_day = service_day < today
        for train_id, (route_name, slot, train_number) in train_routes.items():
            route_id, stops = route_stops[route_name]
            cursor.execute(
                "SELECT schedule_id, departure_at FROM train_schedules "
                "WHERE train_id = %s AND DATE(departure_at) = %s ORDER BY departure_at LIMIT 1",
                (train_id, service_day),
            )
            existing = cursor.fetchone()
            if existing:
                schedule_id = int(existing[0])
                departure = existing[1]
            else:
                past_slots = (time(5, 0), time(8, 0), time(11, 0), time(14, 0), time(17, 0))
                slot_time = past_slots[slot] if past_day else current_slots[slot]
                departure = datetime.combine(service_day, slot_time)
                times = calculate_stop_times(departure, stops)
                arrival = times[-1][0]
                status = "COMPLETED" if past_day or departure <= db_now else "SCHEDULED"
                cursor.execute(
                    "INSERT INTO train_schedules (train_id, route_id, departure_at, arrival_at, schedule_status) "
                    "VALUES (%s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE route_id = VALUES(route_id), "
                    "arrival_at = VALUES(arrival_at), schedule_status = VALUES(schedule_status)",
                    (train_id, route_id, departure, arrival, status),
                )
                cursor.execute(
                    "SELECT schedule_id FROM train_schedules WHERE train_id = %s AND departure_at = %s",
                    (train_id, departure),
                )
                schedule_id = int(cursor.fetchone()[0])

            status = "COMPLETED" if past_day or departure <= db_now else "SCHEDULED"
            times = calculate_stop_times(departure, stops)
            cursor.execute(
                "UPDATE train_schedules SET route_id = %s, arrival_at = %s, schedule_status = %s "
                "WHERE schedule_id = %s",
                (route_id, times[-1][0], status, schedule_id),
            )

            for stop, (arrival_at, departure_at) in zip(stops, times):
                cursor.execute(
                    "INSERT INTO schedule_stops (schedule_id, route_id, route_stop_id, station_id, "
                    "stop_sequence, arrival_at, departure_at) VALUES (%s, %s, %s, %s, %s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE route_id = VALUES(route_id), station_id = VALUES(station_id), "
                    "stop_sequence = VALUES(stop_sequence), arrival_at = VALUES(arrival_at), "
                    "departure_at = VALUES(departure_at)",
                    (schedule_id, route_id, stop[0], stop[1], stop[2], arrival_at, departure_at),
                )

            for class_code, class_id in class_ids.items():
                cursor.execute(
                    "SELECT seat_id FROM seats WHERE train_id = %s AND class_id = %s AND seat_status = 'ACTIVE'",
                    (train_id, class_id),
                )
                for (seat_id,) in cursor.fetchall():
                    cursor.execute(
                        "INSERT INTO schedule_seats (schedule_id, train_id, seat_id, class_id, operational_status) "
                        "VALUES (%s, %s, %s, %s, 'IN_SERVICE') ON DUPLICATE KEY UPDATE "
                        "class_id = VALUES(class_id), operational_status = 'IN_SERVICE'",
                        (schedule_id, train_id, seat_id, class_id),
                    )
            count += 1
    return count


def seed(connection):
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT CURRENT_TIMESTAMP")
        db_now = cursor.fetchone()[0]

        # No booking, passenger, payment, or refund rows are changed.
        rename_legacy_rows(cursor)

        for code, name, city, state in ADDITIONAL_STATIONS:
            ensure_station(cursor, code, name, city, state)

        station_codes = tuple(row[0] for row in ADDITIONAL_STATIONS)
        station_placeholders = ",".join(["%s"] * len(station_codes))
        cursor.execute(
            f"UPDATE stations SET station_status = 'INACTIVE' "
            f"WHERE station_code NOT IN ({station_placeholders})",
            station_codes,
        )
        cursor.execute(
            "UPDATE stations SET station_name = TRIM(REPLACE(station_name, 'Demo ', '')) "
            "WHERE station_name LIKE 'Demo %'"
        )
        cursor.execute(
            "UPDATE routes SET route_status = 'INACTIVE', route_name = "
            "TRIM(REPLACE(REPLACE(route_name, 'Demo: ', ''), 'DEMO: ', ''))"
        )
        cursor.execute(
            "UPDATE trains SET train_status = 'INACTIVE', "
            "train_name = TRIM(REPLACE(train_name, 'Demo ', ''))"
        )

        class_ids = ensure_class_ids(cursor)
        routes = {}
        for route_name, (_description, stops) in ROUTE_DEFINITIONS.items():
            new_name, _ = ROUTE_DEFINITIONS[route_name]
            route_id, route_stop_rows = ensure_route(cursor, new_name, stops)
            routes[route_name] = (route_id, route_stop_rows)

        train_routes = ensure_fleet(cursor)
        ensure_seats(cursor, train_routes, class_ids)
        ensure_fares(cursor, routes, class_ids)
        schedules = ensure_month_schedules(cursor, train_routes, routes, class_ids, db_now)
        ensure_demo_accounts(cursor)
        connection.commit()
        return {
            "stations_added": len(ADDITIONAL_STATIONS),
            "routes": len(routes),
            "trains": len(train_routes),
            "schedules": schedules,
            "month": db_now.strftime("%B %Y"),
            "demo_accounts": len(DEMO_ACCOUNTS),
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-user", default="root", help="database administrator account (default: root)")
    parser.add_argument("--unix-socket", help="optional MariaDB/MySQL Unix socket path")
    args = parser.parse_args()
    password = "" if args.unix_socket else getpass(f"Password for database user {args.db_user}: ")
    connect_args = {
        "database": DatabaseConfig.DB_NAME,
        "user": args.db_user,
        "password": password,
        "connection_timeout": 10,
    }
    if args.unix_socket:
        connect_args["unix_socket"] = args.unix_socket
    else:
        connect_args["host"] = DatabaseConfig.DB_HOST
        connect_args["port"] = DatabaseConfig.DB_PORT

    connection = mysql.connector.connect(**connect_args)
    try:
        result = seed(connection)
    finally:
        connection.close()
    print(
        "Seeded {trains} trains over {schedules} daily services across {routes} routes "
        "for {month}; added {stations_added} stations and verified {demo_accounts} demo accounts. "
        "Existing demo labels were renamed.".format(**result)
    )


if __name__ == "__main__":
    main()
