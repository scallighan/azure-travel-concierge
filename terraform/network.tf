# ---------------------------------------------------------------------------
# Virtual network for the Container Apps environment + private endpoints.
#
# Cosmos DB (and other data services) have public network access disabled by
# subscription policy, so the workloads must reach them over private endpoints.
# The Container Apps environment is VNet-injected into snet-aca-infra and the
# private endpoints live in snet-pe. A private DNS zone linked to the VNet lets
# the containers resolve the Cosmos account to its private IP.
# ---------------------------------------------------------------------------
resource "azurerm_virtual_network" "this" {
  name                = "vnet-${local.func_name}"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  address_space       = var.vnet_address_space

  tags = local.tags
}

# Infrastructure subnet for the Container Apps (workload profiles) environment.
# Must be delegated to Microsoft.App/environments and be at least /27.
resource "azurerm_subnet" "aca_infra" {
  name                 = "snet-aca-infra"
  resource_group_name  = azurerm_resource_group.this.name
  virtual_network_name = azurerm_virtual_network.this.name
  address_prefixes     = [var.aca_infra_subnet_prefix]

  delegation {
    name = "aca-delegation"

    service_delegation {
      name    = "Microsoft.App/environments"
      actions = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
    }
  }
}

# Subnet dedicated to private endpoints.
resource "azurerm_subnet" "private_endpoints" {
  name                              = "snet-pe"
  resource_group_name               = azurerm_resource_group.this.name
  virtual_network_name              = azurerm_virtual_network.this.name
  address_prefixes                  = [var.private_endpoint_subnet_prefix]
  private_endpoint_network_policies = "Disabled"
}

# ---------------------------------------------------------------------------
# Private DNS + private endpoint for Cosmos DB (NoSQL / Sql subresource).
# ---------------------------------------------------------------------------
resource "azurerm_private_dns_zone" "cosmos" {
  name                = "privatelink.documents.azure.com"
  resource_group_name = azurerm_resource_group.this.name

  tags = local.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "cosmos" {
  name                  = "cosmos-${local.func_name}"
  resource_group_name   = azurerm_resource_group.this.name
  private_dns_zone_name = azurerm_private_dns_zone.cosmos.name
  virtual_network_id    = azurerm_virtual_network.this.id
  registration_enabled  = false

  tags = local.tags
}

resource "azurerm_private_endpoint" "cosmos" {
  name                = "pe-cosmos-${local.func_name}"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  subnet_id           = azurerm_subnet.private_endpoints.id

  private_service_connection {
    name                           = "psc-cosmos-${local.func_name}"
    private_connection_resource_id = azurerm_cosmosdb_account.this.id
    is_manual_connection           = false
    subresource_names              = ["Sql"]
  }

  private_dns_zone_group {
    name                 = "cosmos"
    private_dns_zone_ids = [azurerm_private_dns_zone.cosmos.id]
  }

  tags = local.tags
}
