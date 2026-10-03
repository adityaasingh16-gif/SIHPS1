import express from 'express'
import cors from 'cors'

const app = express()
const port = Number(process.env.PORT || 3002)
const apiBase = (process.env.DHRISHTI_API_URL || 'http://localhost:8000').replace(/\/$/, '')

app.use(cors())
app.use(express.json({ limit: '32kb' }))

// Preserve the standalone UI contract while delegating to the authenticated,
// role-filtered local RAG endpoint. The browser's bearer token is never stored.
app.post('/api/chat', async (req, res) => {
  const messages = req.body?.messages
  if (!Array.isArray(messages) || messages.length === 0) {
    return res.status(400).json({ error: 'Invalid messages format' })
  }
  const authorization = req.get('authorization')
  if (!authorization) return res.status(401).json({ error: 'Sign in to use project records.' })
  const lastUser = [...messages].reverse().find((m) => m?.role === 'user' && typeof m.content === 'string')
  if (!lastUser) return res.status(400).json({ error: 'A user message is required.' })
  const history = messages.slice(0, messages.lastIndexOf(lastUser))
    .filter((m) => ['user', 'assistant'].includes(m?.role) && typeof m.content === 'string')
    .slice(-6)
  try {
    const response = await fetch(`${apiBase}/groq-chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: authorization },
      body: JSON.stringify({ message: lastUser.content, history }),
      signal: AbortSignal.timeout(60000),
    })
    const data = await response.json()
    if (!response.ok) return res.status(response.status).json({ error: data.detail || 'Assistant request failed.' })
    return res.json({ content: data.answer, sources: data.sources || [], model: data.model })
  } catch (err) {
    console.error('Local Dhrishti assistant unavailable:', err.message)
    return res.status(502).json({ error: 'The local assistant is unavailable. Please retry shortly.' })
  }
})

app.get('/api/project-context', async (_req, res) => {
  try {
    const response = await fetch(`${apiBase}/groq-chat/health`, { signal: AbortSignal.timeout(3000) })
    const health = await response.json()
    return res.json({ loaded: health.status === 'online', model: health.model, provider: 'local',
      contextLength: 0, structureLength: 0 })
  } catch {
    return res.json({ loaded: false, model: process.env.OLLAMA_CHAT_MODEL || 'llama3.1',
      provider: 'local', contextLength: 0, structureLength: 0 })
  }
})

app.listen(port, () => console.log(`Local assistant bridge listening on port ${port}`))
