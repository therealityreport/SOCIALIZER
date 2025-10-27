resource "azurerm_storage_account" "this" {
  name                     = var.storage_account_name
  resource_group_name      = var.resource_group_name
  location                 = var.location
  account_tier             = var.account_tier
  account_replication_type = var.replication_type
  allow_nested_items_to_be_public = false
  min_tls_version                = "TLS1_2"

  tags = var.tags
}

resource "azurerm_storage_container" "this" {
  for_each              = toset(var.container_names)
  name                  = lower(each.value)
  storage_account_name  = azurerm_storage_account.this.name
  container_access_type = "private"
}

resource "azurerm_storage_share" "this" {
  name                 = lower(var.file_share_name)
  storage_account_name = azurerm_storage_account.this.name
  quota                = var.file_share_quota_gb
}
