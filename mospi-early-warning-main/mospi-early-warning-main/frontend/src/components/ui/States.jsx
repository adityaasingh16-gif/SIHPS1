import { useT } from "../../hooks/useT";

export { EmptyState, ErrorState };

/**
 * Empty and error states.
 *
 * These existed as ad-hoc blocks in five or six places, which is why the app
 * reads as unfinished whenever a filter returns nothing: the user is told
 * nothing and offered no way forward. The point of a shared primitive is that
 * it can *name the cause* and offer the reset, not just say "no data".
 *
 * Both are role="status" / role="alert" so screen readers announce the
 * change, and both avoid colour as the only signal - the icon and the copy
 * carry the meaning too.
 */

function EmptyState({
  icon: Icon,
  title,
  description,
  actionLabel,
  onAction,
  hint,
  tone = "violet",
  className = "",
}) {
  // Icon well tints with the tone so an empty state still belongs to the
  // surface it sits on instead of floating as a grey box.
  const TONES = {
    violet: "bg-cat-1-subtle text-cat-1-subtle-fg",
    fuchsia: "bg-cat-2-subtle text-cat-2-subtle-fg",
    cyan: "bg-cat-3-subtle text-cat-3-subtle-fg",
    emerald: "bg-cat-4-subtle text-cat-4-subtle-fg",
    amber: "bg-cat-5-subtle text-cat-5-subtle-fg",
    rose: "bg-cat-6-subtle text-cat-6-subtle-fg",
  };
  const well = TONES[tone] || TONES.violet;

  return (
    <div
      role="status"
      className={`flex flex-col items-center justify-center rounded-2xl border border-dashed border-line-strong bg-raised/60 px-6 py-12 text-center ${className}`}
    >
      {Icon && (
        <div
          className={`mb-4 flex h-12 w-12 items-center justify-center rounded-2xl ${well}`}
          aria-hidden="true"
        >
          <Icon size={22} />
        </div>
      )}

      <h3 className="text-sm font-semibold text-fg">{title}</h3>

      {description && (
        <p className="mt-1.5 max-w-sm text-xs leading-5 text-fg-3">
          {description}
        </p>
      )}

      {actionLabel && onAction && (
        <button
          type="button"
          onClick={onAction}
          className="mt-5 inline-flex items-center gap-2 rounded-lg border border-brand-border bg-brand-subtle px-3.5 py-2 text-xs font-semibold text-brand-subtle-fg transition hover:bg-brand hover:text-brand-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
        >
          {actionLabel}
        </button>
      )}

      {hint && <p className="mt-3 text-[11px] text-fg-4">{hint}</p>}
    </div>
  );
}

function ErrorState({
  icon: Icon,
  title,
  description,
  onRetry,
  retryLabel,
  tone = "critical",
  className = "",
}) {
  const t = useT();
  const TONES = {
    critical: {
      wrap: "border-risk-critical bg-risk-critical-subtle",
      text: "text-risk-critical",
      button:
        "border-risk-critical/40 text-risk-critical hover:bg-risk-critical hover:text-brand-fg",
    },
    medium: {
      wrap: "border-risk-medium bg-risk-medium-subtle",
      text: "text-risk-medium",
      button:
        "border-risk-medium/40 text-risk-medium hover:bg-risk-medium hover:text-brand-fg",
    },
  };
  // `tr` is the translator and `tone` the palette: naming the palette `t` is
  // what collided with the `t()` translator, so they are kept distinct here.
  const tr = useT();
  const toneMap = TONES[tone] || TONES.critical;
  const Glyph = Icon;

  return (
    <div
      role="alert"
      className={`flex flex-wrap items-start gap-3 rounded-2xl border p-4 ${toneMap.wrap} ${className}`}
    >
      {Glyph && (
        <Glyph size={18} className={`mt-0.5 shrink-0 ${toneMap.text}`} aria-hidden="true" />
      )}

      <div className="min-w-0 flex-1">
        <p className={`text-sm font-semibold ${toneMap.text}`}>
          {title ?? tr("errorState.defaultTitle")}
        </p>
        {description && (
          <p className={`mt-1 text-xs leading-5 ${toneMap.text} opacity-90`}>
            {description}
          </p>
        )}
      </div>

      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className={`shrink-0 rounded-lg border bg-transparent px-3 py-1.5 text-xs font-semibold transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${toneMap.button}`}
        >
          {retryLabel ?? tr("errorState.retry")}
        </button>
      )}
    </div>
  );
}
