# Security Testing Guide

This document provides comprehensive guidance on testing security features and identifying potential vulnerabilities in a11yhood.

## Core Testing Principles

**CRITICAL**: All security tests MUST follow these principles:
3. ✅ Use real HTTP calls and database operations
4. ✅ Test both positive cases (allowed) and negative cases (blocked)
5. ✅ Follow the same patterns as integration tests

## Quick Commands

```bash
uv run pytest tests/test_security.py -v

# Check for dependency vulnerabilities
cd backend && uv pip check

# Secret scanning (if available)
gitleaks detect --no-banner --redact
```

## Automated Security Test Suite

Our comprehensive security test suite (33 total tests) covers:

### Backend: Authentication & Authorization (9 tests)
Located in: `backend/tests/test_security.py`

✅ **Authentication**
- Unauthenticated requests rejected (401)
- Auth tokens validated on protected endpoints

✅ **Ownership Enforcement**
- Non-owners cannot update products (403)
- Non-owners cannot modify collections (403)
- Admins can update any product
- Private collections blocked for non-owners (403)
- Owners can access their private collections

✅ **Role-Based Access Control**
- Regular users cannot approve requests (403)
- Moderators can approve product ownership requests
- Only admins can trigger scrapers (moderators blocked)
- Admin scraper access verified

### Backend: Database Security (9 tests)
Located in: `backend/tests/test_security.py`

✅ **SQL Injection Prevention**
- Malicious SQL in product names safely handled
- SQL injection in search queries prevented
- Parameterized queries via Supabase client verified

✅ **Input Validation**
- Large text fields accepted (no arbitrary limits)
- Special characters (unicode, symbols) preserved correctly
- Null byte injection prevented
- Invalid JSON rejected (422)
- Type confusion prevented (Pydantic validation)
- Integer overflow prevented (rating bounds 1-5)

✅ **Data Protection**
- Email addresses filtered from public endpoints
- Sensitive data not exposed in API responses

✅ **Backend Enforcement Verification**
- Unauthenticated product creation rejected (401)
- Unauthenticated collection creation rejected (401)
- Product updates by non-owners rejected (403)
- Collection mutations by non-owners rejected (403)
- Private collection access by non-owners rejected (403)
- Owner access to private collections allowed (200)

## Test Implementation Patterns

### Backend Security Test Pattern

```python
def test_unauthorized_action_rejected(auth_client, auth_client_2):
    """Test that users cannot perform actions on resources they don't own"""
    # User 1 creates resource
    response = auth_client.post("/api/resource", json={...})
    assert response.status_code == 201
    resource_id = response.json()["id"]
    
    # User 2 tries to modify it
    response = auth_client_2.put(f"/api/resource/{resource_id}", json={...})
    assert response.status_code == 403  # Forbidden
```

## Manual Security Checks

### Before Every Release

1. **Review Authentication Flow**
   - Test login/logout with dev tokens
   - Verify permission escalation attempts fail
   - Check role-based features (admin, moderator, user)

2. **Test Ownership Controls**
   - Try to modify other users' products → expect 403
   - Try to access private collections → expect 403
   - Verify admin override capabilities work

3. **Input Fuzzing**
   - Test with SQL injection strings: `'; DROP TABLE products; --`
   - Test with XSS payloads: `<script>alert(1)</script>`
   - Test with null bytes: `\x00`
   - Test with unicode: `你好 🎉 ™ ® §`
   - Test with oversized payloads (10KB+)

4. **API Security**
   - Verify all mutation endpoints require authentication
   - Check error messages don't leak sensitive info
   - Verify CORS settings allow only trusted origins
   - Test OAuth flows reject mismatched state
   - Ensure HTTPS enforced in production

### Checklist for New Features

When adding new features, ensure:
- [ ] All mutation API endpoints require authentication
- [ ] Authorization checks for ownership/roles implemented
- [ ] Input validation via Pydantic models with proper types
- [ ] Sensitive data filtered in public API responses
- [ ] Security tests added to `test_security.py`
- [ ] Error handling doesn't leak internal details (use generic messages)
- [ ] Logs don't expose tokens, emails, or sensitive payloads

## Known Security Measures

✅ **Implemented**
- JWT-based authentication (dev-token-{userId} in test mode)
- Role-based access control (admin, moderator, user)
- Ownership validation on mutations
- Pydantic input validation with strict types
- HttpUrl type for XSS prevention
- Parameterized queries via Supabase (SQL injection safe)
- Private collection access control
- Email filtering in public endpoints
- Product ownership via product_editors relationship table

⚠️ **Not Yet Implemented**
- Rate limiting on endpoints
- CSRF protection (using token auth, not cookies)
- Content Security Policy headers
- Request size limits at web server level

## CI/CD Integration

Add these checks to your CI pipeline:

```yaml
# Example GitHub Actions workflow
- name: Backend Security Tests
  run: |
    uv run pytest tests/test_security.py -v
    
- name: Dependency Audit
  run: |
    uv pip check
```

## Test Coverage Summary

| Category |  Tests | 
|----------|--------------|
| Authentication | 1  |
| Authorization | 8  | 
| URL Validation | 0 |
| SQL Injection | 2 |
| Input Validation | 5 |
| Data Protection | 2 | 
| **Total** | **18** | 

## Reporting Security Issues

If you discover a security vulnerability:
1. ❌ Do NOT open a public issue
2. ✅ Email the maintainers directly
3. ✅ Provide detailed reproduction steps
4. ✅ Allow time for patching before disclosure

## Additional Resources

- [SECURITY_BEST_PRACTICES.md](./SECURITY_BEST_PRACTICES.md) - Security coding guidelines
- [AGENT_GUIDE.md](./AGENT_GUIDE.md) - Developer guide with security defaults
- Backend tests: `backend/tests/test_security.py`
- Frontend tests: `frontend/src/__tests__/security/`

## CI Integration
- Add dependency scans to CI (npm audit, uv pip check).
- Add security test jobs for backend (`pytest -m security`) and frontend (`npm run test:run -- src/__tests__/security`).
- Fail fast on secret scan findings.

## Security Test Suite Outline
- Backend (`tests/test_security.py`, `tests/test_idor.py`):
  - `test_auth_required_for_mutations` (POST/PUT/DELETE without token → 401)
  - `test_role_matrix_for_product_management` (admin vs. moderator vs. user capabilities)
  - `test_idor_collection_privacy` (private collections not accessible)
  - `test_idor_product_management_requests` (cannot approve/reject if not moderator/admin)
  - `test_rate_limit_discussions_reviews` (multiple POSTs → 429)
  - `test_scraper_domain_allowlist` (reject non-GitHub/Ravelry/Thingiverse URLs)
  - `test_reject_script_in_user_content` (scripts rejected/escaped)


## Reporting
- Capture failures with request/response snippets excluding secrets.
- File issues privately; avoid public disclosure. Follow the repo SECURITY policy for coordinated disclosure.