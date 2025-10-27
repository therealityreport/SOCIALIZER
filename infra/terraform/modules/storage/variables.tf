variable "storage_account_name" {
  description = "Globally unique name for the storage account."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group where the storage account is deployed."
  type        = string
}

variable "location" {
  description = "Azure region for the storage account."
  type        = string
}

variable "account_tier" {
  description = "Storage account performance tier (Standard or Premium)."
  type        = string
}

variable "replication_type" {
  description = "Storage account replication strategy (LRS, GRS, etc.)."
  type        = string
}

variable "file_share_name" {
  description = "Name assigned to the Azure Files share."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9-]{3,63}$", lower(var.file_share_name)))
    error_message = "file_share_name must be 3-63 characters, lowercase letters, numbers, or hyphens."
  }
}

variable "file_share_quota_gb" {
  description = "Quota for the Azure Files share in gigabytes."
  type        = number
  default     = 100
}

variable "container_names" {
  description = "List of blob container names to provision."
  type        = list(string)
  default     = []

  validation {
    condition     = alltrue([for name in var.container_names : can(regex("^[a-z0-9-]{3,63}$", lower(name)))])
    error_message = "Each container name must be 3-63 characters, lowercase letters, numbers, or hyphens."
  }
}

variable "tags" {
  description = "Tags propagated to the storage account."
  type        = map(string)
  default     = {}
}
