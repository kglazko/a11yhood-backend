#!/bin/bash
# Start backend development server for a11yhood
# This script starts the backend API server on port 8000
# 
# Usage:
#   ./start-dev.sh              # Normal start
#   ./start-dev.sh --reset-db   # Reset database before starting
#   ./start-dev.sh --help       # Show help

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
RESET_DB=false
HELP=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --reset-db)
      RESET_DB=true
      shift
      ;;
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
  echo "Usage: ./start-dev.sh [OPTIONS]"
  echo ""
  echo "Options:"
  echo "  --reset-db   Reset database before starting"
  echo "  --help       Show this help message"
  exit 0
fi

# Don't exit on error, handle errors gracefully
set +e

echo -e "${BLUE}🚀 Starting a11yhood backend development server...${NC} (t=0s)"
echo ""

# Kill any existing processes
echo -e "${YELLOW}🔄 Stopping existing backend server...${NC} (t=$(ts))"
pkill -f "uvicorn main:app" 2>/dev/null || true
sleep 1

# Reset database if requested
if [ "$RESET_DB" = true ]; then
  echo -e "${YELLOW}🗑️  Resetting database...${NC} (t=$(ts))"
  rm -f test.db
  echo -e "${GREEN}✓ Database reset${NC}"
fi

# Start backend in background
echo -e "${BLUE}🔧 Starting backend server (port 8000)...${NC} (t=$(ts))"

# Check if .env.test exists
if [ ! -f .env.test ]; then
  echo -e "${RED}✗ Error: .env.test not found in backend/${NC}"
  echo "   Please create backend/.env.test with required environment variables"
  exit 1
fi

# Export all .env.test variables and set ENV_FILE for Pydantic
export ENV_FILE=.env.test
export $(cat .env.test | grep -v '^#' | xargs)

# Seed deterministic test users when using local SQLite so admin/mod roles persist after resets
DB_URL="${DATABASE_URL:-sqlite:///./test.db}"
SEED_CMD=""
if command -v uv >/dev/null 2>&1; then
  SEED_CMD="uv run python seed_test_users.py"
  SEED_SOURCES_CMD="uv run python seed_supported_sources.py"
  SEED_TERMS_CMD="uv run python seed_scraper_search_terms.py"
elif [ -x ".venv/bin/python" ]; then
  SEED_CMD=".venv/bin/python seed_test_users.py"
  SEED_SOURCES_CMD=".venv/bin/python seed_supported_sources.py"
  SEED_TERMS_CMD=".venv/bin/python seed_scraper_search_terms.py"
else
  SEED_CMD="python seed_test_users.py"
  SEED_SOURCES_CMD="python seed_supported_sources.py"
  SEED_TERMS_CMD="python seed_scraper_search_terms.py"
fi

if [[ "$DB_URL" == sqlite* ]]; then
  echo -e "${YELLOW}🌐 Seeding supported sources...${NC} (t=$(ts))"
  if sh -c "$SEED_SOURCES_CMD" >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Supported sources seeded${NC}"
  else
    echo -e "${RED}✗ Failed to seed supported sources${NC}"
  fi
  
  echo -e "${YELLOW}🔎 Seeding scraper search terms...${NC} (t=$(ts))"
  if sh -c "$SEED_TERMS_CMD" >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Scraper search terms seeded${NC}"
  else
    echo -e "${RED}✗ Failed to seed scraper search terms${NC}"
  fi
  
  echo -e "${YELLOW}👤 Seeding test users (admin/mod/user)...${NC} (t=$(ts))"
  if sh -c "$SEED_CMD" >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Test users seeded${NC}"
  else
    echo -e "${RED}✗ Failed to seed test users${NC}"
  fi
else
  echo -e "${YELLOW}ℹ Skipping test user seeding (DATABASE_URL not sqlite)${NC}"
fi

# Prefer uv, fallback to local venv or system Python
BACKEND_CMD=""
if command -v uv >/dev/null 2>&1; then
  # Ensure backend dependencies are installed (uvicorn, fastapi, etc.)
  echo -e "${YELLOW}📦 Syncing backend dependencies with uv...${NC} (t=$(ts))"
  ( uv sync >/dev/null 2>&1 || true)
  BACKEND_CMD="uv run python -m uvicorn main:app --reload --port 8000 --host 0.0.0.0"
elif [ -x ".venv/bin/python" ]; then
  BACKEND_CMD=".venv/bin/python -m uvicorn main:app --reload --port 8000 --host 0.0.0.0"
else
  BACKEND_CMD="python -m uvicorn main:app --reload --port 8000 --host 0.0.0.0"
fi

echo -e "${YELLOW}▶ Backend start command:${NC} $BACKEND_CMD"
sh -c "$BACKEND_CMD" > backend.log 2>&1 &
BACKEND_PID=$!

# Wait for backend to start
echo -e "${YELLOW}⏳ Waiting for backend to start...${NC} (t=$(ts))"
BACKEND_READY=false
for i in {1..40}; do
  if curl -s http://localhost:8000/health > /dev/null 2>&1 || curl -s http://localhost:8000/docs > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Backend is running on http://localhost:8000${NC}"
    BACKEND_READY=true
    break
  fi
  echo -n "."
  sleep 1
done

if [ "$BACKEND_READY" = false ]; then
  echo -e "${RED}✗ Backend failed to start after 30 seconds${NC}"
  echo -e "${YELLOW}Last 20 lines of backend.log:${NC}"
  tail -20 backend.log
  exit 1
fi

echo ""
echo -e "${GREEN}✅ Backend development server started!${NC} (t=$(ts))"
echo ""
echo -e "${BLUE}📍 Services:${NC}"
echo "   Backend:  http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo -e "${BLUE}📋 Process ID:${NC}"
echo "   Backend:  $BACKEND_PID"
echo ""
echo -e "${BLUE}📝 Logs:${NC}"
echo "   Backend:  tail -f backend.log"
echo ""
echo -e "${BLUE}🛑 To stop server:${NC}"
echo "   ./stop-dev.sh"
echo "   or: pkill -f 'uvicorn main:app'"
echo ""
echo -e "${BLUE}🔐 Test Users:${NC}"
echo "   admin_user     - Full system access"
echo "   moderator_user - Content moderation"  
echo "   regular_user   - Regular user features"
echo ""
echo -e "${BLUE}📚 Documentation:${NC}"
echo "   Local Testing:    LOCAL_TESTING.md"
echo "   API Reference:    documentation/API_REFERENCE.md"
echo "   Architecture:     documentation/ARCHITECTURE.md"
echo ""
