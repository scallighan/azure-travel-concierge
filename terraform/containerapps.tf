# ---------------------------------------------------------------------------
# Container Apps environment
# ---------------------------------------------------------------------------
resource "azurerm_container_app_environment" "this" {
  name                       = "ace-${local.func_name}"
  location                   = azurerm_resource_group.this.location
  resource_group_name        = azurerm_resource_group.this.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.this.id
  infrastructure_subnet_id   = azurerm_subnet.aca_infra.id

  workload_profile {
    name                  = "Consumption"
    workload_profile_type = "Consumption"
  }

  tags = local.tags
  lifecycle {
    ignore_changes = [
      infrastructure_resource_group_name
    ]
  }
}

locals {
  image_base = "ghcr.io/${var.gh_repo}"

  # Common env vars shared by every container app
  common_env = {
    AZURE_CLIENT_ID                       = azurerm_user_assigned_identity.workload.client_id
    APPLICATIONINSIGHTS_CONNECTION_STRING = azurerm_application_insights.this.connection_string
  }

  # Internal FQDNs the agent uses to reach the MCP servers (MCP streamable-http).
  # Internal-ingress apps are addressable at "<app>.internal.<default_domain>",
  # so use each app's actual ingress FQDN rather than composing it by hand.
  travel_mcp_url   = "https://${azurerm_container_app.travel_mcp.ingress[0].fqdn}/mcp"
  cart_mcp_url     = "https://${azurerm_container_app.cart_mcp.ingress[0].fqdn}/mcp"
  vic_mcp_url      = "https://${azurerm_container_app.vic_mock.ingress[0].fqdn}/mcp"
  merchant_mcp_url = "https://${azurerm_container_app.merchant_mock.ingress[0].fqdn}/mcp"
}

# ---------------------------------------------------------------------------
# Mock VIC MCP server (internal)
# ---------------------------------------------------------------------------
resource "azurerm_container_app" "vic_mock" {
  name                         = "aca-vic-mock-${local.func_name}"
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = azurerm_resource_group.this.name
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"

  template {
    container {
      name   = "vic-mock"
      image  = "${local.image_base}/vic-mock-mcp:${var.container_image_tag}"
      cpu    = 0.25
      memory = "0.5Gi"

      # AZURE_CLIENT_ID (from common_env) tells DefaultAzureCredential which
      # user-assigned identity to use — required for the Cosmos card store below.
      dynamic "env" {
        for_each = local.common_env
        content {
          name  = env.key
          value = env.value
        }
      }

      env {
        name  = "PORT"
        value = "8080"
      }

      # Durable card store — mirror enrolled cards to Cosmos so they survive a
      # single-replica restart. vic-mock uses the shared workload identity,
      # which already has Cosmos Data Contributor.
      env {
        name  = "COSMOS_ENDPOINT"
        value = azurerm_cosmosdb_account.this.endpoint
      }
      env {
        name  = "COSMOS_DATABASE"
        value = azurerm_cosmosdb_sql_database.this.name
      }
      env {
        name  = "VIC_CARDS_CONTAINER"
        value = "vicCards"
      }
    }
    min_replicas = 1
    max_replicas = 1
  }

  ingress {
    external_enabled        = true
    client_certificate_mode = "ignore"
    target_port             = 8080
    transport               = "auto"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.workload.id]
  }

  tags = local.tags
}

# ---------------------------------------------------------------------------
# Mock merchant / acquirer MCP server (internal) — settles VIC network-token
# credentials and creates the merchant order (the party separate from Visa).
# ---------------------------------------------------------------------------
resource "azurerm_container_app" "merchant_mock" {
  name                         = "aca-merchant-mock-${local.func_name}"
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = azurerm_resource_group.this.name
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"

  template {
    container {
      name   = "merchant-mock"
      image  = "${local.image_base}/merchant-mock-mcp:${var.container_image_tag}"
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name  = "PORT"
        value = "8080"
      }
    }
    min_replicas = 1
    max_replicas = 1
  }

  ingress {
    external_enabled = false
    target_port      = 8080
    transport        = "auto"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.workload.id]
  }

  tags = local.tags
}

# ---------------------------------------------------------------------------
# Travel tools MCP server (internal)
# ---------------------------------------------------------------------------
resource "azurerm_container_app" "travel_mcp" {
  name                         = "aca-travel-mcp-${local.func_name}"
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = azurerm_resource_group.this.name
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"

  template {
    container {
      name   = "travel-mcp"
      image  = "${local.image_base}/travel-tools-mcp:${var.container_image_tag}"
      cpu    = 0.5
      memory = "1Gi"

      dynamic "env" {
        for_each = local.common_env
        content {
          name  = env.key
          value = env.value
        }
      }

      env {
        name  = "PORT"
        value = "8080"
      }
      # When unset, travel tools return deterministic mock data (no external API keys required)
      env {
        name  = "KEY_VAULT_URI"
        value = azurerm_key_vault.this.vault_uri
      }
    }
    min_replicas = 1
    max_replicas = 3
  }

  ingress {
    external_enabled = false
    target_port      = 8080
    transport        = "auto"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.workload.id]
  }

  tags = local.tags
}

# ---------------------------------------------------------------------------
# Cart tools MCP server (internal)
# ---------------------------------------------------------------------------
resource "azurerm_container_app" "cart_mcp" {
  name                         = "aca-cart-mcp-${local.func_name}"
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = azurerm_resource_group.this.name
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"

  template {
    container {
      name   = "cart-mcp"
      image  = "${local.image_base}/cart-tools-mcp:${var.container_image_tag}"
      cpu    = 0.5
      memory = "1Gi"

      dynamic "env" {
        for_each = local.common_env
        content {
          name  = env.key
          value = env.value
        }
      }

      env {
        name  = "PORT"
        value = "8080"
      }
      env {
        name  = "COSMOS_ENDPOINT"
        value = azurerm_cosmosdb_account.this.endpoint
      }
      env {
        name  = "COSMOS_DATABASE"
        value = azurerm_cosmosdb_sql_database.this.name
      }
      env {
        name  = "VIC_MCP_URL"
        value = local.vic_mcp_url
      }
      env {
        name  = "MERCHANT_MCP_URL"
        value = local.merchant_mcp_url
      }
      env {
        name  = "ENABLE_VIC_INTEGRATION"
        value = tostring(var.enable_vic_integration)
      }
    }
    min_replicas = 1
    max_replicas = 1
  }

  ingress {
    external_enabled = false
    target_port      = 8080
    transport        = "auto"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.workload.id]
  }

  tags = local.tags
}

# ---------------------------------------------------------------------------
# Concierge supervisor agent (external - the web UI talks to this)
# ---------------------------------------------------------------------------
resource "azurerm_container_app" "agent" {
  name                         = "aca-agent-${local.func_name}"
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = azurerm_resource_group.this.name
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"

  template {
    container {
      name   = "concierge-agent"
      image  = "${local.image_base}/concierge-agent:${var.container_image_tag}"
      cpu    = 1.0
      memory = "2Gi"

      dynamic "env" {
        for_each = local.common_env
        content {
          name  = env.key
          value = env.value
        }
      }

      env {
        name  = "PORT"
        value = "8080"
      }
      env {
        name  = "AZURE_AI_PROJECT_ENDPOINT"
        value = local.foundry_endpoint
      }
      env {
        name  = "AZURE_AI_MODEL_DEPLOYMENT_NAME"
        value = var.chat_model
      }
      env {
        name  = "COSMOS_ENDPOINT"
        value = azurerm_cosmosdb_account.this.endpoint
      }
      env {
        name  = "COSMOS_DATABASE"
        value = azurerm_cosmosdb_sql_database.this.name
      }
      env {
        name  = "COSMOS_ITINERARY_CONTAINER"
        value = "itinerary"
      }
      env {
        name  = "COSMOS_HISTORY_CONTAINER"
        value = "chatHistory"
      }
      env {
        name  = "TRAVEL_MCP_URL"
        value = local.travel_mcp_url
      }
      env {
        name  = "CART_MCP_URL"
        value = local.cart_mcp_url
      }
      env {
        name  = "PAYMENTS_AGENT_NAME"
        value = var.payments_agent_name
      }
      env {
        name  = "VIC_MCP_CONNECTION"
        value = azapi_resource.vic_mock_connection.name
      }
      env {
        name  = "WEBIQ_MCP_URL"
        value = local.webiq_mcp_url
      }
      env {
        name        = "WEBIQ_API_KEY"
        secret_name = "webiq-api-key"
      }
      env {
        name  = "FOUNDRY_TOOLBOX_NAME"
        value = var.foundry_toolbox_name
      }
      env {
        name  = "FOUNDRY_TOOLBOX_VERSION"
        value = var.foundry_toolbox_version
      }
      env {
        name  = "SEARCH_ENDPOINT"
        value = local.search_endpoint
      }
      env {
        name  = "SEARCH_INDEX_NAME"
        value = var.search_index_name
      }
      env {
        name  = "ENABLE_VIC_INTEGRATION"
        value = tostring(var.enable_vic_integration)
      }
    }

    http_scale_rule {
      name                = "http-1"
      concurrent_requests = "50"
    }

    min_replicas = 1
    max_replicas = 1
  }

  ingress {
    allow_insecure_connections = false
    external_enabled           = true
    target_port                = 8080
    transport                  = "auto"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.workload.id]
  }

  secret {
    name  = "webiq-api-key"
    value = local.webiq_api_key
  }

  tags = local.tags
}
