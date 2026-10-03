import { createContext, useCallback, useContext, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, Info, X } from "lucide-react";

export { ToastProvider, useToasts };

/**
 * Premium toast system: calm entry, readable lifetime with a drain bar,
 * manual dismissal, and a cap so notifications never stack into a wall.
 *
 * `notify(message, tone)` — tone is success | warning | error | info.
 * Copy stays human ("Project list refreshed") rather than raw backend text.
 */
const ToastContext = createContext(() => {});

function useToasts() {
  return useContext(ToastContext);
}

const TONE = {
  success: { icon: CheckCircle2, bar: "bg-risk-low", text: "text-risk-low" },
  warning: { icon: AlertTriangle, bar: "bg-risk-medium", text: "text-risk-medium" },
  error: { icon: AlertTriangle, bar: "bg-risk-critical", text: "text-risk-critical" },
  info: { icon: Info, bar: "bg-brand", text: "text-brand" },
};

let nextId = 0;

function ToastProvider({ children }) {
  const [items, setItems] = useState([]);
  const timers = useRef(new Map());

  const dismiss = useCallback((id) => {
    setItems((prev) => prev.filter((item) => item.id !== id));
    const handle = timers.current.get(id);
    if (handle) {
      clearTimeout(handle);
      timers.current.delete(id);
    }
  }, []);

  const notify = useCallback(
    (message, tone = "info") => {
      const id = ++nextId;
      setItems((prev) => [...prev.slice(-2), { id, message, tone }]);
      timers.current.set(
        id,
        setTimeout(() => dismiss(id), 4600)
      );
    },
    [dismiss]
  );

  return (
    <ToastContext.Provider value={notify}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed bottom-5 right-5 z-[200] flex w-[min(92vw,360px)] flex-col gap-2"
      >
        {items.map((item) => (
          <Toast key={item.id} item={item} onDismiss={() => dismiss(item.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function Toast({ item, onDismiss }) {
  const tone = TONE[item.tone] || TONE.info;
  const Icon = tone.icon;
  return (
    <div className="toast-enter pointer-events-auto overflow-hidden rounded-xl border border-line bg-overlay shadow-pop">
      <div className="flex items-start gap-2.5 px-3.5 py-3">
        <Icon size={16} className={`mt-0.5 shrink-0 ${tone.text}`} aria-hidden="true" />
        <p className="min-w-0 flex-1 text-[13px] leading-snug text-fg">{item.message}</p>
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss notification"
          className="pressable shrink-0 rounded-md p-1 text-fg-3 hover:bg-hover hover:text-fg"
        >
          <X size={14} />
        </button>
      </div>
      <div className="h-0.5 w-full bg-sunken">
        <div className={`toast-bar h-full ${tone.bar}`} />
      </div>
    </div>
  );
}
