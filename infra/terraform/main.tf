terraform {
  required_version = ">= 1.4.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.78"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }
}

provider "azurerm" {
  features {}
}

locals {
  sanitized_storage_prefix = lower(regexreplace(var.storage_account_prefix, "[^a-z0-9]", ""))
  unique_suffix            = random_string.naming.result
  storage_account_name     = substr("${local.sanitized_storage_prefix}${local.unique_suffix}", 0, 24)
  sanitized_name_prefix    = lower(regexreplace(var.name_prefix, "[^a-z0-9]", ""))
  backend_app_name         = substr("${local.sanitized_name_prefix}-backend-${local.unique_suffix}", 0, 60)
  app_service_plan_name    = substr("${local.sanitized_name_prefix}-plan-${local.unique_suffix}", 0, 60)
  text_analytics_account_name = substr("${local.sanitized_name_prefix}ta${local.unique_suffix}", 0, 63)
}

resource "random_string" "naming" {
  length  = 6
  upper   = false
  lower   = true
  numeric = true
  special = false
}

resource "azurerm_resource_group" "this" {
  name     = var.resource_group_name
  location = var.location
  tags     = var.tags
}

module "storage" {
  source = "./modules/storage"

  storage_account_name = local.storage_account_name
  location             = azurerm_resource_group.this.location
  resource_group_name  = azurerm_resource_group.this.name
  account_tier         = var.storage_account_tier
  replication_type     = var.storage_replication_type
  file_share_name      = var.file_share_name
  container_names      = var.container_names
  tags                 = var.tags
}

resource "azurerm_cognitive_account" "text_analytics" {
  name                = local.text_analytics_account_name
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  kind                = "TextAnalytics"
  sku_name            = var.text_analytics_sku
  tags                = var.tags
}

locals {
  text_analytics_endpoint = var.azure_text_analytics_endpoint != "" ? var.azure_text_analytics_endpoint : azurerm_cognitive_account.text_analytics.endpoint
  text_analytics_key      = var.azure_text_analytics_key != "" ? var.azure_text_analytics_key : azurerm_cognitive_account.text_analytics.primary_access_key
}

resource "azurerm_app_service_plan" "this" {
  name                = local.app_service_plan_name
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name

  sku {
    tier = var.app_service_plan_tier
    size = var.app_service_plan_size
  }

  tags = var.tags
}

resource "azurerm_app_service" "backend" {
  name                = local.backend_app_name
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  app_service_plan_id = azurerm_app_service_plan.this.id

  site_config {
    linux_fx_version = var.backend_app_linux_fx_version
    always_on        = true
  }

  app_settings = merge({
    "WEBSITE_RUN_FROM_PACKAGE"      = var.backend_package_url
    "PRIMARY_MODEL"                 = var.primary_model
    "FALLBACK_SERVICE"              = var.fallback_service
    "CONFIDENCE_THRESHOLD"          = tostring(var.confidence_threshold)
    "AZURE_TEXT_ANALYTICS_ENDPOINT" = local.text_analytics_endpoint
    "AZURE_TEXT_ANALYTICS_KEY"      = local.text_analytics_key
    "STORAGE_ACCOUNT_NAME"          = module.storage.storage_account_name
    "STORAGE_ACCOUNT_KEY"           = module.storage.primary_key
    "STORAGE_CONTAINER"             = var.default_blob_container
  }, var.additional_app_settings)

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}
