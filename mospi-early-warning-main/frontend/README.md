# Dhrishti Frontend Deployment

The Vite frontend is a static site. It does not host the FastAPI backend, MongoDB,
or Ollama. The production site therefore needs a separately deployed backend and
an Ollama service reachable by that backend.

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
| `VITE_API_URL` | The public HTTPS origin of the FastAPI backend, without a trailing slash or `/api`, e.g. `https://your-api.example.com` |
| `VITE_ENABLE_DEMO_LOGIN` | `false` (recommended; only enable for isolated test deployments) |

Configure the backend environment as described in `../backend/README.md`:

- `CORS_ORIGINS=https://sihps-1-f.vercel.app` (add each actual frontend origin explicitly)
- `FRONTEND_URL=https://sihps-1-f.vercel.app`
- `GOOGLE_REDIRECT_URI=https://your-api.example.com/auth/google/callback`
- `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` from the Google OAuth client
- a strong persistent `JWT_SECRET`, persistent database storage, and configured MongoDB
- `OLLAMA_BASE_URL` pointing to an Ollama service reachable from the backend network; `localhost` points to the backend container itself
- pull the configured `OLLAMA_CHAT_MODEL` and `OLLAMA_EMBED_MODEL` into that Ollama service

Add the exact `GOOGLE_REDIRECT_URI` to the OAuth client's authorized redirect
URIs. Never put backend secrets in Vercel `VITE_*` variables; Vite exposes those
values to every browser.

If the API URL is unset or the API path returns the frontend HTML instead of
JSON, sign-in now reports that the backend is not connected instead of showing
a confusing JSON parsing error. The assistant health check also remains offline
until the backend and its local model service are reachable.
