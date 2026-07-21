import { PublicClientApplication, Configuration } from "@azure/msal-browser";
import { config } from "./config";

const msalConfig: Configuration = {
  auth: {
    clientId: config.entraClientId,
    authority: `https://login.microsoftonline.com/${config.entraTenantId}`,
    redirectUri: window.location.origin + "/",
  },
  cache: { cacheLocation: "sessionStorage" },
};

export const msalInstance = new PublicClientApplication(msalConfig);
export const loginRequest = { scopes: ["User.Read"] };
