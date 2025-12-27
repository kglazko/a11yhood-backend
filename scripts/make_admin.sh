#!/usr/bin/env bash
# Promote a user to admin in TEST_MODE using dev-token auth.
# Usage: bash backend/scripts/make_admin.sh <USER_ID> [API_BASE_URL]
# Defaults API_BASE_URL to http://localhost:8000 if not provided.

set -euo pipefail

USER_ID="${1-}"
API_BASE_URL="${2:-http://localhost:8000}"

if [[ -z "${USER_ID}" ]]; then
  echo "Usage: bash backend/scripts/make_admin.sh <USER_ID> [API_BASE_URL]" >&2
  exit 1
fi

PATCH_URL="${API_BASE_URL}/api/users/${USER_ID}/role"

echo "Promoting user ${USER_ID} to admin via ${PATCH_URL}" >&2

curl -sS -X PATCH "${PATCH_URL}" \
  -H "Content-Type: application/json" \
  -H "Authorization: dev-token-${USER_ID}" \
  --data '{"role":"admin"}' | jq '.'
