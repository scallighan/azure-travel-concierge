// Runtime configuration sourced from Vite env vars (see .env.example).
export const config = {
  agentUrl: import.meta.env.VITE_AGENT_URL ?? "http://localhost:8080",
  entraClientId: import.meta.env.VITE_ENTRA_CLIENT_ID ?? "",
  entraTenantId: import.meta.env.VITE_ENTRA_TENANT_ID ?? "",
  enableVic: (import.meta.env.VITE_ENABLE_VIC ?? "true") === "true",
  // When true (or when no Entra client id is configured) the UI skips sign-in.
  mockAuth:
    (import.meta.env.VITE_MOCK_AUTH ?? "") === "true" ||
    !import.meta.env.VITE_ENTRA_CLIENT_ID,
};

export const DEMO_USER_ID = import.meta.env.VITE_DEMO_USER_ID ?? "demo-user";
