# Tri9T - Clean Architecture FastAPI Backend

This is a production-quality, asynchronous backend service built using **FastAPI**, **SQLAlchemy 2.0 (SQLite)**, and **Pydantic v2**, with support for a dual SQL/NoSQL storage paradigm (using SQLite and a configurable MongoDB / JSON file document store).

## Features & Architecture

The project adheres to **Clean Architecture** principles to separate concerns and isolate business logic from database and framework dependencies:

- **Entities / Domain Models**: Define the core business models without framework-specific dependencies.
- **Use Cases / Services**: Orchestrate business rules, consuming repository abstractions.
- **Repository Pattern**: Hides the storage layer. Supports asynchronous PostgreSQL/SQLite via SQLAlchemy 2.0 or Document stores via MongoDB (or local JSON store).
- **API (Controllers)**: Lightweight routers exposing HTTP endpoints, performing input validation via Pydantic.
- **Structured Logging**: Structured JSON logging out of the box using `structlog` for production, and human-friendly colorized logs for development.
- **Migrations**: Database schema evolution managed via `alembic` (async configured).

---

## Directory Structure

```
Tri9T/
├── alembic.ini          # Alembic configuration
├── alembic/             # Database migrations
├── app/
│   ├── main.py          # FastAPI application entrypoint
│   ├── api/             # API Router, endpoints, and dependencies
│   ├── core/            # Configuration, logging, and database engines
│   ├── models/          # DB structures (SQL, NoSQL) & Domain entities
│   ├── repositories/    # Database operations (SQL, NoSQL, Base classes)
│   ├── services/        # Business use cases
│   └── schemas/         # Pydantic schemas (Request/Response validation)
└── tests/               # pytest test suite
```

---

## Installation & Setup

1. **Virtual Environment**:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Environment Configuration**:
   Create a `.env` file in the root directory (refer to settings in `app/core/config.py`):
   ```env
   ENVIRONMENT=dev
   DATABASE_URL=sqlite+aiosqlite:///./sql_app.db
   DOCUMENT_STORE_TYPE=json
   DOCUMENT_STORE_PATH=./data/document_db.json
   ```

4. **Run Application**:
   ```bash
   uvicorn app.main:app --reload
   ```
   Access the interactive docs at: http://127.0.0.1:8000/docs

---

## Database Migrations (Alembic)

Initialize/generate database migrations:
```bash
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

---

## Running Tests

Run the test suite using `pytest`:
```bash
pytest
```
