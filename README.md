# Railway Reservation System

Coursework project using Flask, MySQL, and a vanilla HTML/CSS/JavaScript frontend. Project requirements and test references are in [Documents](Documents/).

## Setup
1. Install Python 3.10+, MySQL 8.x, and [uv](https://docs.astral.sh/uv/).
2. Create and activate a virtual environment: `uv venv`, then `source .venv/bin/activate` (Windows PowerShell: `.venv\\Scripts\\Activate.ps1`).
3. Install dependencies: `uv pip install -r requirements.txt`.
4. Copy `.env.example` to `.env` and set your database credentials. Replace `SECRET_KEY` with a high-entropy random value before deployment. Never commit `.env`.
5. Create the schema by running `mysql -u root -p < database/schema.sql`.
6. Start from the repository root with `uv run --active python backend/run.py`, then open http://127.0.0.1:5000.

## Administrator login (Issue #5)
Admin accounts are existing `users` rows with `role='ADMIN'` and `account_status='ACTIVE'`. Public registration cannot set a role. Create the initial admin through a trusted, access-controlled database administration process; do not expose public admin creation.

- `POST /api/admin/login`: JSON `{"email":"admin@example.com","password":"your-password"}`; verifies the stored Werkzeug password hash, role, and active status, then establishes a session.
- `POST /api/admin/logout`: clears the authenticated admin session.
- `GET /api/admin/dashboard`: protected example endpoint (401 anonymous, 403 authenticated non-admin).
- Decorate every future admin-only route with `@admin_required` from `backend.app.admin_auth`.

Sessions use HttpOnly, SameSite=Lax cookies and a 30-minute lifetime. Set a stable random `SECRET_KEY` in deployment and `SESSION_COOKIE_SECURE=true` behind HTTPS. The development fallback secret is generated at startup and is not suitable for deployment.

Example:
```bash
curl -i -c cookies.txt -H 'Content-Type: application/json' -d '{"email":"admin@example.com","password":"your-password"}' http://127.0.0.1:5000/api/admin/login
curl -i -b cookies.txt http://127.0.0.1:5000/api/admin/dashboard
```

## Passenger login and logout (Issue #4)
- `POST /api/login`: JSON `{"email":"passenger@example.com","password":"your-password"}`; verifies an active passenger account and establishes a session.
- `GET /api/session`: restores the current passenger session.
- `POST /api/logout`: clears the passenger session.

## Tests
Run `uv run --active python -m unittest discover -s backend/tests -v` from the repository root. Authentication tests mock database access and cover login, invalid credentials, disabled users, passenger denial, anonymous denial, and logout.

## Current scope
The implemented features are project setup, the database schema, passenger registration and login/logout, administrator login, and scheduled train search with displayed starting fares and seat availability. Administrator login is currently an API flow; create an admin account only through a trusted local database administration process.
