output "storage_account_name" {
  description = "Provisioned storage account name."
  value       = azurerm_storage_account.this.name
}

output "primary_key" {
  description = "Primary access key for the storage account."
  value       = azurerm_storage_account.this.primary_access_key
  sensitive   = true
}

output "primary_connection_string" {
  description = "Primary connection string for the storage account."
  value       = azurerm_storage_account.this.primary_connection_string
  sensitive   = true
}

output "blob_container_names" {
  description = "Names of blob containers that were created."
  value       = [for container in azurerm_storage_container.this : container.name]
}
