# ---------------------------------------------------------------------------
# Entra ID app registration for the web UI (SPA sign-in via MSAL)
#   Replaces AWS Cognito user pool
# ---------------------------------------------------------------------------
resource "azuread_application" "webui" {
  display_name     = "travel-concierge-${local.func_name}"
  owners           = [data.azurerm_client_config.current.object_id]
  sign_in_audience = "AzureADMyOrg"

  single_page_application {
    redirect_uris = [
      "http://localhost:5173/",
      "https://${azurerm_static_web_app.this.default_host_name}/",
    ]
  }

  required_resource_access {
    resource_app_id = "00000003-0000-0000-c000-000000000000" # Microsoft Graph
    resource_access {
      id   = "e1fe6dd8-ba31-4d61-89e7-88639da4683d" # User.Read
      type = "Scope"
    }
  }

  lifecycle {
    ignore_changes = [single_page_application[0].redirect_uris]
  }
}

resource "azuread_service_principal" "webui" {
  client_id = azuread_application.webui.client_id
  owners    = [data.azurerm_client_config.current.object_id]
}
