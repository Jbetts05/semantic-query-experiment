# Azure resources

The experiment base stack is deployed in one Azure environment.

| Setting | Value |
| --- | --- |
| Subscription | `556dc8cb-5da1-41d7-8a10-1be2cd6de16e` |
| Resource group | `rg-semantic-query-experiment` |
| Region | `swedencentral` |
| Azure AI Search | `semqry-search-556dc8sc` |
| Azure AI Services | `semqry-ai-556dc8sc` |
| Storage account | `semqry556dc8sc` |
| Application Insights | `semqry-appi-556dc8sc` |

East US 2 was the first requested region, but Azure rejected new Search
provisioning there with `InsufficientResourcesAvailable`. The partial East US 2
resources were removed and the base stack was redeployed in Sweden Central.

Model deployments are intentionally separate from the base stack and must pass
live model/SKU/quota validation before creation.
