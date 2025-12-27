#!/bin/bash
# Stop backend production server for a11yhood
# Cleanly shuts down the backend server

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🛑 Stopping a11yhood backend production server...${NC}"
echo ""

# Kill backend (uvicorn)
echo -e "${YELLOW}🔧 Stopping backend server...${NC}"
pkill -f "uvicorn main:app"
if [ $? -eq 0 ]; then
  echo -e "${GREEN}✓ Backend stopped${NC}"
else
  echo -e "${YELLOW}⚠️  No backend process found${NC}"
fi

# Give process time to clean up
sleep 1

echo ""
echo -e "${GREEN}✅ Backend production server stopped${NC}"
echo ""
echo -e "${BLUE}💡 To restart production:${NC}"
echo "   ./start-prod.sh"
echo ""
echo -e "${BLUE}💡 To start development environment instead:${NC}"
echo "   ./start-dev.sh"
echo ""
