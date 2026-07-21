output "resource_group_name" {
  value = azurerm_resource_group.this.name
}

output "foundry_project_endpoint" {
  value = local.foundry_endpoint
}

output "chat_model_deployment" {
  value = var.chat_model
}

output "agent_url" {
  description = "Public HTTPS endpoint of the concierge agent (web UI backend)."
  value       = "https://${azurerm_container_app.agent.ingress[0].fqdn}"
}

output "cosmos_endpoint" {
  value = azurerm_cosmosdb_account.this.endpoint
}

output "cosmos_database" {
  value = azurerm_cosmosdb_sql_database.this.name
}

output "search_endpoint" {
  value = local.search_endpoint
}

output "search_index_name" {
  value = var.search_index_name
}

output "storage_account_name" {
  value = azurerm_storage_account.this.name
}

output "visa_docs_container" {
  value = azurerm_storage_container.visa_docs.name
}

output "key_vault_uri" {
  value = azurerm_key_vault.this.vault_uri
}

output "workload_identity_client_id" {
  value = azurerm_user_assigned_identity.workload.client_id
}

output "static_web_app_hostname" {
  value = "https://${azurerm_static_web_app.this.default_host_name}"
}

output "static_web_app_api_key" {
  description = "Deployment token used by the SWA CLI / GitHub Action."
  value       = azurerm_static_web_app.this.api_key
  sensitive   = true
}

# Values the SPA needs at build time (see web-ui/.env.example)
output "webui_entra_client_id" {
  value = azuread_application.webui.client_id
}

output "webui_entra_tenant_id" {
  value = data.azurerm_client_config.current.tenant_id
}

output "enable_vic_integration" {
  description = "Whether the (mock) VIC payment integration is enabled in the agent and UI."
  value       = var.enable_vic_integration
}
