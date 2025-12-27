# a11yhood Environment Modes Guide

This guide explains how to switch between **test mode** (SQLite) and **production mode** (Supabase) and how the application maintains isolation between these modes.

## Overview

a11yhood supports running in **TWO ISOLATED MODES**:

### 1. Test Mode (Local Development & Testing)
- **Database**: SQLite (local, no credentials needed)
- **OAuth**: Disabled (uses mock/test users)
- **Data**: Ephemeral (can be reset without affecting production)
- **Files**: `.env.test`, test-seed scripts
- **Purpose**: Development, automated testing, CI/CD
- **Start**: `./start-dev.sh`

### 2. Production Mode (Local or Cloud Deployment)
- **Database**: Supabase PostgreSQL (remote, requires credentials)
- **OAuth**: Real GitHub, Ravelry, Thingiverse
- **Data**: Persistent (real user data)
- **Files**: `.env`, `.env.local`
- **Purpose**: Production deployment, manual testing with real data
- **Start**: `./start-prod.sh`

## How the Isolation Works

The application uses the **`ENV_FILE` environment variable** to select which mode to use:

```bash
ENV_FILE=.env.test  →  Test mode (SQLite)
ENV_FILE=.env       →  Production mode (Supabase)
```

This controls which configuration file Pydantic loads in [config.py](../config.py):

### start-dev.sh (Test Mode)
```bash
export ENV_FILE=.env.test
# Loads: .env.test (SQLite, test settings)
```

### start-prod.sh (Production Mode)
```bash
export ENV_FILE=.env
# Loads: .env (Supabase, production settings)
```

### run-tests.sh (Test Isolation)
```bash
export ENV_FILE=.env.test
# Ensures tests NEVER use production database
```

## Running in Test Mode (Development)

Test mode is for local development and automated testing.

### Setup
```bash
# No secrets needed - test SQLite database is local
# backend/.env.test should already exist
ls .env.test

# If it doesn't exist:
cp .env.test.example .env.test
```

### Start Test Mode
```bash
cd /path/to/repo
./start-dev.sh
```

This automatically:
- Exports `ENV_FILE=.env.test` in the backend
- Loads `backend/.env.test` configuration
- Starts SQLite on `/tmp/a11yhood-test.db`
- Disables real OAuth (uses test users: admin, moderator, user)
- Seeds test data (products, sources, users)
- Starts frontend in dev mode with mock OAuth

### Verify Test Mode
```bash
# Check environment variable
echo $ENV_FILE
# Should output: .env.test

# Check backend health
curl http://localhost:8000/health
```

### Running Tests
```bash
./run-tests.sh           
```

Tests automatically set `ENV_FILE=.env.test` and use isolated SQLite.

### Stop Test Mode
```bash
./stop-dev.sh
```

## Running in Production Mode (Real Supabase)

Production mode uses your real Supabase database for:
- Local testing with real data before cloud deployment
- Manual QA against real backend
- Staging/preview environments

### Prerequisites

1. **Create production Supabase project** at https://supabase.com
2. **Apply schema**: supabase-schema.sql to Supabase (Settings → SQL Editor)
3. **Create GitHub OAuth app**: https://github.com/settings/developers
4. **Have domain ready**: for OAuth callback URLs

### Setup Step 1: Create backend/.env

```bash
cp .env.test.example .env
```

Edit `.env` with production credentials:

```dotenv
# Production Supabase Database
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=sb_secret_your_service_role_key
SUPABASE_ANON_KEY=sb_publishable_your_anon_key

# GitHub OAuth
GITHUB_CLIENT_ID=your_oauth_id
GITHUB_CLIENT_SECRET=your_oauth_secret

# Security: Generate random key with:
# python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=your_random_production_secret_key_64_chars

# Production mode (NOT test mode)
TEST_MODE=false
```

See [backend/.env.example](../backend/.env.example) for detailed documentation.

### Start Production Mode

```bash
cd /path/to/repo
./start-prod.sh
```

This automatically:
- Exports `ENV_FILE=.env` 
- Loads `.env` configuration
- Connects to your production Supabase database
- Enables real GitHub OAuth
- Does NOT seed test data (preserves real production data)

### Verify Production Mode

```bash
# Check backend health
curl http://localhost:8000/health

# Check database connection
curl http://localhost:8000/api/sources/supported
```

### Stop Production Mode

```bash
./stop-prod.sh
```

## Critical: How to Avoid Accidents

### Problem 1: Running tests against production database

**Solution**:
- `run-tests.sh` always sets `ENV_FILE=.env.test`
- Tests never read `.env` (production config)
- If backend/.env.test is missing, tests fail explicitly
- Verify with: `grep ENV_FILE backend/run-tests.sh`

### Problem 2: Starting dev with wrong environment file

**Solution**:
- `start-dev.sh` explicitly exports `ENV_FILE=.env.test`
- If ENV_FILE is not set, Pydantic defaults to `.env`
- To debug: `echo $ENV_FILE` (should show `.env.test`)
- If wrong: Kill backend and restart with `./start-dev.sh`

### Problem 3: Accidental data modification in production

**Solution**:
- Use separate Supabase projects:
  - **Production project**: Real user data, use only for deployed app
  - **Staging project**: Same schema, safe for testing
- In `.env` for testing: `SUPABASE_URL=staging-project`
- In production deployment: `SUPABASE_URL=production-project`

### Problem 4: Using test data in production (or vice versa)

**Solution**:
- Test mode (SQLite): Uses deterministic UUIDs in seed scripts
- Production (Supabase): Real GUIDs, no seeding
- Data schema is identical between modes
- Tests verify compatibility via API (not direct DB)

## Checking Which Mode You're In

If you're unsure which mode is running:

### 1. Check environment variable

```bash
echo $ENV_FILE
# Should output: .env.test (dev) or .env (prod)
```

### 2. Check database health

```bash
curl http://localhost:8000/health
# Request should succeed
```

### 4. Check logs

- `start-dev.sh` output: Shows "Seeding test users" (test mode)
- `start-prod.sh` output: Shows "Using PRODUCTION Supabase" (prod mode)

### 5. Check database location

```bash
# Test mode: SQLite file exists
ls /tmp/a11yhood-test.db

# Production: No local DB file (connects to Supabase)
```

## Switching Between Modes

### Test → Production

```bash
# 1. Stop test mode
./stop-dev.sh

# 2. Set up production credentials
# Create backend/.env and frontend/.env.local

# 3. Start production
./start-prod.sh

# 4. Verify
echo $ENV_FILE  # Should show: .env
```

### Production → Test

```bash
# 1. Stop production
./stop-prod.sh

# 2. Restart in test mode
./start-dev.sh

# 3. Verify
echo $ENV_FILE  # Should show: .env.test
```

## Environment Variables Reference

### Backend Configuration (Controls database and OAuth)

| Variable | Test Mode | Production Mode | Purpose |
|----------|-----------|-----------------|---------|
| `ENV_FILE` | `.env.test` | `.env` | Which config file to load |
| `TEST_MODE` | `true` | `false` | Use SQLite or Supabase |
| `DATABASE_URL` | `sqlite://...` | (unset) | SQLite connection (test only) |
| `SUPABASE_URL` | dummy value | real URL | Production database URL |
| `SUPABASE_KEY` | dummy value | real key | Service role key (backend) |
| `GITHUB_CLIENT_ID` | test ID | production ID | OAuth app ID |

### Frontend Configuration (Controls API endpoint)

| Variable | Test Mode | Production Mode | Purpose |
|----------|-----------|-----------------|---------|
| `VITE_ENV` | `development` | `production` | Debug features, OAuth style |
| `VITE_API_URL` | (unset) | set if needed | Backend API endpoint |
| `VITE_SUPABASE_URL` | test URL | production URL | Supabase anon access |
| `VITE_SUPABASE_ANON_KEY` | test key | production key | Frontend database access |

## Troubleshooting

### "ERROR: .env.test not found in backend/"

**Solution**:
```bash
cp .env.test.example .env.test
```

### "ERROR: SUPABASE_URL not configured in backend/.env"

**Solution**: Create `.env` with production Supabase credentials. See [DEPLOYMENT_PLAN.md](DEPLOYMENT_PLAN.md).

### Tests are using production database

**Solution**:
- Check that `run-tests.sh` is setting `ENV_FILE=.env.test`
- Verify: `grep ENV_FILE run-tests.sh`
- Verify: `.env.test` exists and has correct SQLite configuration

### Can't login - GitHub OAuth not working

**Checklist**:
- You're in production mode (`ENV_FILE=.env`)
- `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` are in `.env`
- GitHub OAuth app callback URL matches `FRONTEND_URL`
- Frontend is running at `FRONTEND_URL` (not different port)

### Getting 'readonly database' errors

**Solution**:
- SQLite permission issue, probably in test mode
- Database file: `/tmp/a11yhood-test.db`
- Restart:
  ```bash
  ./stop-dev.sh
  rm /tmp/a11yhood-test.db
  ./start-dev.sh
  ```

## Related Documentation

- [AGENT_GUIDE.md](AGENT_GUIDE.md) - Development conventions and commands
- [DEPLOYMENT_PLAN.md](DEPLOYMENT_PLAN.md) - Detailed production setup and OAuth configuration
- [QUICK_START.md](QUICK_START.md) - Quick reference for getting started
- [LOCAL_TESTING.md](LOCAL_TESTING.md) - Local environment setup and testing procedures
- [backend/.env.example](../.env.example) - Backend configuration template with full documentation