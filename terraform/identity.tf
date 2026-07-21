# ---------------------------------------------------------------------------
# Workload managed identity (shared by the agent runtime + MCP servers)
# ---------------------------------------------------------------------------
resource "azurerm_user_assigned_identity" "workload" {
  name                = "uai-workload-${local.func_name}"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  tags                = local.tags
}

# Call Foundry models + agent service
resource "azurerm_role_assignment" "workload_foundry_user" {
  scope                = azurerm_resource_group.this.id
  role_definition_name = "Foundry User"
  principal_id         = azurerm_user_assigned_identity.workload.principal_id
}

# Read/write blobs (document staging)
resource "azurerm_role_assignment" "workload_storage" {
  scope                = azurerm_storage_account.this.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.workload.principal_id
}

# Read secrets (VIC mock creds, external API keys)
resource "azurerm_role_assignment" "workload_kv" {
  scope                = azurerm_key_vault.this.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.workload.principal_id
}

# Query AI Search indexes
resource "azurerm_role_assignment" "workload_search_query" {
  scope                = local.search_id
  role_definition_name = "Search Index Data Reader"
  principal_id         = azurerm_user_assigned_identity.workload.principal_id
}
