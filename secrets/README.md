# Docker Secrets Directory

This directory contains Docker secrets for production deployments.

## Setup Instructions

### 1. Create Secret Files

For each secret, create a file containing only the secret value (no newline at end):

```bash
# Database password
echo -n "your_strong_db_password_here" > db_password.txt

# Redis password  
echo -n "your_strong_redis_password_here" > redis_password.txt

# JWT secret (generate with: openssl rand -hex 32)
openssl rand -hex 32 | tr -d '\n' > jwt_secret.txt

# Master API key (generate with: openssl rand -hex 32)
openssl rand -hex 32 | tr -d '\n' > master_api_key.txt

# The Odds API key (get from https://the-odds-api.com/)
# Code reads from: /run/secrets/odds_api_key (Docker) or env var THE_ODDS_API_KEY (Azure)
# Replace YOUR_ACTUAL_KEY with your real API key from the website
echo -n "YOUR_ACTUAL_KEY" > odds_api_key.txt

# Microsoft Teams Incoming Webhook URL (OPTIONAL - only needed for --teams)
# Code reads from: /run/secrets/teams_webhook_url (Docker) or env var TEAMS_WEBHOOK_URL (Azure)
echo -n "YOUR_TEAMS_WEBHOOK_URL" > teams_webhook_url.txt
```

### 2. Secure File Permissions

```bash
chmod 600 *.txt
```

### 3. Add to .gitignore

These files should NEVER be committed:

```
secrets/*.txt
secrets/*.key
```

## Docker Secrets Usage

The `docker-compose.yml` mounts these as Docker secrets:

```yaml
secrets:
  db_password:
    file: ./secrets/db_password.txt
  redis_password:
    file: ./secrets/redis_password.txt
  jwt_secret:
    file: ./secrets/jwt_secret.txt

services:
  postgres:
    secrets:
      - db_password
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
```

## Security Best Practices

1. **Never commit secrets** - All `.txt` files in this directory are gitignored
2. **Use strong passwords** - Minimum 32 characters for production
3. **Rotate regularly** - Change secrets at least quarterly
4. **Audit access** - Monitor who has access to this directory
5. **Use vault for production** - Consider HashiCorp Vault for enterprise deployments

## Generating Strong Secrets

```bash
# 32-character hex string (recommended for JWT/API keys)
openssl rand -hex 32

# 48-character base64 string (alternative)
openssl rand -base64 36

# Password with special characters
openssl rand -base64 24 | tr -d '\n'
```

