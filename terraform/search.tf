# ---------------------------------------------------------------------------
# Azure AI Search - knowledge base (create a new service, or reuse an existing
# one to save cost/capacity via var.use_existing_search).
# ---------------------------------------------------------------------------
locals {
  search_rg = var.existing_search_resource_group_name != "" ? var.existing_search_resource_group_name : azurerm_resource_group.this.name

  search_id       = var.use_existing_search ? data.azurerm_search_service.existing[0].id : azurerm_search_service.this[0].id
  search_name     = var.use_existing_search ? var.existing_search_service_name : azurerm_search_service.this[0].name
  search_endpoint = "https://${local.search_name}.search.windows.net"
}

resource "azurerm_search_service" "this" {
  count = var.use_existing_search ? 0 : 1

  name                = "ais${local.func_name}"
  resource_group_name = azurerm_resource_group.this.name
  location            = "westus"
  sku                 = "basic"

  local_authentication_enabled = false
  semantic_search_sku          = "free"

  identity {
    type = "SystemAssigned"
  }

  tags = local.tags
}

# Reuse an existing AI Search service instead of provisioning a new one.
data "azurerm_search_service" "existing" {
  count               = var.use_existing_search ? 1 : 0
  name                = var.existing_search_service_name
  resource_group_name = local.search_rg
}

moved {
  from = azurerm_search_service.this
  to   = azurerm_search_service.this[0]
}

# Search reads documents from the staging storage account (new service only —
# an existing service is assumed to be configured already).
resource "azurerm_role_assignment" "search_storage" {
  count                = var.use_existing_search ? 0 : 1
  scope                = azurerm_storage_account.this.id
  role_definition_name = "Storage Blob Data Reader"
  principal_id         = azurerm_search_service.this[0].identity[0].principal_id
}

moved {
  from = azurerm_role_assignment.search_storage
  to   = azurerm_role_assignment.search_storage[0]
}

# Search calls the Foundry embedding model for integrated vectorization
# (new service only).
resource "azurerm_role_assignment" "search_foundry" {
  count                = var.use_existing_search ? 0 : 1
  scope                = azapi_resource.ai_foundry.id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azurerm_search_service.this[0].identity[0].principal_id
}

moved {
  from = azurerm_role_assignment.search_foundry
  to   = azurerm_role_assignment.search_foundry[0]
}

# The deploying principal manages indexes/indexers during ingestion (works for
# both a newly created and a reused search service).
resource "azurerm_role_assignment" "current_user_search_contributor" {
  scope                = local.search_id
  role_definition_name = "Search Service Contributor"
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "azurerm_role_assignment" "current_user_search_data" {
  scope                = local.search_id
  role_definition_name = "Search Index Data Contributor"
  principal_id         = data.azurerm_client_config.current.object_id
}
