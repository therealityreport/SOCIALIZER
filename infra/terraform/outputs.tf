output "resource_group_name" {
  description = "Name of the resource group containing the Socializer infrastructure."
  value       = azurerm_resource_group.this.name
}

output "resource_group_location" {
  description = "Azure region where resources were provisioned."
  value       = azurerm_resource_group.this.location
}

output "storage_account_name" {
  description = "Globally unique storage account name."
  value       = module.storage.storage_account_name
}

output "storage_account_primary_connection_string" {
  description = "Connection string for the generated storage account."
  value       = module.storage.primary_connection_string
  sensitive   = true
}

output "backend_app_hostname" {
  description = "Default hostname for the backend App Service."
  value       = azurerm_app_service.backend.default_site_hostname
}

output "text_analytics_endpoint" {
  description = "Endpoint for the Text Analytics cognitive service."
  value       = local.text_analytics_endpoint
}
