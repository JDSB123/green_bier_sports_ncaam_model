# Configure Container Apps to Use Existing Azure PostgreSQL Database

This guide shows how to configure your NCAAM Container Apps to use an existing Azure PostgreSQL database instead of creating a new one.

## Quick Setup (PowerShell Script)

Use the provided script to configure all container apps at once:

```powershell
cd azure
.\configure-existing-db.ps1 `
    -DbHost "ncaam-stable-gbsv-postgres.postgres.database.azure.com" `
    -DbUser "ncaam" `
    -DbPassword "<password>" `
    -DbName "ncaam"
```

This will:
1. Set the database password as a secret in each container app
2. Update environment variables (DB_HOST, DB_USER, DB_NAME, DB_PORT, DATABASE_URL)
3. Verify the configuration

The container apps will automatically restart with the new configuration.

## Manual Setup (Azure CLI)

If you prefer to configure manually, use these commands:

### 1. Set Database Password Secret

```powershell
$ResourceGroup = "NCAAM-GBSV-MODEL-RG"
$Environment = "stable"
$DbPassword = "your_password"

# For prediction service
az containerapp secret set `
    --name "ncaam-$Environment-prediction" `
    --resource-group $ResourceGroup `
    --secrets "db-password=$DbPassword"

# For ratings sync job
az containerapp secret set `
    --name "ncaam-$Environment-ratings-sync" `
    --resource-group $ResourceGroup `
    --secrets "db-password=$DbPassword"

# For odds ingestion job
az containerapp secret set `
    --name "ncaam-$Environment-odds-ingestion" `
    --resource-group $ResourceGroup `
    --secrets "db-password=$DbPassword"
```

### 2. Update Environment Variables

```powershell
$DbHost = "ncaam-stable-gbsv-postgres.postgres.database.azure.com"
$DbUser = "your_username"
$DbPassword = "your_password"
$DbName = "ncaam"
$DbPort = "5432"
$DatabaseUrl = "postgresql://${DbUser}:${DbPassword}@${DbHost}:${DbPort}/${DbName}?sslmode=require"

# Update prediction service
az containerapp update `
    --name "ncaam-$Environment-prediction" `
    --resource-group $ResourceGroup `
    --set-env-vars "DB_HOST=$DbHost" "DB_USER=$DbUser" "DB_NAME=$DbName" "DB_PORT=$DbPort" "DATABASE_URL=$DatabaseUrl"

# Update ratings sync job
az containerapp update `
    --name "ncaam-$Environment-ratings-sync" `
    --resource-group $ResourceGroup `
    --set-env-vars "DB_HOST=$DbHost" "DB_USER=$DbUser" "DB_NAME=$DbName" "DB_PORT=$DbPort" "DATABASE_URL=$DatabaseUrl"

# Update odds ingestion job
az containerapp update `
    --name "ncaam-$Environment-odds-ingestion" `
    --resource-group $ResourceGroup `
    --set-env-vars "DB_HOST=$DbHost" "DB_USER=$DbUser" "DB_NAME=$DbName" "DB_PORT=$DbPort" "DATABASE_URL=$DatabaseUrl"
```

## Verify Configuration

### Check Environment Variables

```powershell
az containerapp show `
    --name "ncaam-$Environment-prediction" `
    --resource-group $ResourceGroup `
    --query "properties.template.containers[0].env[?name=='DB_HOST'].value" `
    --output tsv
```

### Check Logs

```powershell
az containerapp logs show `
    --name "ncaam-$Environment-prediction" `
    --resource-group $ResourceGroup `
    --follow
```

### Check Health Endpoint

```powershell
$fqdn = az containerapp show `
    --name "ncaam-$Environment-prediction" `
    --resource-group $ResourceGroup `
    --query "properties.configuration.ingress.fqdn" `
    --output tsv

curl "https://$fqdn/health"
```

## Database Connection Details

Your existing database configuration:

- **Host:** `ncaam-stable-gbsv-postgres.postgres.database.azure.com`
- **User:** `<your_username>` (replace with actual username)
- **Password:** `<your_password>` (replace with actual password)
- **Database:** `ncaam`
- **Port:** `5432`
- **SSL:** Required (`?sslmode=require`)

## Important Notes

1. **SSL Required:** Azure PostgreSQL requires SSL connections. The connection string includes `?sslmode=require`.

2. **Firewall Rules:** Ensure your Azure PostgreSQL firewall allows connections from:
   - Azure Container Apps (use "Allow access to Azure services")
   - Your IP address if testing locally

3. **Secret Storage:** The password is stored as an Azure Container App secret, which is more secure than plain environment variables.

4. **Restart:** Container apps automatically restart when environment variables or secrets are updated.

5. **Multiple Apps:** All three container apps (prediction, ratings-sync, odds-ingestion) need the same database configuration.

## Troubleshooting

### Connection Errors

If you see connection errors in the logs:

1. **Check firewall rules:**
   ```powershell
   az postgres flexible-server firewall-rule list `
       --resource-group $ResourceGroup `
       --name "ncaam-stable-gbsv-postgres"
   ```

2. **Test connection from Azure Cloud Shell:**
   ```bash
   psql "host=ncaam-stable-gbsv-postgres.postgres.database.azure.com port=5432 dbname=ncaam user=ncaam sslmode=require"
   ```

### Environment Variables Not Updating

If environment variables don't seem to update:

1. Check the container app revision:
   ```powershell
   az containerapp revision list `
       --name "ncaam-$Environment-prediction" `
       --resource-group $ResourceGroup
   ```

2. Force a new revision:
   ```powershell
   az containerapp update `
       --name "ncaam-$Environment-prediction" `
       --resource-group $ResourceGroup `
       --set-env-vars "DB_HOST=$DbHost" `
       --output none
   ```

## Next Steps

After configuring the database:

1. Run database migrations (they run automatically on container startup)
2. Verify the health endpoint returns `200 OK`
3. Check logs for any connection errors
4. Test predictions: `curl https://<fqdn>/predict`

