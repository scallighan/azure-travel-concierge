variable "subscription_id" {
  type      = string
  sensitive = true
}

variable "location" {
  type    = string
  default = "EastUS2"
}

variable "gh_repo" {
  type        = string
  description = "GitHub repo in owner/name form used for image pulls and naming (e.g. scallighan/travel-concierge-azure)."
}

variable "chat_model" {
  type        = string
  description = "Azure AI Foundry chat model to deploy for orchestration/sub-agents."
  default     = "gpt-5.4"
}

variable "chat_model_version" {
  type    = string
  default = "2026-03-05"
}

variable "chat_model_capacity" {
  type        = number
  description = "TPM capacity (in thousands) for the chat model deployment."
  default     = 750
}

variable "embedding_model" {
  type        = string
  description = "Azure AI Foundry embedding model for AI Search vectorization."
  default     = "text-embedding-3-small"
}

variable "embedding_model_version" {
  type    = string
  default = "1"
}

variable "container_image_tag" {
  type    = string
  default = "latest"
}

variable "vnet_address_space" {
  type        = list(string)
  description = "Address space for the VNet that hosts the Container Apps environment and private endpoints."
  default     = ["10.0.0.0/16"]
}

variable "aca_infra_subnet_prefix" {
  type        = string
  description = "CIDR for the Container Apps environment infrastructure subnet (min /27 for workload profiles environments)."
  default     = "10.0.0.0/23"
}

variable "private_endpoint_subnet_prefix" {
  type        = string
  description = "CIDR for the subnet that hosts private endpoints (Cosmos DB, etc.)."
  default     = "10.0.4.0/24"
}

variable "enable_vic_integration" {
  type        = bool
  description = "Feature flag to enable the (mock) VIC payment integration in the agent and UI."
  default     = true
}

variable "use_existing_search" {
  type        = bool
  description = "Reuse an existing Azure AI Search service instead of creating a new one (saves cost/capacity)."
  default     = false
}

variable "existing_search_service_name" {
  type        = string
  description = "Name of the existing Azure AI Search service to reuse (required when use_existing_search = true)."
  default     = ""
}

variable "existing_search_resource_group_name" {
  type        = string
  description = "Resource group of the existing search service. Defaults to this deployment's resource group when blank."
  default     = ""
}

variable "search_index_name" {
  type        = string
  description = "Name of the AI Search index used for the knowledge base."
  default     = "travel-documentation"
}

# ---------------------------------------------------------------------------
# Foundry Toolbox (travel-concierge-toolbox) + Foundry-hosted Payments agent
# ---------------------------------------------------------------------------
# The travel-concierge-toolbox bundles WebIQ (web intelligence) and the VIC
# payment tools behind one MCP endpoint. The skills and the Payments agent
# consume it with centralized AAD auth.
variable "foundry_toolbox_name" {
  type        = string
  description = "Name of the Foundry Toolbox the skills and Payments agent consume."
  default     = "travel-concierge-toolbox"
}

variable "foundry_toolbox_version" {
  type        = string
  description = "Toolbox version to pin. When blank the default version is resolved at startup."
  default     = ""
}

variable "payments_agent_name" {
  type        = string
  description = "Name of the Foundry-hosted Payments agent (visible in the Foundry portal)."
  default     = "travel-payments-agent"
}

variable "webiq_mcp_url" {
  type        = string
  description = "Fallback WebIQ MCP endpoint used only if the existing Foundry 'webiq' connection can't be read. Normally the URL is read from that connection."
  default     = "https://api.microsoft.ai/v3/mcp"
}
