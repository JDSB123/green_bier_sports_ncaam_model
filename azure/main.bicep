// ═══════════════════════════════════════════════════════════════════════════════
// NCAAM v33.6.1 - Azure Container Apps Deployment
// ═══════════════════════════════════════════════════════════════════════════════
// Deploys:
// - Azure Container Registry (ACR)
// - Azure Database for PostgreSQL Flexible Server
// - Azure Cache for Redis
// - Azure Container Apps Environment
// - NCAAM Prediction Service Container App
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

@description('Microsoft Teams incoming webhook URL (optional)')
@secure()
param teamsWebhookUrl string = ''

@description('Basketball API key (api-basketball.com)')
@secure()
param basketballApiKey string = ''

@description('Container image tag')
param imageTag string = 'v33.6.1'

@description('Suffix for resource names (e.g. -gbe for enterprise resources)')
param resourceNameSuffix string = ''

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
var ratingsJobName = '${resourcePrefix}-ratings-sync'
var oddsJobName = '${resourcePrefix}-odds-ingestion'
var logAnalyticsName = '${resourcePrefix}-logs'

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
        (basketballApiKey != '') ? [
          {
            name: 'basketball-api-key'
            value: basketballApiKey
          }
        ] : [],
        (teamsWebhookUrl != '') ? [
          {
            name: 'teams-webhook-url'
            value: teamsWebhookUrl
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
            (teamsWebhookUrl != '') ? [
              {
                name: 'TEAMS_WEBHOOK_URL'
                secretRef: 'teams-webhook-url'
              }
            ] : [],
            [
              {
                name: 'MODEL__HOME_COURT_ADVANTAGE_SPREAD'
                value: '3.2'
              }
              {
                name: 'MODEL__HOME_COURT_ADVANTAGE_TOTAL'
                value: '0.0'
              }
              {
                name: 'TZ'
                value: 'America/Chicago'
              }
            ]
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
// MANUAL-ONLY PIPELINE JOBS (Container Apps Jobs)
// ─────────────────────────────────────────────────────────────────────────────────

resource ratingsSyncJob 'Microsoft.App/jobs@2023-05-01' = {
  name: ratingsJobName
  location: location
  tags: commonTags
  properties: {
    environmentId: containerEnv.id
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: 1800
      replicaRetryLimit: 1
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
          name: 'ratings-sync'
          image: '${acr.properties.loginServer}/${baseName}-ratings-sync:${imageTag}'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            {
              name: 'SPORT'
              value: 'ncaam'
            }
            {
              name: 'RUN_ONCE'
              value: 'true'
            }
            {
              name: 'DATABASE_URL'
              value: 'postgresql://ncaam:${postgresPassword}@${postgres.properties.fullyQualifiedDomainName}:5432/ncaam?sslmode=require'
            }
          ]
        }
      ]
    }
  }
}

resource oddsIngestionJob 'Microsoft.App/jobs@2023-05-01' = {
  name: oddsJobName
  location: location
  tags: commonTags
  properties: {
    environmentId: containerEnv.id
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: 1800
      replicaRetryLimit: 1
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
        {
          name: 'odds-api-key'
          value: oddsApiKey
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'odds-ingestion'
          image: '${acr.properties.loginServer}/${baseName}-odds-ingestion:${imageTag}'
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
          env: [
            {
              name: 'SPORT'
              value: 'ncaam'
            }
            {
              name: 'RUN_ONCE'
              value: 'true'
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
          ]
        }
      ]
    }
  }
}

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
output ratingsJobName string = ratingsSyncJob.name
output oddsJobName string = oddsIngestionJob.name
output containerEnvName string = containerEnv.name
output actionGroupId string = actionGroup.id
