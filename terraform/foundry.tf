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
