# ---------------------------------------------------------------------------
# Azure AI Foundry account (Cognitive Services / AIServices kind)
# ---------------------------------------------------------------------------
resource "azapi_resource" "ai_foundry" {
  type                      = "Microsoft.CognitiveServices/accounts@2025-06-01"
  name                      = local.foundry_name
  parent_id                 = azurerm_resource_group.this.id
  location                  = azurerm_resource_group.this.location
  schema_validation_enabled = false

  body = {
    kind = "AIServices"
    sku = {
      name = "S0"
    }
    identity = {
      type = "SystemAssigned"
    }
    properties = {
      # Entra ID only (no local API keys) - agents authenticate with managed identity
      disableLocalAuth       = true
      allowProjectManagement = true
      customSubDomainName    = local.foundry_name
      publicNetworkAccess    = "Enabled"
      networkAcls = {
        defaultAction = "Allow"
      }
    }
  }

  response_export_values = [
    "identity.principalId"
  ]

  tags = local.tags
}

# ---------------------------------------------------------------------------
# Foundry project - hosts the concierge agents and threads
# ---------------------------------------------------------------------------
resource "azapi_resource" "ai_foundry_project" {
  depends_on = [azapi_resource.ai_foundry]

  type                      = "Microsoft.CognitiveServices/accounts/projects@2025-06-01"
  name                      = local.foundry_project
  parent_id                 = azapi_resource.ai_foundry.id
  location                  = azurerm_resource_group.this.location
  schema_validation_enabled = false

  body = {
    sku = {
      name = "S0"
    }
    identity = {
      type = "SystemAssigned"
    }
    properties = {
      displayName = "Travel Concierge"
      description = "Multi-agent travel concierge (supervisor + travel + cart sub-agents)."
    }
  }

  response_export_values = [
    "identity.principalId",
    "properties.internalId"
  ]
}

# ---------------------------------------------------------------------------
# Model deployments (chat + embeddings)
# ---------------------------------------------------------------------------
resource "azapi_resource" "chat_deployment" {
  type                      = "Microsoft.CognitiveServices/accounts/deployments@2024-10-01"
  name                      = var.chat_model
  parent_id                 = azapi_resource.ai_foundry.id
  schema_validation_enabled = false

  body = {
    sku = {
      name     = "GlobalStandard"
      capacity = var.chat_model_capacity
    }
    properties = {
      model = {
        format  = "OpenAI"
        name    = var.chat_model
        version = var.chat_model_version
      }
      versionUpgradeOption = "OnceNewDefaultVersionAvailable"
    }
  }
}

# ---------------------------------------------------------------------------
# Application Insights connection (enables agent/trace observability in the
# Foundry portal). Foundry reads GenAI traces from the connected App Insights
# resource; the connection is created at BOTH the account and project level
# (only one App Insights may be connected to a project at a time).
# ---------------------------------------------------------------------------
resource "azapi_resource" "foundry_appinsights_connection" {
  type                      = "Microsoft.CognitiveServices/accounts/connections@2025-06-01"
  name                      = "${local.foundry_name}-appinsights"
  parent_id                 = azapi_resource.ai_foundry.id
  schema_validation_enabled = false

  body = {
    properties = {
      category      = "AppInsights"
      target        = azurerm_application_insights.this.id
      authType      = "ApiKey"
      isSharedToAll = true
      credentials = {
        key = azurerm_application_insights.this.connection_string
      }
      metadata = {
        ApiType    = "Azure"
        ResourceId = azurerm_application_insights.this.id
      }
    }
  }
}

resource "azapi_resource" "project_appinsights_connection" {
  type                      = "Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01"
  name                      = "appi-connection"
  parent_id                 = azapi_resource.ai_foundry_project.id
  schema_validation_enabled = false

  body = {
    properties = {
      category      = "AppInsights"
      target        = azurerm_application_insights.this.id
      authType      = "ApiKey"
      isSharedToAll = false
      credentials = {
        key = azurerm_application_insights.this.connection_string
      }
      metadata = {
        ApiType    = "Azure"
        ResourceId = azurerm_application_insights.this.id
      }
    }
  }
}

# Let the Foundry project's managed identity read the traces it emits so the
# portal's tracing/evaluation views can render GenAI content.
# Log Analytics Reader + Monitoring Data Reader (the latter is required to read
# GenAI trace content).
resource "azurerm_role_assignment" "project_appinsights_log_reader" {
  scope                = azurerm_application_insights.this.id
  role_definition_name = "Log Analytics Reader"
  principal_id         = azapi_resource.ai_foundry_project.output.identity.principalId
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "project_appinsights_monitoring_reader" {
  scope                = azurerm_application_insights.this.id
  role_definition_name = "Monitoring Data Reader"
  principal_id         = azapi_resource.ai_foundry_project.output.identity.principalId
  principal_type       = "ServicePrincipal"
}

# ---------------------------------------------------------------------------
# Mock VIC payments connection (RemoteTool / custom MCP). The Foundry-hosted
# payments agent references this connection by name (project_connection_id) so
# all payment traffic flows through the mock VIC MCP server rather than the
# shared Toolbox. authType is None because the mock service is anonymous.
# ---------------------------------------------------------------------------
resource "azapi_resource" "vic_mock_connection" {
  type                      = "Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01"
  name                      = "vic-mock"
  parent_id                 = azapi_resource.ai_foundry_project.id
  schema_validation_enabled = false

  body = {
    properties = {
      category      = "RemoteTool"
      target        = local.vic_mcp_url
      authType      = "None"
      group         = "GenericProtocol"
      isSharedToAll = false
      metadata = {
        type = "custom_MCP"
      }
    }
  }
}

# ---------------------------------------------------------------------------
# WebIQ web-intelligence connection (RemoteTool / custom MCP). This connection
# already exists in the Foundry project, so Terraform READS it (rather than
# managing/recreating it) and wires its endpoint + API key into the agent. The
# key is pulled from the existing connection at apply time via listsecrets — no
# key variable is required.
# ---------------------------------------------------------------------------
data "azapi_resource" "webiq_connection" {
  type                   = "Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01"
  resource_id            = "${azapi_resource.ai_foundry_project.id}/connections/webiq"
  response_export_values = ["properties.target"]
}

data "azapi_resource_action" "webiq_secrets" {
  type                   = "Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01"
  resource_id            = data.azapi_resource.webiq_connection.id
  action                 = "listsecrets"
  method                 = "POST"
  response_export_values = ["properties.credentials.keys"]
}

locals {
  # Endpoint + API key read from the existing Foundry `webiq` connection.
  webiq_mcp_url = try(data.azapi_resource.webiq_connection.output.properties.target, var.webiq_mcp_url)
  webiq_api_key = try(data.azapi_resource_action.webiq_secrets.output.properties.credentials.keys["x-apikey"], "")
}

resource "azapi_resource" "embedding_deployment" {
  depends_on = [azapi_resource.chat_deployment] # deployments must be created serially

  type                      = "Microsoft.CognitiveServices/accounts/deployments@2024-10-01"
  name                      = var.embedding_model
  parent_id                 = azapi_resource.ai_foundry.id
  schema_validation_enabled = false

  body = {
    sku = {
      name     = "Standard"
      capacity = 50
    }
    properties = {
      model = {
        format  = "OpenAI"
        name    = var.embedding_model
        version = var.embedding_model_version
      }
    }
  }
}
