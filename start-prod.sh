#!/bin/bash
# Start backend production server for a11yhood
# This script starts the backend API server on port 8000 in production mode
# Uses production Supabase database with real OAuth
# 
# Usage:
#   ./start-prod.sh        # Normal start
#   ./start-prod.sh --help # Show help

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Timing helper
SECONDS=0
ts() {
  # Prints elapsed seconds since script start
  echo "${SECONDS}s"
}

# Parse arguments
HELP=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --help)
      HELP=true
      shift
      ;;
    *)
      echo "Unknown option: $1"
      HELP=true
      shift
      ;;
  esac
done

if [ "$HELP" = true ]; then
  echo "Usage: ./start-prod.sh [OPTIONS]"
  echo ""
  echo "Starts backend production server (production Supabase database)"
  echo ""
  echo "Prerequisites:"
  echo "  - .env configured with production Supabase credentials"
  echo "  - Production Supabase project set up with schema applied"
  echo ""
  echo "Options:"
  echo "  --help       Show this help message"
  echo ""
  echo "See documentation/DEPLOYMENT_PLAN.md for detailed setup instructions"
  exit 0
fi

# Don't exit on error, handle errors gracefully
set +e

echo -e "${BLUE}🚀 Starting a11yhood backend PRODUCTION server...${NC} (t=0s)"
echo -e "${YELLOW}⚠️  Using PRODUCTION Supabase database${NC}"
echo ""

# Kill any existing backend process
echo -e "${YELLOW}🔄 Stopping existing backend server...${NC} (t=$(ts))"
pkill -f "uvicorn main:app" 2>/dev/null || true
sleep 1

# Start backend in background
echo -e "${BLUE}🔧 Starting backend server (port 8000)...${NC} (t=$(ts))"

# Check if .env exists
if [ ! -f .env ]; then
  echo -e "${RED}✗ Error: .env not found${NC}"
  echo "   Please create .env with production Supabase credentials"
  echo "   See documentation/DEPLOYMENT_PLAN.md for setup instructions"
  exit 1
fi

# Export all .env variables and set ENV_FILE for Pydantic
export ENV_FILE=.env
export $(cat .env | grep -v '^#' | xargs)

# Verify critical production settings
if [ -z "$SUPABASE_URL" ] || [ "$SUPABASE_URL" = "https://your-production-project.supabase.co" ]; then
  echo -e "${RED}✗ Error: SUPABASE_URL not configured in backend/.env${NC}"
  echo "   Please set SUPABASE_URL to your production Supabase project URL"
  exit 1
fi

if [ -z "$SUPABASE_KEY" ] || [ "$SUPABASE_KEY" = "your-production-service-role-key" ]; then
  echo -e "${RED}✗ Error: SUPABASE_KEY not configured in backend/.env${NC}"
  echo "   Please set SUPABASE_KEY to your production service_role key"
  exit 1
fi

if [ "$TEST_MODE" = "true" ]; then
  echo -e "${YELLOW}⚠️  Warning: TEST_MODE=true in .env${NC}"
  echo "   Production should use TEST_MODE=false"
fi

echo -e "${GREEN}✓ Production Supabase configured: ${SUPABASE_URL}${NC}"

# Do not seed data in production
echo -e "${YELLOW}ℹ Skipping all seeding in production mode${NC}"

# Start backend server
UVICORN_CMD=""
if command -v uv >/dev/null 2>&1; then
  UVICORN_CMD="uv run python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000"
elif [ -x ".venv/bin/uvicorn" ]; then
  UVICORN_CMD=".venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000"
else
  echo -e "${RED}✗ Error: uvicorn not found${NC}"
  echo "   Please install dependencies: uv sync"
  exit 1
fi

echo -e "${BLUE}Starting uvicorn...${NC}"
$UVICORN_CMD > backend.log 2>&1 &
BACKEND_PID=$!
echo -e "${GREEN}✓ Backend started (PID: $BACKEND_PID)${NC} (t=$(ts))"

# Wait for backend to be ready
echo -e "${BLUE}⏳ Waiting for backend to be ready...${NC}"
RETRIES=0
MAX_RETRIES=30
until curl -s http://localhost:8000/health > /dev/null 2>&1; do
  RETRIES=$((RETRIES+1))
  if [ $RETRIES -ge $MAX_RETRIES ]; then
    echo -e "${RED}✗ Backend failed to start after ${MAX_RETRIES} seconds${NC}"
    echo "   Check backend.log for errors:"
    tail -n 20 backend.log
    exit 1
  fi
  sleep 1
done
echo -e "${GREEN}✓ Backend is ready${NC} (t=$(ts))"

# Verify Supabase connection
echo -e "${BLUE}🔍 Verifying Supabase connection...${NC}"
SOURCES_CHECK=$(curl -s http://localhost:8000/api/supported-sources 2>&1)
if [ $? -eq 0 ]; then
  echo -e "${GREEN}✓ Supabase connection verified${NC}"
else
  echo -e "${YELLOW}⚠️  Warning: Could not verify Supabase connection${NC}"
  echo "   This may be normal if no supported sources are seeded yet"
fi

echo ""
echo -e "${GREEN}✅ Backend production server started successfully!${NC} (t=$(ts))"
echo ""
echo -e "${BLUE}🌐 Services:${NC}"
echo "   Backend:   http://localhost:8000"
echo "   API Docs:  http://localhost:8000/docs"
echo ""
echo -e "${BLUE}📊 Database:${NC}"
echo "   Supabase:  $SUPABASE_URL"
echo "   Mode:      PRODUCTION (real data, real OAuth)"
echo ""
echo -e "${BLUE}📝 Logs:${NC}"
echo "   Backend:   tail -f backend.log"
echo ""
echo -e "${BLUE}🛑 Stop server:${NC}"
echo "   ./stop-prod.sh"
echo ""
echo -e "${YELLOW}⚠️  IMPORTANT: You are using PRODUCTION database${NC}"
echo "   - All data changes are PERMANENT"
echo "   - Use real GitHub OAuth (not test users)"
echo "   - Monitor Supabase dashboard for activity"
echo ""
