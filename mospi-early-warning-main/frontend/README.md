# Dhrishti Frontend Deployment

The Vite frontend is a static site. It does not host the FastAPI backend or
MongoDB. Assistant generation uses Groq from the backend; Ollama is optional for
dense embeddings only.

## Local development

```bash
npm ci
npm run dev
```

Vite proxies `/api` to `http://127.0.0.1:8000` during development. Demo role
buttons are shown only in development unless explicitly enabled at build time.

## Vercel deployment

Set these **Production** environment variables for the Vercel project, then
redeploy the frontend:

| Variable | Value |
| --- | --- |
| `VITE_API_URL` | `https://sihps1-f.onrender.com` (backend origin; no trailing slash or `/api`) |
| `VITE_ENABLE_DEMO_LOGIN` | `false` (recommended; only enable for isolated test deployments) |

Configure the backend environment as described in `../backend/README.md`:

- `CORS_ORIGINS=https://sihps-1-om86z0b39-adityaasingh16-gifs-projects.vercel.app` (replace/add the public production origin once configured)
- `FRONTEND_URL=https://sihps-1-om86z0b39-adityaasingh16-gifs-projects.vercel.app`
- `GOOGLE_REDIRECT_URI=https://sihps1-f.onrender.com/auth/google/callback`
- `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` from the Google OAuth client
- `GROQ_API_KEY`, `GROQ_CHAT_MODEL=llama-3.3-70b-versatile`, and `GROQ_REQUEST_TIMEOUT_SECONDS=30`
- a strong persistent `JWT_SECRET`, persistent database storage, and configured MongoDB

Add the exact `GOOGLE_REDIRECT_URI` to the OAuth client's authorized redirect
URIs. Never put backend secrets in Vercel `VITE_*` variables; Vite exposes those
values to every browser.

If the API URL is unset or the API path returns the frontend HTML instead of
JSON, sign-in now reports that the backend is not connected instead of showing
a confusing JSON parsing error. The assistant status checks Groq reachability and
reports unavailable cleanly when its key or provider is unavailable.
