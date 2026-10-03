import { useState } from"react";
import { KeyRound, LogOut, ShieldCheck, Eye, EyeOff } from"lucide-react";
import { translate, LANGUAGES } from"./i18n";
import { changePassword } from"./api";
import { useAuth } from"./AuthContext";

function checkStrength(pw) {
 let score = 0;
 if (pw.length >= 10) score += 1;
 if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) score += 1;
 if (/\d/.test(pw)) score += 1;
 if (/[^A-Za-z0-9]/.test(pw)) score += 1;
 return score;
}

// Strength wording is read from the i18n catalogue (password.strength0..4)
// rather than from a table local to this file, so en/hi parity is enforced by
// backend/tests/test_i18n.py instead of being a second place the two languages
// can drift apart.

export default function ChangePasswordView({ language, setLanguage }) {
 const { token, user, completePasswordChange, logout } = useAuth();
 const [current, setCurrent] = useState("");
 const [next, setNext] = useState("");
 const [confirm, setConfirm] = useState("");
 const [show, setShow] = useState(false);
 const [error, setError] = useState(null);
 const [busy, setBusy] = useState(false);

 const t = (k) => translate(language, k);
 const strength = checkStrength(next);

 const handleSubmit = async (e) => {
 e.preventDefault();
 setError(null);
 if (next !== confirm) {
 setError(t("password.changeMismatch"));
 return;
 }
 if (next === current) {
 setError(t("password.sameAsOld"));
 return;
 }
 setBusy(true);
 try {
 const res = await changePassword(token, current, next);
 completePasswordChange(res.user);
 } catch (err) {
 setError(err.message || t("password.changeFailed"));
 setBusy(false);
 }
 };

 return (
  <div className="relative min-h-screen bg-page text-fg">
  <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(70%_45%_at_50%_0%,rgba(99,102,241,0.14),transparent)]" />
  <div className="relative z-10 flex min-h-screen items-center justify-center px-4 py-12">
  <div className="w-full max-w-md">
  <div className="mb-6 flex items-center justify-between">
  <span className="text-xs font-semibold uppercase tracking-widest text-brand">
  Dhrishti · MoSPI Early Warning
  </span>
  <select
  value={language}
  onChange={(e) => setLanguage(e.target.value)}
  className="rounded-lg border border-line-strong bg-raised px-2 py-1 text-xs text-fg-2 outline-none focus:border-brand"
  aria-label={t("language")}
  >
  {LANGUAGES.map((l) => (
  <option key={l.code} value={l.code}>
  {l.native} ({l.name})
  </option>
  ))}
  </select>
  </div>

  <div className="rounded-2xl border border-line bg-raised p-7 shadow-pop">
  <div className="mb-6 flex items-center gap-3">
  <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-subtle">
  <KeyRound className="h-5 w-5 text-brand" />
  </div>
  <div>
  <h1 className="text-lg font-bold text-fg">{t("password.title")}</h1>
  <p className="text-xs text-fg-3">{user?.email}</p>
  </div>
  </div>

  <div className="mb-6 flex items-start gap-2.5 rounded-xl border border-risk-medium/40 bg-risk-medium-subtle px-3.5 py-3 text-xs leading-relaxed text-fg-2">
  <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-risk-medium" />
  <span>
  {t("password.mustNote")}
  </span>
  </div>

  <form onSubmit={handleSubmit} className="space-y-4">
  <div>
  <label className="mb-1.5 block text-xs font-medium text-fg-3">
  {t("password.current")}
  </label>
  <input
  type={show ?"text" :"password"}
  value={current}
  onChange={(e) => setCurrent(e.target.value)}
  required
  className="w-full rounded-xl border border-line-strong bg-sunken px-3.5 py-2.5 text-sm text-fg outline-none transition-colors focus:border-brand"
  placeholder="••••••••••"
  />
  </div>

  <div>
  <label className="mb-1.5 block text-xs font-medium text-fg-3">
  {t("password.new")}
  </label>
  <div className="relative">
  <input
  type={show ?"text" :"password"}
  value={next}
  onChange={(e) => setNext(e.target.value)}
  required
  className="w-full rounded-xl border border-line-strong bg-sunken px-3.5 py-2.5 pr-10 text-sm text-fg outline-none transition-colors focus:border-brand"
  placeholder="••••••••••"
  />
  <button
  type="button"
  onClick={() => setShow((s) => !s)}
  className="absolute right-3 top-1/2 -translate-y-1/2 text-fg-3 hover:text-fg"
   aria-label={t("password.toggleVisibility")}
  >
  {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
  </button>
  </div>
  <div className="mt-2 flex items-center gap-2">
  <div className="flex h-1.5 flex-1 gap-1">
  {[0, 1, 2, 3].map((i) => (
  <div
  key={i}
  className={`h-full flex-1 rounded-full transition-colors ${
  strength > i
  ? i < 2
  ?"bg-risk-medium"
  :"bg-risk-low"
  :"bg-sunken"
  }`}
  />
  ))}
  </div>
  <span className="w-24 text-right text-[10px] text-fg-3">
   {t(`password.strength${strength}`)}
  </span>
  </div>
  <p className="mt-1.5 text-[11px] text-fg-3">
  {t("passwordHint")}
  </p>
  </div>

  <div>
  <label className="mb-1.5 block text-xs font-medium text-fg-3">
  {t("password.confirm")}
  </label>
  <input
  type={show ?"text" :"password"}
  value={confirm}
  onChange={(e) => setConfirm(e.target.value)}
  required
  className="w-full rounded-xl border border-line-strong bg-sunken px-3.5 py-2.5 text-sm text-fg outline-none transition-colors focus:border-brand"
  placeholder="••••••••••"
  />
  </div>

  {error && (
  <div className="rounded-lg border border-risk-critical/30 bg-risk-critical-subtle px-3 py-2 text-xs text-risk-critical">
  {error}
  </div>
  )}

  <button
  type="submit"
  disabled={busy}
  className="flex w-full items-center justify-center gap-2 rounded-xl bg-brand px-4 py-3 text-sm font-semibold text-brand-fg shadow-lg shadow-brand/20 transition-colors hover:bg-brand-hover disabled:cursor-not-allowed disabled:opacity-50"
  >
  <KeyRound className="h-4 w-4" />
  {busy
  ? (t("password.saving"))
  : (t("password.submit"))}
  </button>

  <button
  type="button"
  onClick={logout}
  className="flex w-full items-center justify-center gap-2 rounded-xl border border-line-strong px-4 py-2.5 text-sm font-medium text-fg-2 transition-colors hover:border-line-heavy hover:bg-hover"
  >

 <LogOut className="h-4 w-4" />
 {t("common.signOut")}
 </button>
 </form>
 </div>
 </div>
 </div>
 </div>
 );
}