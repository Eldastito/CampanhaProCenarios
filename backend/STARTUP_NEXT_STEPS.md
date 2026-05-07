# Backend startup and wiring next steps

## Current state
The repository already contains:
- FastAPI entrypoint with startup bootstrap
- database session and bootstrap helpers
- initial ORM models
- repository layer
- scenario and prediction application services
- memory provider abstraction
- local graph adapter
- internal API key dependency
- local filesystem storage provider
- backend Dockerfile

## Current behavior
1. API initializes logging and creates tables at startup
2. scenario endpoints persist scenario and scenario run records
3. prediction endpoints persist prediction records
4. forge ingest endpoints require integration secret
5. scenario and prediction endpoints require internal API key

## Next wiring pass
1. persist FORGE ingest logs
2. add report export storage flow
3. add worker runtime backed by Redis
4. add user auth and organization-aware RBAC
5. replace placeholder prediction values with actual scoring services
6. replace placeholder scenario result with execution engine

## Local commands
### Create tables
```bash
cd backend
python manage.py
```

### Run API manually
```bash
uvicorn app.main:app --reload --port 8000
```

### Run local stack
```bash
docker compose up -d --build
```
