# Railway Reservation System

Initial project scaffold for the Railway Reservation System coursework. The repository's SRS, use-case flow, and test plan are available in [Documents](Documents/).

## Stack

- **Frontend:** HTML, CSS, and vanilla JavaScript
- **Backend:** Python and Flask
- **Database:** MySQL

## Project structure

```text
.
├── Documents/              # Project requirements and test references
├── backend/
│   ├── app/
│   │   ├── __init__.py     # Flask application factory and frontend serving
│   │   ├── config.py       # Environment-based configuration
│   │   ├── db.py           # MySQL connection helper
│   │   └── routes.py       # Initial health endpoints
│   └── run.py              # Development entry point
├── frontend/
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── .env.example
├── .gitignore
└── requirements.txt
```

## Requirements

- Python 3.10 or newer
- MySQL Server 8.x (for database connectivity checks)

## Setup

1. Clone the repository and open its root directory.
2. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   # macOS/Linux
   source .venv/bin/activate
   # Windows PowerShell: .venv\\Scripts\\Activate.ps1
   ```

3. Install backend dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Copy `.env.example` to `.env` and update the MySQL username and password. Do not commit `.env` or real credentials.
5. Create the local database in MySQL (the schema is a separate task):

   ```sql
   CREATE DATABASE railway_reservation;
   ```

6. Start the backend and frontend server from the repository root:

   ```bash
   python backend/run.py
   ```

7. Open [http://127.0.0.1:5000](http://127.0.0.1:5000). Flask serves the frontend and API from the same origin, so a separate frontend server is not needed.

## Health endpoints

- `GET /api/health` — confirms the API is running.
- `GET /api/health/db` — checks MySQL connectivity. Returns HTTP 503 if MySQL is not configured or reachable; it does not expose connection details.

## Current scope

This commit establishes the project structure, environment configuration, dependency list, MySQL connection helper, and a minimal frontend/API health check. Reservation features, authentication, database tables, payment handling, and business logic have not been implemented yet and should be developed in their assigned issues.
