# ---------------------------------------------------------------------------
# Azure Cosmos DB (NoSQL) - replaces DynamoDB
#   Containers: userProfiles, cart, itinerary, orders
# ---------------------------------------------------------------------------
resource "azurerm_cosmosdb_account" "this" {
  name                = "cosmos${local.func_name}"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  offer_type          = "Standard"
  kind                = "GlobalDocumentDB"

  # Entra ID (RBAC) auth for data plane; disable key auth
  local_authentication_disabled = true

  consistency_policy {
    consistency_level = "Session"
  }

  geo_location {
    location          = azurerm_resource_group.this.location
    failover_priority = 0
  }

  capabilities {
    name = "EnableServerless"
  }

  tags = local.tags
}

resource "azurerm_cosmosdb_sql_database" "this" {
  name                = "concierge"
  resource_group_name = azurerm_resource_group.this.name
  account_name        = azurerm_cosmosdb_account.this.name
}

locals {
  cosmos_containers = {
    userProfiles = "/userId"
    cart         = "/userId"
    itinerary    = "/userId"
    orders       = "/userId"
  }
}

resource "azurerm_cosmosdb_sql_container" "containers" {
  for_each = local.cosmos_containers

  name                  = each.key
  resource_group_name   = azurerm_resource_group.this.name
  account_name          = azurerm_cosmosdb_account.this.name
  database_name         = azurerm_cosmosdb_sql_database.this.name
  partition_key_paths   = [each.value]
  partition_key_version = 2
}

# Cosmos DB built-in data-plane RBAC role (Data Contributor)
resource "azurerm_cosmosdb_sql_role_assignment" "workload" {
  resource_group_name = azurerm_resource_group.this.name
  account_name        = azurerm_cosmosdb_account.this.name
  role_definition_id  = "${azurerm_cosmosdb_account.this.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002"
  principal_id        = azurerm_user_assigned_identity.workload.principal_id
  scope               = azurerm_cosmosdb_account.this.id
}

# Allow the deploying user to seed demo data
resource "azurerm_cosmosdb_sql_role_assignment" "current_user" {
  resource_group_name = azurerm_resource_group.this.name
  account_name        = azurerm_cosmosdb_account.this.name
  role_definition_id  = "${azurerm_cosmosdb_account.this.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002"
  principal_id        = data.azurerm_client_config.current.object_id
  scope               = azurerm_cosmosdb_account.this.id
}
