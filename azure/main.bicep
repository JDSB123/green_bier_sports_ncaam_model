// ═══════════════════════════════════════════════════════════════════════════════
// NCAAM - Azure Container Apps Deployment v33.15.0
// ═══════════════════════════════════════════════════════════════════════════════
// Deploys:
// - Azure Key Vault (secrets storage) - v33.10.0
// - Azure Container Registry (ACR)
// - Azure Database for PostgreSQL Flexible Server
// - Azure Cache for Redis
// - Azure Container Apps Environment
// - NCAAM Prediction Service Container App
//
// v33.14.0 Changes:
// - Pick history blob storage uses external account (metricstrackersgbsv)
// - Pass storageConnectionString param to enable blob uploads
//
// v33.10.0 Changes:
// - Added Azure Key Vault for secure secrets management
// - All API keys and passwords stored in Key Vault
// - Container Apps reference Key Vault secrets
// - Completed cleanup
// ═══════════════════════════════════════════════════════════════════════════════

targetScope = 'resourceGroup'

// ─────────────────────────────────────────────────────────────────────────────────
// PARAMETERS
// ─────────────────────────────────────────────────────────────────────────────────

@description('Environment name (dev, staging, prod, stable)')
@allowed(['dev', 'staging', 'prod', 'stable'])
param environment string = 'stable'

@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Base name for all resources')
param baseName string = 'ncaam'

@description('PostgreSQL administrator password')
@secure()
param postgresPassword string

@description('The Odds API key')
@secure()
param oddsApiKey string

@description('Basketball API key (api-basketball.com)')
@secure()
param basketballApiKey string = ''

@description('Action Network username (for betting splits)')
@secure()
param actionNetworkUsername string = ''

@description('Action Network password (for betting splits)')
@secure()
param actionNetworkPassword string = ''

@description('Container image tag')
param imageTag string = 'v0.0.0'

@description('Suffix for resource names (e.g. -gbe for enterprise resources)')
param resourceNameSuffix string = ''

@description('Azure Storage connection string for pick history (external storage account)')
@secure()
param storageConnectionString string = ''

@description('Azure Storage connection string for canonical historical data')
@secure()
param canonicalStorageConnectionString string = ''

// ─────────────────────────────────────────────────────────────────────────────────
// VARIABLES
// ─────────────────────────────────────────────────────────────────────────────────

var resourcePrefix = '${baseName}-${environment}'
var acrName = replace('${resourcePrefix}${replace(resourceNameSuffix, '-', '')}acr', '-', '')
var postgresServerName = '${resourcePrefix}${resourceNameSuffix}-postgres'
var redisName = '${resourcePrefix}${resourceNameSuffix}-redis'
var containerEnvName = '${resourcePrefix}-env'
var containerAppName = '${resourcePrefix}-prediction'
var webAppName = '${resourcePrefix}-web'
var logAnalyticsName = '${resourcePrefix}-logs'
// REMOVED: ratingsJobName and oddsJobName - jobs consolidated into prediction service (v33.11.0)

// Common tags for resource organization (especially for enterprise resource group)
var commonTags = {
  Model: baseName
  Environment: environment
  ManagedBy: 'Bicep'
  Application: 'NCAAM-Prediction-Model'
}

// ─────────────────────────────────────────────────────────────────────────────────
// LOG ANALYTICS WORKSPACE
// ─────────────────────────────────────────────────────────────────────────────────

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: logAnalyticsName
  location: location
  tags: commonTags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// ─────────────────────────────────────────────────────────────────────────────────
// AZURE CONTAINER REGISTRY
// ─────────────────────────────────────────────────────────────────────────────────

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  tags: commonTags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: true
  }
}

// ─────────────────────────────────────────────────────────────────────────────────
// POSTGRESQL FLEXIBLE SERVER
// ─────────────────────────────────────────────────────────────────────────────────

resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2023-03-01-preview' = {
  name: postgresServerName
  location: location
  tags: commonTags
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    version: '15'
    administratorLogin: 'ncaam'
    administratorLoginPassword: postgresPassword
    storage: {
      storageSizeGB: 32
    }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
  }
}

// PostgreSQL Database
resource postgresDb 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2023-03-01-preview' = {
  parent: postgres
  name: 'ncaam'
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

// PostgreSQL Firewall - Allow Azure Services
resource postgresFirewall 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2023-03-01-preview' = {
  parent: postgres
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

// PostgreSQL Extensions (TimescaleDB not available in Azure, use pg_stat_statements)
resource postgresExtensions 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2023-03-01-preview' = {
  parent: postgres
  name: 'azure.extensions'
  properties: {
    value: 'PG_STAT_STATEMENTS,UUID-OSSP'
    source: 'user-override'
  }
}

// ─────────────────────────────────────────────────────────────────────────────────
// AZURE CACHE FOR REDIS
// ─────────────────────────────────────────────────────────────────────────────────

resource redis 'Microsoft.Cache/redis@2023-08-01' = {
  name: redisName
  location: location
  tags: commonTags
  properties: {
    sku: {
      name: 'Basic'
      family: 'C'
      capacity: 0
    }
    enableNonSslPort: false
    minimumTlsVersion: '1.2'
    redisConfiguration: {
      'maxmemory-policy': 'allkeys-lru'
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────────
// AZURE KEY VAULT - Secure secrets storage (v33.10.0)
// ─────────────────────────────────────────────────────────────────────────────────

var keyVaultName = '${resourcePrefix}${replace(resourceNameSuffix, '-', '')}kv'

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  tags: commonTags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enabledForDeployment: false
    enabledForDiskEncryption: false
    enabledForTemplateDeployment: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    enableRbacAuthorization: true
    publicNetworkAccess: 'Enabled'
  }
}

// Store secrets in Key Vault
resource kvSecretPostgres 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'postgres-password'
  properties: {
    value: postgresPassword
    contentType: 'text/plain'
  }
}

resource kvSecretOddsApi 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'odds-api-key'
  properties: {
    value: oddsApiKey
    contentType: 'text/plain'
  }
}

resource kvSecretRedis 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'redis-password'
  properties: {
    value: redis.listKeys().primaryKey
    contentType: 'text/plain'
  }
}

resource kvSecretBasketballApi 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (basketballApiKey != '') {
  parent: keyVault
  name: 'basketball-api-key'
  properties: {
    value: basketballApiKey
    contentType: 'text/plain'
  }
}

resource kvSecretActionNetworkUsername 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (actionNetworkUsername != '') {
  parent: keyVault
  name: 'action-network-username'
  properties: {
    value: actionNetworkUsername
    contentType: 'text/plain'
  }
}

resource kvSecretActionNetworkPassword 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (actionNetworkPassword != '') {
  parent: keyVault
  name: 'action-network-password'
  properties: {
    value: actionNetworkPassword
    contentType: 'text/plain'
  }
}

resource kvSecretAcr 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'acr-password'
  properties: {
    value: acr.listCredentials().passwords[0].value
    contentType: 'text/plain'
  }
}

resource kvSecretDatabaseUrl 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'database-url'
  properties: {
    value: 'postgresql://ncaam:${postgresPassword}@${postgres.properties.fullyQualifiedDomainName}:5432/ncaam?sslmode=require'
    contentType: 'text/plain'
  }
}

resource kvSecretStorageConnection 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (storageConnectionString != '') {
  parent: keyVault
  name: 'storage-connection-string'
  properties: {
    value: storageConnectionString
    contentType: 'text/plain'
  }
}

resource kvSecretCanonicalStorageConnection 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (canonicalStorageConnectionString != '') {
  parent: keyVault
  name: 'canonical-storage-connection-string'
  properties: {
    value: canonicalStorageConnectionString
    contentType: 'text/plain'
  }
}

resource kvSecretRedisUrl 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'redis-url'
  properties: {
    value: 'rediss://:${redis.listKeys().primaryKey}@${redis.properties.hostName}:6380'
    contentType: 'text/plain'
  }
}

// ─────────────────────────────────────────────────────────────────────────────────
// CONTAINER APPS ENVIRONMENT
// ─────────────────────────────────────────────────────────────────────────────────

resource containerEnv 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: containerEnvName
  location: location
  tags: commonTags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────────
// PREDICTION SERVICE CONTAINER APP
// ─────────────────────────────────────────────────────────────────────────────────

resource predictionApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: containerAppName
  location: location
  tags: commonTags
  properties: {
    managedEnvironmentId: containerEnv.id
    configuration: {
      activeRevisionsMode: 'Single'
      // Keep infra clean: allow only a small number of inactive revisions.
      // Historical ROI tracking lives in Postgres, not in old container revisions.
      maxInactiveRevisions: 1
      ingress: {
        external: true
        targetPort: 8082
        transport: 'http'
        allowInsecure: false
      }
      registries: [
        {
          server: acr.properties.loginServer
          username: acr.listCredentials().username
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: concat(
        [
          {
            name: 'acr-password'
            value: acr.listCredentials().passwords[0].value
          }
          {
            name: 'db-password'
            value: postgresPassword
          }
          {
            name: 'redis-password'
            value: redis.listKeys().primaryKey
          }
          {
            name: 'odds-api-key'
            value: oddsApiKey
          }
        ],
        (storageConnectionString != '') ? [
          {
            name: 'storage-connection-string'
            value: storageConnectionString
          }
        ] : [],
        (canonicalStorageConnectionString != '') ? [
          {
            name: 'canonical-storage-connection-string'
            value: canonicalStorageConnectionString
          }
        ] : [],
        (basketballApiKey != '') ? [
          {
            name: 'basketball-api-key'
            value: basketballApiKey
          }
        ] : [],
        (actionNetworkUsername != '') ? [
          {
            name: 'action-network-username'
            value: actionNetworkUsername
          }
        ] : [],
        (actionNetworkPassword != '') ? [
          {
            name: 'action-network-password'
            value: actionNetworkPassword
          }
        ] : []
      )
    }
    template: {
      containers: [
        {
          name: 'prediction-service'
          image: '${acr.properties.loginServer}/${baseName}-prediction:${imageTag}'
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
          env: concat(
            [
              {
                name: 'SPORT'
                value: 'ncaam'
              }
              {
                name: 'DB_USER'
                value: 'ncaam'
              }
              {
                name: 'DB_NAME'
                value: 'ncaam'
              }
              {
                name: 'DB_HOST'
                value: postgres.properties.fullyQualifiedDomainName
              }
              {
                name: 'DB_PORT'
                value: '5432'
              }
              {
                name: 'DATABASE_URL'
                value: 'postgresql://ncaam:${postgresPassword}@${postgres.properties.fullyQualifiedDomainName}:5432/ncaam?sslmode=require'
              }
              {
                name: 'REDIS_URL'
                value: 'rediss://:${redis.listKeys().primaryKey}@${redis.properties.hostName}:6380'
              }
              {
                name: 'THE_ODDS_API_KEY'
                secretRef: 'odds-api-key'
              }
            ],
            (basketballApiKey != '') ? [
              {
                name: 'BASKETBALL_API_KEY'
                secretRef: 'basketball-api-key'
              }
            ] : [],
            (actionNetworkUsername != '') ? [
              {
                name: 'ACTION_NETWORK_USERNAME'
                secretRef: 'action-network-username'
              }
            ] : [],
            (actionNetworkPassword != '') ? [
              {
                name: 'ACTION_NETWORK_PASSWORD'
                secretRef: 'action-network-password'
              }
            ] : [],
            [
              {
                name: 'TZ'
                value: 'America/Chicago'
              }
              // Team matching health defaults (override via env as needed)
              {
                name: 'TEAM_MATCHING_LOOKBACK_DAYS'
                value: '7'
              }
              {
                name: 'MIN_TEAM_RESOLUTION_RATE'
                value: '0.95'
              }
              {
                name: 'MAX_UNRESOLVED_TEAM_VARIANTS'
                value: '1'
              }
              // Azure Blob Storage for pick history snapshots (v33.14.0)
              {
                name: 'AZURE_STORAGE_CONNECTION_STRING'
                secretRef: 'storage-connection-string'
              }
              {
                name: 'AZURE_STORAGE_CONTAINER'
                value: 'picks-history'
              }
              {
                name: 'AZURE_CANONICAL_CONTAINER'
                value: 'ncaam-historical-data'
              }
            ],
            // Azure Blob Storage for canonical historical data (no fallbacks)
            (canonicalStorageConnectionString != '') ? [
              {
                name: 'AZURE_CANONICAL_CONNECTION_STRING'
                secretRef: 'canonical-storage-connection-string'
              }
            ] : []
          )
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: 8082
              }
              initialDelaySeconds: 30
              periodSeconds: 30
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/health'
                port: 8082
              }
              initialDelaySeconds: 10
              periodSeconds: 10
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
        rules: [
          {
            name: 'http-rule'
            http: {
              metadata: {
                concurrentRequests: '10'
              }
            }
          }
        ]
      }
    }
  }
}



// ─────────────────────────────────────────────────────────────────────────────────
// WEB FRONTEND CONTAINER APP (www.greenbiersportventures.com)
// ─────────────────────────────────────────────────────────────────────────────────

resource webApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: webAppName
  location: location
  tags: commonTags
  properties: {
    managedEnvironmentId: containerEnv.id
    configuration: {
      activeRevisionsMode: 'Single'
      // Keep infra clean: allow only a small number of inactive revisions.
      // Historical ROI tracking lives in Postgres, not in old container revisions.
      maxInactiveRevisions: 1
      ingress: {
        external: true
        targetPort: 8080
        transport: 'http'
        allowInsecure: false
      }
      registries: [
        {
          server: acr.properties.loginServer
          username: acr.listCredentials().username
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: [
        {
          name: 'acr-password'
          value: acr.listCredentials().passwords[0].value
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'web'
          image: '${acr.properties.loginServer}/gbsv-web:${imageTag}'
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: 8080
              }
              initialDelaySeconds: 5
              periodSeconds: 30
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 2
        rules: [
          {
            name: 'http-rule'
            http: {
              metadata: {
                concurrentRequests: '50'
              }
            }
          }
        ]
      }
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────────
// REMOVED: Standalone Container App Jobs (v33.11.0)
// ─────────────────────────────────────────────────────────────────────────────────
// The prediction service now handles ALL data orchestration internally:
// - Ratings sync: Embedded Go binary (/app/bin/ratings-sync) + Python fallback
// - Odds ingestion: Embedded Rust binary (/app/bin/odds-ingestion) + Python fallback
// - Betting splits: Python (Action Network client)
// - Barttorvik stats: Python (direct fetch)
//
// Single entry point: run_today.py orchestrates parallel data ingestion,
// team name resolution, validation, and prediction generation.
//
// Benefits:
// - No manual job triggering required
// - Guaranteed execution order (sync → validate → predict)
// - Atomic failures (no partial state)
// - Reduced ACA resource costs
// ─────────────────────────────────────────────────────────────────────────────────

// ─────────────────────────────────────────────────────────────────────────────────
// MONITORING & ALERTING
// ─────────────────────────────────────────────────────────────────────────────────

// Action Group for alert notifications
resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: '${resourcePrefix}-alerts'
  location: 'global'
  tags: commonTags
  properties: {
    groupShortName: 'NcaamAlerts'
    enabled: true
    emailReceivers: []  // Add email addresses as needed
    // If Teams webhook is configured, add webhook receiver
  }
}

// Alert: API Health Check Failures
resource apiHealthAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: '${resourcePrefix}-api-health-alert'
  location: 'global'
  tags: commonTags
  properties: {
    description: 'Alert when API health check fails'
    severity: 1
    enabled: true
    scopes: [
      predictionApp.id
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'HealthProbeFailure'
          criterionType: 'StaticThresholdCriterion'
          metricName: 'RestartCount'
          metricNamespace: 'microsoft.app/containerapps'
          operator: 'GreaterThan'
          threshold: 2
          timeAggregation: 'Total'
        }
      ]
    }
    actions: [
      {
        actionGroupId: actionGroup.id
      }
    ]
  }
}

// Alert: High Response Time
// resource latencyAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
//   name: '${resourcePrefix}-latency-alert'
//   location: 'global'
//   tags: commonTags
//   properties: {
//     description: 'Alert when API response time exceeds threshold'
//     severity: 2
//     enabled: true
//     scopes: [
//       predictionApp.id
//     ]
//     evaluationFrequency: 'PT5M'
//     windowSize: 'PT15M'
//     criteria: {
//       'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
//       allOf: [
//         {
//           name: 'HighLatency'
//           criterionType: 'StaticThresholdCriterion'
//           metricName: 'RequestDuration'
//           metricNamespace: 'microsoft.app/containerapps'
//           operator: 'GreaterThan'
//           threshold: 5000  // 5 seconds
//           timeAggregation: 'Average'
//         }
//       ]
//     }
//     actions: [
//       {
//         actionGroupId: actionGroup.id
//       }
//     ]
//   }
// }

// Alert: Database Connection Issues
resource dbConnectionAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: '${resourcePrefix}-db-connection-alert'
  location: 'global'
  tags: commonTags
  properties: {
    description: 'Alert when database connections are failing'
    severity: 1
    enabled: true
    scopes: [
      postgres.id
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'ConnectionFailures'
          criterionType: 'StaticThresholdCriterion'
          metricName: 'connections_failed'
          metricNamespace: 'microsoft.dbforpostgresql/flexibleservers'
          operator: 'GreaterThan'
          threshold: 5
          timeAggregation: 'Total'
        }
      ]
    }
    actions: [
      {
        actionGroupId: actionGroup.id
      }
    ]
  }
}

// Alert: High CPU Usage
resource cpuAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: '${resourcePrefix}-cpu-alert'
  location: 'global'
  tags: commonTags
  properties: {
    description: 'Alert when CPU usage is high'
    severity: 2
    enabled: true
    scopes: [
      predictionApp.id
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'HighCPU'
          criterionType: 'StaticThresholdCriterion'
          metricName: 'UsageNanoCores'
          metricNamespace: 'microsoft.app/containerapps'
          operator: 'GreaterThan'
          threshold: 800000000  // 80% of 1 core (in nanocores)
          timeAggregation: 'Average'
        }
      ]
    }
    actions: [
      {
        actionGroupId: actionGroup.id
      }
    ]
  }
}

// Alert: High Memory Usage
resource memoryAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: '${resourcePrefix}-memory-alert'
  location: 'global'
  tags: commonTags
  properties: {
    description: 'Alert when memory usage is high'
    severity: 2
    enabled: true
    scopes: [
      predictionApp.id
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'HighMemory'
          criterionType: 'StaticThresholdCriterion'
          metricName: 'WorkingSetBytes'
          metricNamespace: 'microsoft.app/containerapps'
          operator: 'GreaterThan'
          threshold: 1717986918  // ~1.6GB (80% of 2GB)
          timeAggregation: 'Average'
        }
      ]
    }
    actions: [
      {
        actionGroupId: actionGroup.id
      }
    ]
  }
}

// Log Analytics Query-based Alert: API 5xx Errors
resource serverErrorAlert 'Microsoft.Insights/scheduledQueryRules@2022-06-15' = {
  name: '${resourcePrefix}-5xx-errors-alert'
  location: location
  tags: commonTags
  properties: {
    displayName: 'API 5xx Errors'
    description: 'Alert when API returns 5xx errors'
    severity: 1
    enabled: true
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    scopes: [
      logAnalytics.id
    ]
    criteria: {
      allOf: [
        {
          query: '''
            ContainerAppConsoleLogs_CL
            | where ContainerAppName_s == '${containerAppName}'
            | where Log_s contains "500" or Log_s contains "502" or Log_s contains "503"
            | summarize ErrorCount = count() by bin(TimeGenerated, 5m)
          '''
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 5
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: [
        actionGroup.id
      ]
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────────
// OUTPUTS
// ─────────────────────────────────────────────────────────────────────────────────

output acrLoginServer string = acr.properties.loginServer
output acrName string = acr.name
output postgresHost string = postgres.properties.fullyQualifiedDomainName
output redisHost string = redis.properties.hostName
output containerAppUrl string = predictionApp.properties.configuration.ingress.fqdn
output webAppUrl string = webApp.properties.configuration.ingress.fqdn
// REMOVED: ratingsJobName and oddsJobName outputs - jobs consolidated into prediction service (v33.11.0)
output containerEnvName string = containerEnv.name
output actionGroupId string = actionGroup.id
output keyVaultName string = keyVault.name
output keyVaultUri string = keyVault.properties.vaultUri
// Storage account is external (metricstrackersgbsv in dashboard-gbsv-main-rg)
