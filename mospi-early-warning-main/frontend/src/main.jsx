import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "./index.css";
import App from "./App.jsx";
import { AuthProvider } from "./AuthContext.jsx";
import { PreferencesProvider } from "./hooks/usePreferences.jsx";
import { ToastProvider } from "./components/ui/Toasts.jsx";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <PreferencesProvider>
      <AuthProvider>
        {/* The router sits above the session gate so anonymous visitors can
            reach the read-only feature routes, not just the portal home. */}
        <BrowserRouter>
          <ToastProvider>
            <App />
          </ToastProvider>
        </BrowserRouter>
      </AuthProvider>
    </PreferencesProvider>
  </StrictMode>,
);
