# Google login setup

The application implements the Google OpenID Connect authorization-code flow. A Google OAuth client is required before the button can authenticate real accounts.

1. Open Google Cloud Console and select or create a project.
2. Configure the OAuth consent screen.
3. Create an **OAuth client ID** with application type **Web application**.
4. Add this authorized redirect URI for local development:

   `http://localhost:8000/auth/google/callback`

5. Add these values to `.env` when running the backend locally, or `.env.docker` when using Docker Compose:

   ```dotenv
   GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=your-client-secret
   GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
   FRONTEND_URL=http://localhost:5173
   OAUTH_COOKIE_SECURE=false
   ```

6. Apply migrations and restart the backend:

   ```powershell
   .\.venv\Scripts\python.exe -m alembic upgrade head
   ```

For production, register the production callback URL, set `GOOGLE_REDIRECT_URI` and `FRONTEND_URL` to HTTPS URLs, and set `OAUTH_COOKIE_SECURE=true`.
