#!/usr/bin/env python3
"""Test scraper API endpoint to debug 422 error"""
import asyncio
import sys
sys.path.insert(0, '.')

from database_adapter import DatabaseAdapter  
from config import settings

# Initialize test database
settings.TEST_MODE = True
db_adapter = DatabaseAdapter(settings)
db_adapter.init()

# Get a test admin user
result = db_adapter.table('users').select('*').eq('username', 'admin_user').execute()
if not result.data:
    print("No admin user found!")
    sys.exit(1)

admin_user = result.data[0]
print(f"Admin user: {admin_user['username']} ({admin_user['id']})")

# Test the scraper trigger with various payloads
import json

test_payloads = [
    {"source": "ravelry", "test_mode": True, "test_limit": 5},
    {"source": "thingiverse", "test_mode": False},
    {"source": "github", "testMode": True, "testLimit": 3},  # camelCase (should fail)
]

from models.scrapers import ScraperTriggerRequest

for i, payload in enumerate(test_payloads, 1):
    print(f"\n=== Test {i}: {json.dumps(payload)} ===")
    try:
        req = ScraperTriggerRequest(**payload)
        print(f"✓ Valid: source={req.source}, test_mode={req.test_mode}, test_limit={req.test_limit}")
    except Exception as e:
        print(f"✗ Validation error: {e}")
