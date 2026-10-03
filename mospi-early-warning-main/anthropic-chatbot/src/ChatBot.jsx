import { useState, useRef, useEffect } from 'react'
import './ChatBot.css'

const API_URL = '/api/chat'

function ChatBot() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [service, setService] = useState({ loaded: false, model: 'llama3.2' })
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    fetch('/api/project-context').then((res) => res.json()).then(setService).catch(() => {})
  }, [])

  const handleSend = async (e) => {
    e.preventDefault()
    if (!input.trim() || loading) return

    const userMessage = { role: 'user', content: input, timestamp: Date.now() }
    setMessages(prev => [...prev, userMessage])
    setInput('')
    setLoading(true)
    setError(null)

    try {
      const res = await fetch(API_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(localStorage.getItem('dhrishti-token')
            ? { Authorization: `Bearer ${localStorage.getItem('dhrishti-token')}` }
            : {}),
        },
        body: JSON.stringify({ messages: [...messages, userMessage] })
      })

      const data = await res.json()
      if (!res.ok) throw new Error(data.error || 'Failed to get response')
      setMessages(prev => [...prev, { role: 'assistant', content: data.content, sources: data.sources, timestamp: Date.now() }])
    } catch (err) {
      setError(err.message)
      setMessages(prev => [...prev, { role: 'assistant', content: 'Sorry, something went wrong. Please try again.', timestamp: Date.now() }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="chatbot-container">
      <header className="chatbot-header">
        <h1>💬 Dhrishti Assistant</h1>
        <span className="status">
          {service.loaded ? `Local · ${service.model}` : 'Local assistant offline'}
        </span>
      </header>

      <div className="chatbot-messages" role="log" aria-live="polite">
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            <div className="message-bubble">
              {msg.role === 'assistant' && <span className="bot-icon">🤖</span>}
              <div className="message-content">{msg.content}</div>
              {msg.sources?.length > 0 && (
                <div className="message-content source-list">
                  Sources: {msg.sources.map((source) => source.title).join(', ')}
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="message assistant loading">
            <div className="message-bubble">
              <span className="bot-icon">🤖</span>
              <div className="typing-indicator">
                <span></span><span></span><span></span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {error && <div className="error-banner">{error}</div>}

      <form onSubmit={handleSend} className="chatbot-input-form">
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask me anything..."
          disabled={loading}
          className="chatbot-input"
          aria-label="Chat input"
        />
        <button type="submit" disabled={loading || !input.trim()} className="chatbot-send-btn">
          {loading ? '⏳' : '➤'}
        </button>
      </form>
    </div>
  )
}

export default ChatBot
