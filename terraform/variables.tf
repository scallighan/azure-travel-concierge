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
  default     = 50
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
  default     = "visa-documentation"
}
