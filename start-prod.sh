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
NO_BUILD=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --help)
      HELP=true
      shift
      ;;
    --no-build)
      NO_BUILD=true
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
  echo "Starts backend production server using Docker Compose v2 (production Supabase database)"
  echo ""
  echo "Prerequisites:"
  echo "  - Docker running (colima start)"
  echo "  - Docker Compose v2 plugin available (docker compose)"
  echo "  - .env configured with production Supabase credentials"
  echo "  - Production Supabase project set up with schema applied"
  echo ""
  echo "Options:"
  echo "  --help       Show this help message"
   echo "  --no-build   Skip image build (use when image is already loaded)"
  echo ""
  echo "See documentation/DEPLOYMENT_PLAN.md for detailed setup instructions"
  exit 0
fi

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
  echo -e "${RED}✗ Docker is not running${NC}"
  echo "  Please start Docker (or Colima) first:"
  echo "    colima start"
  exit 1
fi

# Ensure Docker Compose v2 plugin is available
if ! docker compose version >/dev/null 2>&1; then
  echo -e "${RED}✗ Docker Compose v2 plugin (docker compose) not found${NC}"
  echo "  Install the Compose v2 plugin or use plain Docker script:"
  echo "    - macOS: Use Docker Desktop (includes Compose v2)"
  echo "    - Linux (Debian/Ubuntu): sudo apt-get install -y docker-compose-plugin"
  echo "    - Fallback: ./start-prod-plain.sh"
  exit 1
fi

echo -e "${BLUE}🚀 Starting a11yhood backend PRODUCTION server (Docker)...${NC} (t=0s)"
echo ""

# Validate production environment  
if [ ! -f .env ]; then
  echo -e "${RED}✗ .env file not found${NC}"
  echo "  Production requires a .env file with Supabase credentials"
  echo "  See documentation/DEPLOYMENT_PLAN.md for setup instructions"
  exit 1
fi

# Validate Supabase environment variables
echo -e "${YELLOW}🔧 Validating production configuration...${NC} (t=$(ts))"

# Quick check without sourcing (Docker will source it)
if ! grep -q "SUPABASE_URL=" .env || ! grep -q "SUPABASE_KEY=" .env; then
  echo -e "${RED}✗ Missing required environment variables in .env${NC}"
  echo "  SUPABASE_URL and SUPABASE_KEY must be set"
  echo "  See documentation/DEPLOYMENT_PLAN.md for setup instructions"
  exit 1
fi

SUPABASE_URL=$(grep "^SUPABASE_URL=" .env | cut -d '=' -f2- | tr -d '"')

if [[ "$SUPABASE_URL" == *"localhost"* ]]; then
  echo -e "${RED}✗ SUPABASE_URL points to localhost${NC}"
  echo "  Production must use a real Supabase project URL"
  echo "  Format: https://your-project.supabase.co"
  exit 1
fi

echo -e "${GREEN}✓ Environment validated${NC}"
echo "   Supabase URL: $SUPABASE_URL"
echo ""

echo -e "${YELLOW}⚠️  PRODUCTION MODE${NC}"
echo "   Using Supabase database"
echo "   OAuth enabled (real authentication)"
echo "   DO NOT seed or reset production database"
echo ""

if [ "$NO_BUILD" = false ]; then
  echo -e "${YELLOW}🔨 Building production Docker image...${NC} (t=$(ts))"
  if docker compose build backend-prod 2>/tmp/build.out; then
    echo -e "${GREEN}✓ Image ready${NC}"
  else
    echo -e "${YELLOW}⚠️  Build failed, retrying with legacy builder...${NC}"
    if DOCKER_BUILDKIT=0 docker compose build backend-prod 2>/tmp/build_legacy.out; then
      echo -e "${GREEN}✓ Image ready (legacy builder)${NC}"
    else
      echo -e "${RED}✗ Build failed with both builders${NC}"
      echo "  Consider building the image on another machine and transferring it:"
      echo "    # On your dev machine"
      echo "    docker build --target production -t a11yhood-backend:prod ."
      echo "    docker save a11yhood-backend:prod -o a11yhood-backend-prod.tar"
      echo "    scp a11yhood-backend-prod.tar user@server:/tmp/"
      echo "    # On the server"
      echo "    docker load -i /tmp/a11yhood-backend-prod.tar"
      echo "    docker compose --profile production up -d --no-build backend-prod"
      echo ""
      echo "  Build logs (first attempt):"
      tail -n 30 /tmp/build.out 2>/dev/null || true
      echo ""
      echo "  Build logs (legacy attempt):"
      tail -n 30 /tmp/build_legacy.out 2>/dev/null || true
      exit 1
    fi
  fi
  echo ""
else
  echo -e "${YELLOW}⏭️  Skipping build (--no-build)${NC}"
fi

# Start production container
echo -e "${GREEN}🚀 Starting production container...${NC} (t=$(ts))"
echo "   Server will be available at: http://localhost:8001"
echo "   API documentation at: http://localhost:8001/docs"
echo "   (Production uses port 8001, development uses port 8000)"
echo ""

docker compose --profile production up -d backend-prod

if [ $? -ne 0 ]; then
  echo -e "${RED}✗ Failed to start production container${NC}"
  exit 1
fi

# Wait for server to be ready
echo -e "${YELLOW}⏳ Waiting for server to start...${NC}"
for i in {1..60}; do  # Production might take longer
  if curl -s http://localhost:8001/health >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Backend is ready!${NC} (t=$(ts))"
    break
  fi
  
  # Check if container is still running
  if ! docker compose ps backend-prod | grep -q "Up"; then
    echo -e "${RED}✗ Container is not running${NC}"
    echo "  Check logs with: docker compose logs backend-prod"
    exit 1
  fi
  
  sleep 1
  
  # Show progress
  if [ $i -eq 15 ]; then
    echo "  Still waiting..."
  fi
  if [ $i -eq 30 ]; then
    echo "  Taking longer than usual..."
  fi
  if [ $i -eq 45 ]; then
    echo "  Almost there..."
  fi
done

# Final check
if ! curl -s http://localhost:8001/health >/dev/null 2>&1; then
  echo -e "${RED}✗ Server failed to start within 60 seconds${NC}"
  echo "  Check logs with: docker compose logs backend-prod"
  docker compose logs --tail=50 backend-prod
  exit 1
fi

echo ""
echo -e "${GREEN}✅ PRODUCTION server is running!${NC} (t=$(ts))"
echo ""
echo -e "${BLUE}📡 Backend API:${NC}"
echo "   http://localhost:8001"
echo ""
echo -e "${BLUE}📚 API Documentation:${NC}"
echo "   http://localhost:8001/docs"
echo ""
echo -e "${BLUE}💡 To monitor logs:${NC}"
echo "   docker compose logs -f backend-prod"
echo ""
echo -e "${BLUE}🛑 To stop the server:${NC}"
echo "   ./stop-prod.sh"
echo ""
echo -e "${YELLOW}⚠️  Remember:${NC}"
echo "   - This is PRODUCTION mode with real authentication"
echo "   - Never reset or seed the production database"
echo "   - Monitor logs with: docker compose logs -f backend-prod"
echo ""
