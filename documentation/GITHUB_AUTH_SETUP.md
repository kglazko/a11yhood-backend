# GitHub Authentication Setup

## Overview

a11yhood uses Supabase Auth with GitHub OAuth for user authentication. This provides:
- ✅ GitHub login (no password needed)
- ✅ Automatic user account creation  
- ✅ Secure JWT tokens
- ✅ No custom auth code needed

## Current Implementation

**Backend** (`services/auth.py`):
- Verifies Supabase JWT tokens
- Extracts user from token
- Protects API endpoints with `Depends(get_current_user)`

## Setup Steps

### 1. Configure GitHub OAuth App

1. Go to https://github.com/settings/developers
2. Click "New OAuth App"
3. Fill in:
   - **Application name**: `a11yhood`
   - **Homepage URL**: `https://yourdomain.com` (or `http://localhost:5173` for dev)
   - **Authorization callback URL**: `https://[your-project-ref].supabase.co/auth/v1/callback`
4. Save and copy:
   - **Client ID**
   - **Client Secret**

### 2. Configure Supabase

1. Go to your Supabase project dashboard
2. Navigate to **Authentication** → **Providers**
3. Find **GitHub** and enable it
4. Enter:
   - **Client ID**: From GitHub OAuth app
   - **Client Secret**: From GitHub OAuth app
5. (Optional) Configure redirect URLs:
   - Go to **Authentication** → **URL Configuration**
   - Add site URL: `https://yourdomain.com`
   - Add redirect URLs: `http://localhost:5173` (for dev)

### 3. Environment Variables

**Backend** (`.env`):
```bash
SUPABASE_URL=https://[your-project-ref].supabase.co
SUPABASE_KEY=[your-service-role-key]
SUPABASE_ANON_KEY=[your-anon-key]
```

### 4. Test Authentication

1. Start backend:
   ```bash
   uv run uvicorn main:app --reload
   ```


## User Data Structure

When authenticated, the user object contains:
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "user_metadata": {
    "avatar_url": "https://avatars.githubusercontent.com/...",
    "email": "user@example.com",
    "email_verified": true,
    "full_name": "User Name",
    "iss": "https://api.github.com",
    "name": "User Name",
    "preferred_username": "username",
    "provider_id": "12345",
    "sub": "12345",
    "user_name": "username"
  },
  "app_metadata": {
    "provider": "github",
    "providers": ["github"]
  },
  "aud": "authenticated",
  "created_at": "2025-12-17T...",
  "role": "authenticated"
}
```


## Admin Users

To make a user an admin:

1. Go to Supabase Dashboard → Authentication → Users
2. Find the user
3. Edit their user metadata
4. Add: `"is_admin": true`
5. Save

Or via SQL:
```sql
UPDATE auth.users 
SET raw_user_meta_data = raw_user_meta_data || '{"is_admin": true}'::jsonb
WHERE email = 'admin@example.com';
```

## Troubleshooting

### "Invalid token" errors
- Check that `SUPABASE_KEY` is the **service_role** key (not anon key)
- Verify JWT token is being sent in Authorization header
- Check token hasn't expired

### GitHub OAuth redirect fails
- Verify callback URL matches exactly in GitHub app settings
- Check Supabase project URL is correct
- Ensure GitHub OAuth is enabled in Supabase

### User not created in database
- Supabase Auth automatically creates users in `auth.users` table
- Your app doesn't need to manually create user records
- Use user ID from JWT for foreign keys

### Local development issues
- Make sure localhost URLs are in Supabase redirect URLs
- Use HTTP for localhost (HTTPS not required for dev)
- Check browser console for errors

## Security Notes

- ✅ Never expose `SUPABASE_KEY` (service_role) in frontend
- ✅ Frontend only uses `SUPABASE_ANON_KEY`
- ✅ JWTs are verified on backend
- ✅ Row Level Security (RLS) can be enabled in Supabase
- ✅ No passwords stored (GitHub handles auth)
