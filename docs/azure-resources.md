# Azure resources

The experiment base stack is deployed in one Azure environment.

| Setting | Value |
| --- | --- |
| Subscription | `556dc8cb-5da1-41d7-8a10-1be2cd6de16e` |
| Resource group | `rg-semantic-query-experiment` |
| Region | `swedencentral` |
| Azure AI Search | `semqry-search-556dc8sc` |
| Search index | `semantic-query-gxp-8fcc73ca-azure-openai-text-embedding-3-large-3072` |
| Azure AI Services | `semqry-ai-556dc8sc` |
| Storage account | `semqry556dc8sc` |
| Application Insights | `semqry-appi-556dc8sc` |
| Embedding deployment | `text-embedding-3-large` / `text-embedding-3-large` v`1` / `Standard` capacity `10` |
| Generation deployment | `gpt-5-4` / `gpt-5.4` v`2026-03-05` / `GlobalStandard` capacity `10` |

East US 2 was the first requested region, but Azure rejected new Search
provisioning there with `InsufficientResourcesAvailable`. The partial East US 2
resources were removed and the base stack was redeployed in Sweden Central.

`gpt-5.5` was listed in the model catalog but had zero quota in this
subscription/region at deployment time, so `gpt-5.4` was selected as the
generation fallback.
