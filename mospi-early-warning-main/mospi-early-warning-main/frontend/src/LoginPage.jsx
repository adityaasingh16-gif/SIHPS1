import { useMemo, useState } from"react";
import {
 AlertTriangle,
 ArrowLeft,
 Clock3,
 Globe2,
  KeyRound,
  ShieldCheck,
 ShieldX,
 UserRoundPlus,
} from"lucide-react";
import { LANGUAGES, translate } from"./i18n";
import { loginPublicAccount, registerPublicAccount } from"./api";
import { useAuth } from"./AuthContext";
import { DhrishtiMark } from"./components/public/PublicChrome";

function GoogleLogo({ size = 18 }) {
 return (
 <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true">
 <path
 fill="#FFC107"
 d="M43.611 20.083H42V20H24v8h11.303c-1.649 4.657-6.08 8-11.303 8-6.627 0-12-5.373-12-12s5.373-12 12-12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 12.955 4 4 12.955 4 24s8.955 20 20 20 20-8.955 20-20c0-1.341-.138-2.65-.389-3.917z"
 />
 <path
 fill="#FF3D00"
 d="M6.306 14.691l6.571 4.819C14.655 15.108 18.961 12 24 12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 16.318 4 9.656 8.337 6.306 14.691z"
 />
 <path
 fill="#4CAF50"
 d="M24 44c5.166 0 9.86-1.977 13.409-5.192l-6.19-5.238C29.211 35.091 26.715 36 24 36c-5.202 0-9.619-3.317-11.283-7.946l-6.522 5.025C9.505 39.556 16.227 44 24 44z"
 />
 <path
 fill="#1976D2"
 d="M43.611 20.083H42V20H24v8h11.303c-.792 2.237-2.231 4.166-4.087 5.571.001-.001 6.19 5.238 6.19 5.238C36.971 39.205 44 34 44 24c0-1.341-.138-2.65-.389-3.917z"
 />
 </svg>
 );
}

function Divider({ label }) {
 return (
  <div className="my-6 flex items-center gap-3 text-xs uppercase tracking-wider text-fg-3">
  <span className="h-px flex-1 bg-line" />
  <span>{label}</span>
  <span className="h-px flex-1 bg-line" />
  </div>
 );
}

const inputClass ="w-full rounded-xl border border-line-strong bg-sunken px-3.5 py-2.5 text-sm text-fg placeholder:text-fg-3 outline-none transition-colors focus:border-brand focus:ring-2 focus:ring-brand/30";

const fieldLabelClass ="mb-1 block text-xs font-semibold uppercase tracking-wide text-fg-3";


export default function LoginPage({ language, setLanguage, onBackBrowse }) {
 const { setAuthToken, status, bootError, setBootError, logout } = useAuth();
 const [mode, setMode] = useState("signin"); // signin | create | createLogin
 const [form, setForm] = useState({ name:"", email:"", password:"" });
 const [loading, setLoading] = useState(false);
 const [error, setError] = useState(null);

 const t = useMemo(() => (key, vars) => translate(language, key, vars), [language]);

 const goToGoogle = (intent) => {
 window.location.href = `${import.meta.env.VITE_API_URL ||"/api"}/auth/google/login?intent=${intent}`;
 };

 const setAuth = (res) => {
 if (res?.token) {
 setAuthToken(res.token);
 setBootError(null);
 }
 };

 const handleCreateAccount = async (e) => {
 e.preventDefault();
 setLoading(true);
 setError(null);
 try {
 setAuth(await registerPublicAccount(form.name.trim(), form.email.trim(), form.password));
 } catch (err) {
 setError(err.message ||"Could not create account");
 } finally {
 setLoading(false);
 }
 };

 const handleLoginPublic = async (e) => {
 e.preventDefault();
 setLoading(true);
 setError(null);
 try {
 setAuth(await loginPublicAccount(form.email.trim(), form.password));
 } catch (err) {
 setError(err.message ||"Sign in failed");
 } finally {
 setLoading(false);
 }
 };

 if (status ==="pending") {
 return (
 <StatusScreen
 language={language}
 icon={<Clock3 className="h-12 w-12 text-risk-medium" />}
 title={t("login.pending")}
 message={t("login.pendingMsg")}
 tone="amber"
 actionLabel={t("login.logout")}
 onAction={logout}
 />
 );
 }

 if (status ==="revoked") {
 return (
 <StatusScreen
 language={language}
 icon={<ShieldX className="h-12 w-12 text-risk-critical" />}
 title={t("login.revoked")}
 message={t("login.revokedMsg")}
 tone="red"
 actionLabel={t("login.logout")}
 onAction={logout}
 />
 );
 }

 const urlError = bootError || error;
 const errorMsg =
 urlError ==="google_cancelled"
 ? t("login.cancelled")
 : urlError ==="google_failed" ||
 urlError ==="token_exchange_failed" ||
 urlError ==="verification_failed" ||
 urlError ==="email_unverified"
 ? t("login.failed")
 : urlError || null;

 return (
  <div className="relative min-h-screen bg-page text-fg">
  <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(70%_45%_at_50%_0%,rgba(99,102,241,0.14),transparent)]" />

  <header className="relative flex items-center justify-between border-b border-line px-6 py-4">
  <div className="flex items-center gap-3">
  <DhrishtiMark className="h-10" t={t} />
  </div>
  <div className="flex items-center gap-2">
  {onBackBrowse && (
  <button
  type="button"
  onClick={onBackBrowse}
  className="rounded-xl border border-line-strong px-4 py-2 text-sm font-medium text-fg-2 transition-colors hover:border-line-heavy hover:bg-hover hover:text-fg"
  >
  ← {t("login.browse")}
  </button>
  )}
  <label className="flex items-center gap-2 rounded-xl border border-line bg-raised px-3 py-2 text-sm">
  <Globe2 className="h-4 w-4 text-fg-3" />
  <select
  value={language}
  onChange={(e) => setLanguage(e.target.value)}
  className="bg-transparent text-sm text-fg outline-none"
  aria-label={t("language")}
  >
  {LANGUAGES.map((l) => (
  <option key={l.code} value={l.code}>
  {l.native} ({l.name})
  </option>
  ))}
  </select>
  </label>
  </div>
  </header>

  <main className="relative flex min-h-[calc(100vh-73px)] items-center justify-center px-6 py-12">
  <section className="w-full max-w-md rounded-2xl border border-line bg-raised p-8 shadow-pop">
  {mode ==="signin" && (
  <>
  <h2 className="text-xl font-bold text-fg">{t("login.title")}</h2>
  <p className="mt-1 text-sm text-fg-3">{t("login.subtitle")}</p>


 {errorMsg && (
 <div className="mt-4 flex items-start gap-2 rounded-xl border border-risk-critical/30 bg-risk-critical/10 px-3 py-2.5 text-sm text-risk-critical">
 <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
 <span>{errorMsg}</span>
 </div>
 )}

 <form onSubmit={handleLoginPublic} className="mt-5 space-y-4">
 <label className="block text-sm">
 <span className={fieldLabelClass}>{t("login.email")}</span>
 <input
 type="email"
 value={form.email}
 onChange={(e) => setForm({ ...form, email: e.target.value })}
 required
 autoComplete="email"
 className={inputClass}
 />
 </label>
 <label className="block text-sm">
 <span className={fieldLabelClass}>{t("login.password")}</span>
 <input
 type="password"
 value={form.password}
 onChange={(e) => setForm({ ...form, password: e.target.value })}
 required
 autoComplete="current-password"
 className={inputClass}
 />
 </label>
 <button
 type="submit"
 disabled={loading}
  className="flex w-full items-center justify-center gap-2 rounded-xl bg-brand px-4 py-3 text-sm font-semibold text-brand-fg shadow-lg shadow-brand/25 transition-colors hover:bg-brand-hover disabled:cursor-not-allowed disabled:opacity-50"
  >
  <KeyRound className="h-4 w-4" />
  {loading ?"…" : t("login.title")}
  </button>
  </form>

  <Divider label={t("login.or")} />

  <button
  type="button"
  onClick={() => goToGoogle("enterprise")}
  className="flex w-full items-center justify-center gap-3 rounded-xl border border-line bg-sunken px-4 py-3 text-sm font-semibold text-fg transition-colors hover:bg-hover"
  >
  <GoogleLogo />
  {t("login.google")}
  </button>

  <div className="mt-5 flex items-start gap-2.5 rounded-xl border border-line bg-sunken px-3.5 py-3 text-xs leading-relaxed text-fg-3">
  <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-brand" />
  <span>{t("login.enterpriseNote")}</span>
  </div>

  <button
  type="button"
  onClick={() => {
  setMode("create");
  setError(null);
  }}
  className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl border border-line-strong px-4 py-2.5 text-sm font-medium text-fg-2 transition-colors hover:border-line-heavy hover:bg-hover hover:text-fg"
  >
  <UserRoundPlus className="h-4 w-4 text-fg-3" />

 <span>
 {t("login.newHere")} {t("login.createAccount")}
 </span>
 </button>
 </>
 )}

 {mode ==="create" && (
 <>
 <button
 type="button"
 onClick={() => setMode("signin")}
  className="mb-4 inline-flex items-center gap-1.5 text-sm text-fg-3 transition-colors hover:text-fg"
  >
  <ArrowLeft className="h-4 w-4" /> {t("login.back")}
  </button>
  <h2 className="text-xl font-bold text-fg">{t("login.createAccount")}</h2>

  <div className="mt-3 flex items-start gap-2.5 rounded-xl border border-brand-border bg-brand-subtle px-3.5 py-3 text-xs leading-relaxed text-brand-subtle-fg">

 <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-brand" />
 <span>{t("login.publicNote")}</span>
 </div>

 {errorMsg && (
 <div className="mt-4 flex items-start gap-2 rounded-xl border border-risk-critical/30 bg-risk-critical/10 px-3 py-2.5 text-sm text-risk-critical">
 <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
 <span>{errorMsg}</span>
 </div>
 )}

 <form onSubmit={handleCreateAccount} className="mt-5 space-y-4">
 <label className="block text-sm">
 <span className={fieldLabelClass}>{t("login.name")}</span>
 <input
 value={form.name}
 onChange={(e) => setForm({ ...form, name: e.target.value })}
 required
 minLength={2}
 autoComplete="name"
 className={inputClass}
 />
 </label>
 <label className="block text-sm">
 <span className={fieldLabelClass}>{t("login.email")}</span>
 <input
 type="email"
 value={form.email}
 onChange={(e) => setForm({ ...form, email: e.target.value })}
 required
 autoComplete="email"
 className={inputClass}
 />
 </label>
 <label className="block text-sm">
 <span className={fieldLabelClass}>{t("login.password")}</span>
 <input
 type="password"
 value={form.password}
 onChange={(e) => setForm({ ...form, password: e.target.value })}
 required
 minLength={10}
 autoComplete="new-password"
 className={inputClass}
 />
 <span className="mt-1 block text-xs text-fg-3">{t("login.passwordHint")}</span>
 </label>
 <button
 type="submit"
 disabled={loading}
  className="w-full rounded-xl bg-brand px-4 py-3 text-sm font-semibold text-brand-fg shadow-lg shadow-brand/25 transition-colors hover:bg-brand-hover disabled:cursor-not-allowed disabled:opacity-50"
  >
  {loading ?"…" : t("login.signUp")}
  </button>
  </form>

  <Divider label={t("login.or")} />

  <button
  type="button"
  onClick={() => goToGoogle("public")}
  className="flex w-full items-center justify-center gap-3 rounded-xl border border-line bg-sunken px-4 py-3 text-sm font-semibold text-fg transition-colors hover:bg-hover"
  >
  <GoogleLogo />
  {t("login.continueGoogle")}
  </button>

  <button
  type="button"
  onClick={() => {
  setMode("createLogin");
  setError(null);
  }}
  className="mt-5 w-full text-center text-xs text-fg-3 transition-colors hover:text-fg"
  >

 {t("login.haveAccount")}
 </button>
 </>
 )}

 {mode ==="createLogin" && (
 <>
 <button
 type="button"
 onClick={() => setMode("create")}
  className="mb-4 inline-flex items-center gap-1.5 text-sm text-fg-3 transition-colors hover:text-fg"
  >
  <ArrowLeft className="h-4 w-4" /> {t("login.createNew")}
  </button>
  <h2 className="flex items-center gap-2 text-xl font-bold text-fg">
  <KeyRound className="h-5 w-5 text-brand" /> {t("login.signInEmail")}
  </h2>


 {errorMsg && (
 <div className="mt-4 flex items-start gap-2 rounded-xl border border-risk-critical/30 bg-risk-critical/10 px-3 py-2.5 text-sm text-risk-critical">
 <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
 <span>{errorMsg}</span>
 </div>
 )}

 <form onSubmit={handleLoginPublic} className="mt-5 space-y-4">
 <label className="block text-sm">
 <span className={fieldLabelClass}>{t("login.email")}</span>
 <input
 type="email"
 value={form.email}
 onChange={(e) => setForm({ ...form, email: e.target.value })}
 required
 autoComplete="email"
 className={inputClass}
 />
 </label>
 <label className="block text-sm">
 <span className={fieldLabelClass}>{t("login.password")}</span>
 <input
 type="password"
 value={form.password}
 onChange={(e) => setForm({ ...form, password: e.target.value })}
 required
 autoComplete="current-password"
 className={inputClass}
 />
 </label>
 <button
 type="submit"
 disabled={loading}
  className="w-full rounded-xl bg-brand px-4 py-3 text-sm font-semibold text-brand-fg shadow-lg shadow-brand/25 transition-colors hover:bg-brand-hover disabled:cursor-not-allowed disabled:opacity-50"
  >
  {loading ?"…" : t("login.title")}
  </button>
  </form>
  </>
  )}
  </section>
  </main>
  </div>
  );
}

function StatusScreen({ _language, icon, title, message, tone, actionLabel, onAction }) {
  const ring =
  tone ==="amber"
  ?"border-risk-medium/40"
  :"border-risk-critical/40";
  const iconTone =
  tone ==="amber" ? "text-risk-medium" : "text-risk-critical";
  return (
  <div className="flex min-h-screen items-center justify-center bg-page px-4 text-fg">
  <div className={`w-full max-w-md rounded-2xl border bg-raised p-8 text-center shadow-pop ${ring}`}>
  <div className="mx-auto mb-4 flex h-20 w-20 items-center justify-center rounded-full bg-sunken">
  {icon}
  </div>
  <h1 className={`text-2xl font-bold ${iconTone}`}>{title}</h1>
  <p className="mt-3 text-sm leading-relaxed text-fg-2">{message}</p>
  <button
  type="button"
  onClick={onAction}
  className="mt-6 rounded-xl bg-brand px-5 py-2.5 text-sm font-semibold text-brand-fg transition-colors hover:bg-brand-hover"
  >
  {actionLabel}
  </button>
  </div>
  </div>
  );
}
