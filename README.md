# Railway Reservation System

Coursework project using Flask, MySQL, and a vanilla HTML/CSS/JavaScript frontend. Project requirements and test references are in [Documents](Documents/).

## Setup
1. Install Python 3.10+ and MySQL 8.x.
2. Create and activate a virtual environment: `python -m venv .venv`, then `source .venv/bin/activate` (Windows PowerShell: `.venv\\Scripts\\Activate.ps1`).
3. Install dependencies: `pip install -r requirements.txt`.
4. Copy `.env.example` to `.env`, set database credentials, and replace `SECRET_KEY` with a high-entropy random value. Never commit `.env`.
5. Run `database/schema.sql` in MySQL.
6. Start from the repository root with `python backend/run.py`, then open http://127.0.0.1:5000.

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

## Tests
Run `python -m unittest discover -s backend/tests -v` from the repository root. Admin tests mock database access and cover login, invalid credentials, disabled users, passenger denial, anonymous denial, and logout.
