# ---------------------------------------------------------------------------
# Azure Static Web App - hosts the React concierge UI (replaces AWS Amplify)
# ---------------------------------------------------------------------------
resource "azurerm_static_web_app" "this" {
  name                = "swa-${local.func_name}"
  resource_group_name = azurerm_resource_group.this.name
  location            = "eastus2" # SWA is available in a limited set of regions
  sku_tier            = "Free"
  sku_size            = "Free"
  tags                = local.tags
}
