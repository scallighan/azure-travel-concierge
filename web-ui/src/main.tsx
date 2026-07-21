import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { config } from "./lib/config";
import "./styles.css";

function Root() {
  // Mock-auth path (default for local/demo): skip Entra entirely.
  if (config.mockAuth) {
    return <App />;
  }
  return <AuthedApp />;
}

// Lazily set up MSAL only when real auth is configured, so demo builds don't
// require an Entra app registration.
function AuthedApp() {
  const [state, setState] = React.useState<{ userId?: string; userName?: string; ready: boolean }>(
    { ready: false },
  );

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      const { msalInstance, loginRequest } = await import("./lib/auth");
      await msalInstance.initialize();
      const resp = await msalInstance.handleRedirectPromise();
      let account = resp?.account ?? msalInstance.getAllAccounts()[0];
      if (!account) {
        await msalInstance.loginRedirect(loginRequest);
        return;
      }
      if (!cancelled) {
        setState({
          userId: account.localAccountId,
          userName: account.name ?? account.username,
          ready: true,
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (!state.ready) return <div className="loading">Signing in…</div>;
  return <App userId={state.userId} userName={state.userName} />;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>,
);
