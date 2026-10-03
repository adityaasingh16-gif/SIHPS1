# Dhrishti Local Assistant

The standalone UI delegates to the authenticated Dhrishti chat API. Answers use role-filtered project records and the configured local Ollama service. It does not crawl source files or send prompts to a hosted LLM.

## Run

1. Start the Dhrishti backend and local Ollama service from the repository root with `docker compose up --build`.
2. Pull the local models once: `docker compose exec ollama ollama pull llama3.2` and `docker compose exec ollama ollama pull nomic-embed-text`.
3. Install the UI dependencies with `npm install`.
4. Start the bridge and UI with `npm run dev`.
5. Sign in to Dhrishti in the same browser origin so the UI can use the existing `dhrishti-token` session.

The bridge defaults to `http://localhost:8000`; set `DHRISHTI_API_URL` to use another local API address. The backend reads `OLLAMA_CHAT_MODEL`, `OLLAMA_EMBED_MODEL`, and `OLLAMA_BASE_URL`.
