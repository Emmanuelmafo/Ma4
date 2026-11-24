# SmartShop — Python + Flask demo

## Stack
- Python and Flask for the application and business logic.
- SQLAlchemy for database access.
- SQLite locally; PostgreSQL (Neon) when DATABASE_URL is configured.
- HTML/CSS templates. Browser camera barcode scanning will require JavaScript.

## Run locally (Windows)
1. Install Python 3.11+.
2. Open a terminal in this folder.
3. python -m venv venv
4. venv\\Scripts\\activate
5. pip install -r requirements.txt
6. Copy .env.example to .env and set a strong SECRET_KEY.
7. python app.py
8. Visit http://127.0.0.1:8080

## Included
- Owner, Manager and Employee dashboard views.
- Manager receives boxed stock into storage.
- Manager transfers units from storage to display without changing total inventory.
- Employee records sales; display and total stock decrease.
- Barcode lookup API endpoint (camera scanner interface not yet included).
- SQLite or PostgreSQL database support.

## Deployment
Set DATABASE_URL to the Neon PostgreSQL connection string and SECRET_KEY in Railway variables. Never commit .env or database credentials.

## Important limitations
This is an early demo, not a commercial-ready release. Authentication, role permissions, shop/branch isolation, robust transaction locking, item-barcode management, camera scanning UI, OCR, expenses, staff management, reports, receipts, refunds, backups, audit logging and security testing remain to be implemented. Do not use real customer or financial records until these are completed and reviewed.
