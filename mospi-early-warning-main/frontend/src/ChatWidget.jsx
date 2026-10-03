import { useEffect, useRef, useState } from "react";
import { Bot, MessageSquare, Send, Sparkles, X } from "lucide-react";
import { askLocalAssistant, checkLocalAssistantHealth } from "./api";
import { useT } from "./hooks/useT";
import { useAuth } from "./AuthContext";

const SUGGESTION_KEYS = [
  "chat.suggestCritical",
  "chat.suggestOverruns",
  "chat.suggestHowScored",
  "chat.suggestShap",
];

export default function ChatWidget({ backendOnline }) {
  const t = useT();
  const { token } = useAuth();
  const suggestions = SUGGESTION_KEYS.map((k) => t(k));
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [assistantHealth, setAssistantHealth] = useState(null);
  const assistantOnline = assistantHealth ? assistantHealth.status === "online" : null;
  const [assistantWaking, setAssistantWaking] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    const checkHealth = async () => {
      // Retry up to 4 times with 15s gap — handles Render free-tier cold start (~50s)
      for (let attempt = 0; attempt < 4; attempt++) {
        const h = await checkLocalAssistantHealth();
        if (cancelled) return;
        if (h && h.status === "online") {
          setAssistantHealth(h);
          setAssistantWaking(false);
          return;
        }
        if (attempt === 0) setAssistantWaking(true);
        if (attempt < 3) await new Promise(r => setTimeout(r, 15000));
      }
      if (!cancelled) {
        setAssistantHealth({ status: "offline", model: "Groq" });
        setAssistantWaking(false);
      }
    };
    checkHealth();
    return () => { cancelled = true; };
  }, [open]);


  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  const send = async (text) => {
    const question = (text ?? input).trim();
    if (!question || loading) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: question }]);
    setLoading(true);

    const history = messages.slice(-8).map(({ role, content }) => ({ role, content }));
    if (!token) {
      setLoading(false);
      setMessages((m) => [...m, { role: "assistant", content: t("chat.signInRequired") }]);
      return;
    }

    const res = await askLocalAssistant(question, history, token, {
      onDelta: (delta) =>
        setMessages((m) => {
          const arr = [...m];
          const last = arr[arr.length - 1];
          if (last && last.role === "assistant" && last.streaming) {
            arr[arr.length - 1] = { ...last, content: last.content + delta };
          } else {
            arr.push({ role: "assistant", content: delta, streaming: true });
          }
          return arr;
        }),
      onMeta: (meta) =>
        setMessages((m) => {
          const arr = [...m];
          const idx = arr.length - 1;
          if (idx >= 0 && arr[idx].role === "assistant") {
            arr[idx] = { ...arr[idx], streaming: false, sources: meta?.sources || [] };
          }
          return arr;
        }),
    });
    setLoading(false);

    if (res?.failed) {
      setMessages((m) => [...m, {
        role: "assistant",
        content: res.unauthorized ? t("chat.signInAgain") : t("chat.localUnavailable"),
      }]);
    } else if (res === false) {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: t("chat.localUnavailable"),
        },
      ]);
    }
  };

  const onKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="fixed bottom-5 right-5 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-brand text-white shadow-lg shadow-brand/30 transition-transform hover:scale-105"
        aria-label={open ? t("chat.closeLabel") : t("chat.openLabel")}
        title={t("chat.askTitle")}
      >
        {open ? <X className="h-6 w-6" /> : <MessageSquare className="h-6 w-6" />}
        {!open && assistantOnline === false && (
          <span className="absolute -right-0.5 -top-0.5 h-3.5 w-3.5 rounded-full bg-risk-high ring-2 ring-white" />
        )}
      </button>

      {open && (
        <aside
          className="fixed bottom-24 right-5 z-50 flex max-h-[70vh] w-[calc(100vw-2.5rem)] max-w-md flex-col overflow-hidden rounded-2xl border border-line bg-raised shadow-2xl"
          role="dialog"
          aria-label={t("chat.title")}
        >
          <header className="flex items-center gap-3 border-b border-line bg-gradient-to-r from-brand to-brand-active px-4 py-3 text-white">
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-raised/20">
              <Bot className="h-5 w-5" />
            </span>
            <div className="flex-1">
              <p className="text-sm font-semibold">{t("chat.title")}</p>
              <p className="flex items-center gap-1.5 text-[11px] text-white/80">
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    assistantOnline === null
                      ? assistantWaking ? "animate-pulse bg-yellow-400" : "bg-risk-medium"
                      : assistantOnline
                      ? "bg-risk-low"
                      : "bg-risk-high"
                  }`}
                />
                {assistantOnline === null
                  ? assistantWaking ? "Waking up server, please wait (~30s)…" : t("chat.checkingLlm")
                  : assistantOnline
                  ? t("chat.aiReady", { model: assistantHealth?.model || "Groq" })
                  : t("chat.aiOffline")}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="rounded-lg p-1.5 text-white/80 hover:bg-raised/20"
              aria-label={t("chat.close")}
            >
              <X className="h-5 w-5" />
            </button>
          </header>

          <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-4">
            {messages.length === 0 && (
              <div className="space-y-2">
                <p className="text-sm text-fg-2">{t("chat.intro")}</p>
                {suggestions.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => send(s)}
                    className="block w-full rounded-lg border border-brand-border bg-brand-subtle px-3 py-2 text-left text-xs text-brand-hover transition-colors hover:bg-brand-subtle :bg-fg-2"
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}

            {messages.map((m, i) => (
              <div key={i} className={m.role === "user" ? "flex justify-end" : "flex justify-start"}>
                <div
                  className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${
                    m.role === "user"
                      ? "rounded-br-sm bg-brand text-white"
                      : "rounded-bl-sm border border-line bg-page text-fg"
                  }`}
                >
                  <p className="whitespace-pre-wrap">{m.content}</p>
                  {m.sources && m.sources.length > 0 && (
                    <div className="mt-2 border-t border-line pt-2">
                      <p className="mb-1 flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-fg-4">
                        <Sparkles className="h-3 w-3" /> {t("chat.sources")}
                      </p>
                      <div className="max-h-20 space-y-1 overflow-y-auto">
                        {m.sources.map((s, si) => (
                          <p key={si} className="truncate text-[10px] text-fg-3">
                            {s.title}
                          </p>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}

            {loading && !messages.some((m) => m.streaming) && (
              <div className="flex justify-start">
                <div className="flex items-center gap-1.5 rounded-2xl rounded-bl-sm border border-line bg-page px-3.5 py-2.5">
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-fg-4" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-fg-4 [animation-delay:120ms]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-fg-4 [animation-delay:240ms]" />
                </div>
              </div>
            )}
          </div>

          <footer className="border-t border-line p-3">
            <div className="flex items-end gap-2">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={onKeyDown}
                rows={1}
                placeholder={t("chat.placeholder")}
                className="max-h-28 flex-1 resize-none rounded-xl border border-line bg-page px-3 py-2 text-sm text-fg outline-none focus:border-brand focus:ring-2 focus:ring-brand/40 :border-brand :ring-brand/30"
              />
              <button
                type="button"
                onClick={() => send()}
                disabled={loading || !input.trim()}
                className="rounded-xl bg-brand p-2.5 text-white transition-colors hover:bg-brand-hover disabled:cursor-not-allowed disabled:opacity-40 :bg-brand"
                aria-label={t("chat.send")}
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
            {!backendOnline && (
              <p className="mt-2 text-[10px] text-risk-high">
                {t("chat.backendOffline")}
              </p>
            )}
            {assistantOnline === false && (
              <p className="mt-2 text-[10px] text-risk-high">
                {t("chat.aiOffline")}
              </p>
            )}
          </footer>
        </aside>
      )}
    </>
  );
}
