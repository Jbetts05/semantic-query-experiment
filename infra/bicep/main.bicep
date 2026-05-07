targetScope = 'resourceGroup'

@description('Base name used for experiment resources.')
param experimentName string = 'semantic-query-experiment'

@description('Azure region selected by the preflight step.')
param location string = resourceGroup().location

@description('Azure AI Search service name.')
param searchServiceName string

@description('Azure AI Search SKU. Keep small unless the experiment requires more scale.')
@allowed([
  'basic'
  'standard'
])
param searchSku string = 'basic'

@description('Azure AI Services account name for model deployments.')
param aiServicesName string

@description('Storage account name for experiment artifacts.')
param storageAccountName string

@description('Application Insights component name for experiment telemetry.')
param appInsightsName string

@description('Resource tags.')
param tags object = {}

resource search 'Microsoft.Search/searchServices@2025-05-01' = {
  name: searchServiceName
  location: location
  tags: tags
  sku: {
    name: searchSku
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'Default'
    semanticSearch: 'standard'
    publicNetworkAccess: 'enabled'
    disableLocalAuth: false
  }
}

resource aiServices 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: aiServicesName
  location: location
  kind: 'AIServices'
  tags: tags
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    publicNetworkAccess: 'Enabled'
    customSubDomainName: aiServicesName
  }
}

resource storage 'Microsoft.Storage/storageAccounts@2025-01-01' = {
  name: storageAccountName
  location: location
  tags: tags
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
  }
}

output experimentName string = experimentName
output searchEndpoint string = 'https://${search.name}.search.windows.net'
output aiServicesEndpoint string = aiServices.properties.endpoint
output storageAccountName string = storage.name
output appInsightsInstrumentationKey string = appInsights.properties.InstrumentationKey
