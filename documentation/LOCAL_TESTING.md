# Local Testing Guide

This guide helps you run a fully functional local version of a11yhood for testing and development. Run commands from the repo root unless noted otherwise.

## Prerequisites

- **Node.js 18+**: Frontend development
- **Python 3.9+**: Backend development  
- **uv**: Python package manager (`pip install uv`)
- **npm**: Node package manager

## Quick Start

### One-Command Setup

```bash
# Start backend
./start-dev.sh

# Stop backend
./stop-dev.sh
```

### Manual Start (if you prefer separate terminals)

**Terminal 1 - Backend:**
```bash
export $(cat .env.test | grep -v '^#' | xargs)
uv run python -m uvicorn main:app --reload --port 8000
```

## Accessing the Application

| Component | URL | Purpose |
|-----------|-----|---------|
| Backend API | http://localhost:8000 | API endpoints |
| API Docs | http://localhost:8000/docs | Interactive API documentation |
| API Schema | http://localhost:8000/openapi.json | OpenAPI schema |

## Test Users (Local SQLite)

The `.env.test` configuration uses a local SQLite database with pre-seeded test users:

| Username | User ID | Role | Use Case |
|----------|---------|------|----------|
| `admin_user` | admin-test-001 | Admin | Full system access, scraper controls |
| `moderator_user` | mod-test-002 | Moderator | Content moderation, user management |
| `regular_user` | user-test-003 | User | Regular user features, submit products |

## Local Database

The application uses **SQLite** in test mode for fast iteration without Supabase setup.

### Database File
```
backend/test.db
```

### Reset Database

```bash
# Delete the test database to start fresh
rm test.db

# On next backend start, the schema will be recreated
```

### Seed Test Data

```bash
export $(cat .env.test | grep -v '^#' | xargs)
uv run python seed_test_users.py
uv run python seed_test_product.py
uv run python seed_test_collections.py
uv run python seed_scraper_search_terms.py
uv run python seed_supported_sources.py
```

### View Database

```bash
# Using sqlite3
sqlite3 test.db

# Inside sqlite3:
.tables           # List all tables
.schema products  # Show products table structure
SELECT * FROM users LIMIT 5;
```

## Testing Features

### Backend Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run unit tests only (excludes integration tests)
uv run pytest tests/ -v -m "not integration"

# Run specific test file
uv run pytest tests/test_products.py -v

# Run with coverage
uv run pytest tests/ --cov=. --cov-report=html
```


## Working with Scrapers

### Scraper Configuration

Scrapers work with test mode to avoid hitting external APIs during development:

1. **GitHub Scraper** - Uses GitHub API (configured in `.env.test`)
2. **Ravelry Scraper** - Requires OAuth token (test mode available)
3. **Thingiverse Scraper** - Requires API key (test mode available)

### Running Scrapers in Admin Dashboard

1. Log in as `admin_user`
2. Navigate to Admin Dashboard
3. Click "Scraper Manager"
4. Select a scraper and click "Run" or "Test Run" (limited products)

### Testing Scrapers in Code

```bash
cd backend
export $(cat .env.test | grep -v '^#' | xargs)

# Test individual scrapers
uv run python -c "
import asyncio
from services.scrapers import ScraperService
service = ScraperService(None)  # Uses local db in test mode

# Test GitHub scraper
result = asyncio.run(service.scrape_github(test_mode=True, test_limit=3))
print(f'GitHub: Found {result[\"products_found\"]} products')
"
```

## Common Development Tasks

### Add a New Product Type

1. Create model in `backend/models/products.py`
2. Add routes in `backend/routers/products.py`
3. Update database schema in `backend/database_adapter.py`
5. Add tests for new functionality

### Debug API Responses

```bash
# Test endpoint directly
curl -s http://localhost:8000/api/products \
  -H "Authorization: Bearer <token>" | python -m json.tool
```

### View Logs

```bash
# Backend logs
tail -f backend.log

# Or inside each terminal running the dev server
# Check terminal output directly
```

### Update Dependencies

```bash
# Backend
uv sync

# Frontend
npm install
```

## Troubleshooting

### Backend won't start: "Address already in use"

```bash
# Kill any existing processes
pkill -9 -f "uvicorn"
pkill -9 -f "python.*main:app"

# Then restart
./start-dev.sh
```

### Tests failing locally but passing in CI

1. Make sure you've run `uv sync` and `npm install`
2. Check `.env.test` exists with correct settings
3. Try resetting the database: `rm backend/test.db`
4. Run with verbose output: `pytest -vv` or `npm test -- -reporter=verbose`

### "Module not found" errors

```bash
# Python
cd uv sync && cd ..


### Port 8000 already in use

Specify different ports:

```bash
# Backend on port 8001
uv run python -m uvicorn main:app --port 8001
```

## Performance Tips

### Faster Development

- Use `npm run dev` instead of `npm run build` (dev mode is faster)
- Use `uv run` instead of pip (faster package resolution)
- Run backend with `--reload` enabled (hot reloading)

### Database Optimization

- Indexes created automatically for common queries
- Use test mode to avoid external API calls
- Cache frequently accessed data locally

## Performance Monitoring

### Check API Response Times

```bash
# Backend performance
time curl -s http://localhost:8000/api/products | wc -c
```

## Next Steps

- [API Reference](API_REFERENCE.md) - Learn all available endpoints
- [Architecture](ARCHITECTURE.md) - Understand system design
- [Code Standards](CODE_STANDARDS.md) - Follow coding conventions
- [Database](DATABASE.md) - Database schema and design

## Environment Variables

### Backend (.env.test)

```env
# Database
TEST_MODE=true
DATABASE_URL=sqlite:///./test.db

# Supabase (optional, only for production)
SUPABASE_URL=
SUPABASE_KEY=

# GitHub OAuth (test mode)
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=

# API Settings
API_PORT=8000
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

## Need Help?

- Check existing docs via the [documentation index](README.md)
- Review test examples in `backend/tests/` and `frontend/src/__tests__/`
- Run with verbose logging: `DEBUG=* npm run dev`
