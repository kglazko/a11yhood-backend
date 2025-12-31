#!/bin/bash
# Start backend production server for a11yhood
# This script starts the backend API server on port 8000 in production mode
# Uses production Supabase database with real OAuth
# 
# Usage:
#   ./start-prod.sh        # Normal start
#   ./start-prod.sh --help # Show help
#   ./start-prod.sh --no-build # Skip image build

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Timing helper
SECONDS=0
ts() {
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
  echo "Starts backend production server using Docker (production Supabase database)"
  echo ""
  echo "Prerequisites:"
  echo "  - Docker running (colima start)"
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
  if docker build -t a11yhood-backend:prod . 2>/tmp/build.out; then
    echo -e "${GREEN}✓ Image ready${NC}"
  else
    echo -e "${RED}✗ Build failed${NC}"
    echo ""
    echo "  Build logs:"
    tail -n 30 /tmp/build.out 2>/dev/null || true
    exit 1
  fi
  echo ""
else
  echo -e "${YELLOW}⏭️  Skipping build (--no-build)${NC}"
  echo ""
fi

# Check if container is already running and stop it
echo -e "${YELLOW}🔧 Checking for existing containers...${NC} (t=$(ts))"
if docker ps -a --filter "name=a11yhood-backend-prod" --format "{{.Names}}" | grep -q "a11yhood-backend-prod"; then
  echo "  Stopping existing container..."
  docker stop a11yhood-backend-prod >/dev/null 2>&1
  docker rm a11yhood-backend-prod >/dev/null 2>&1
  sleep 1
fi
echo -e "${GREEN}✓ Ready to start${NC}"
echo ""

# Start production container
echo -e "${GREEN}🚀 Starting production container...${NC} (t=$(ts))"
echo "   Server will be available at: http://localhost:8001"
echo "   API documentation at: http://localhost:8001/docs"
echo ""

docker run \
  -d \
  --name a11yhood-backend-prod \
  --env-file .env \
  -p 8001:8000 \
  --restart unless-stopped \
  --health-cmd="curl -f http://localhost:8000/health || exit 1" \
  --health-interval=30s \
  --health-timeout=3s \
  --health-retries=3 \
  --health-start-period=5s \
  a11yhood-backend:prod

if [ $? -ne 0 ]; then
  echo -e "${RED}✗ Failed to start production container${NC}"
  exit 1
fi

# Wait for server to be ready
echo -e "${YELLOW}⏳ Waiting for server to start...${NC}"
for i in {1..60}; do
  if curl -s http://localhost:8001/health >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Backend is ready!${NC} (t=$(ts))"
    break
  fi
  
  # Check if container is still running
  if ! docker ps --filter "name=a11yhood-backend-prod" --format "{{.Names}}" | grep -q "a11yhood-backend-prod"; then
    echo -e "${RED}✗ Container is not running${NC}"
    echo "  Check logs with: docker logs a11yhood-backend-prod"
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
if ! curl -s http://localhost:8000/health >/dev/null 2>&1; then
  echo -e "${RED}✗ Server failed to start within 60 seconds${NC}"
  echo "  Check logs with: docker logs a11yhood-backend-prod"
  docker logs --tail=50 a11yhood-backend-prod
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
echo "   docker logs -f a11yhood-backend-prod"
echo ""
echo -e "${BLUE}🛑 To stop the server:${NC}"
echo "   ./stop-prod.sh"
echo ""
echo -e "${YELLOW}⚠️  Remember:${NC}"
echo "   - This is PRODUCTION mode with real authentication"
echo "   - Never reset or seed the production database"
echo "   - Monitor logs with: docker logs -f a11yhood-backend-prod"
echo ""
