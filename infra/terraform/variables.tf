variable "resource_group_name" {
  description = "Name of the Azure resource group to create or reuse."
  type        = string
}

variable "location" {
  description = "Azure region where resources will be deployed."
  type        = string
}

variable "tags" {
  description = "Common tags applied to all resources."
  type        = map(string)
  default     = {}
}

variable "storage_account_prefix" {
  description = "Prefix used when generating the globally unique storage account name (letters and numbers only)."
  type        = string
  default     = "socializerstorage"

  validation {
    condition     = can(regex("^[-a-zA-Z0-9]{3,18}$", var.storage_account_prefix))
    error_message = "storage_account_prefix must be 3-18 characters and contain only letters, numbers, or dashes."
  }

  validation {
    condition     = length(regexreplace(var.storage_account_prefix, "[^a-zA-Z0-9]", "")) >= 3
    error_message = "storage_account_prefix must contain at least three alphanumeric characters once non-supported characters are removed."
  }
}

variable "storage_account_tier" {
  description = "Storage account performance tier."
  type        = string
  default     = "Standard"
}

variable "storage_replication_type" {
  description = "Storage account replication type (e.g. LRS, GRS)."
  type        = string
  default     = "LRS"
}

variable "file_share_name" {
  description = "Name of the Azure file share created for the application."
  type        = string
  default     = "appshare"
}

variable "container_names" {
  description = "List of blob containers provisioned for the backend."
  type        = list(string)
  default     = ["media", "logs"]
}

variable "default_blob_container" {
  description = "Primary blob container used by the backend service."
  type        = string
  default     = "media"

  validation {
    condition     = contains(var.container_names, var.default_blob_container)
    error_message = "default_blob_container must be included in container_names."
  }
}

variable "name_prefix" {
  description = "Base name applied to Azure resources for this deployment."
  type        = string
  default     = "socializer"
}

variable "text_analytics_sku" {
  description = "SKU for the Azure Cognitive Services Text Analytics account."
  type        = string
  default     = "S"
}

variable "app_service_plan_tier" {
  description = "App Service plan SKU tier."
  type        = string
  default     = "P1v2"
}

variable "app_service_plan_size" {
  description = "App Service plan SKU size."
  type        = string
  default     = "P1v2"
}

variable "backend_app_linux_fx_version" {
  description = "Runtime stack for the backend App Service (e.g. DOTNETCORE|7.0, NODE|18-lts)."
  type        = string
  default     = "NODE|18-lts"
}

variable "backend_package_url" {
  description = "URL to the backend zip package or artifact for run-from-package deployments."
  type        = string
  default     = ""
}

variable "primary_model" {
  description = "Primary ML model identifier for sentiment analysis."
  type        = string
  default     = "cardiffnlp/twitter-roberta-base-topic-sentiment-latest"
}

variable "fallback_service" {
  description = "Fallback sentiment analysis service name."
  type        = string
  default     = "azure-opinion-mining"
}

variable "confidence_threshold" {
  description = "Confidence threshold controlling backend classification decisions."
  type        = number
  default     = 0.75
}

variable "azure_text_analytics_endpoint" {
  description = "Azure Cognitive Services Text Analytics endpoint URL."
  type        = string
  default     = ""
}

variable "azure_text_analytics_key" {
  description = "Azure Cognitive Services Text Analytics API key."
  type        = string
  default     = ""
  sensitive   = true
}

variable "additional_app_settings" {
  description = "Additional App Service application settings."
  type        = map(string)
  default     = {}
}
