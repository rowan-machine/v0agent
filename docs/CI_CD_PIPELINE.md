# CI/CD Pipeline Documentation

## Overview

This project uses GitHub Actions for continuous integration and Railway for deployment. The pipeline follows best practices with separate staging and production environments.

## Environment Setup

### Railway Environments

| Environment | Branch | URL | Purpose |
|-------------|--------|-----|---------|
| **Staging** | `dev` | https://v0agent-staging.up.railway.app | Testing and validation |
| **Production** | `main` | https://v0agent-production.up.railway.app | Live user traffic |

### Required GitHub Secrets

Add these secrets in GitHub Repository Settings → Secrets and variables → Actions:

```
# Railway Deployment Tokens
# Generate at: https://railway.com/account/tokens
# Each environment can have its own token for isolation
RAILWAY_TOKEN              # Fallback token (if environment-specific not set)
RAILWAY_TOKEN_STAGING      # Token for staging deployments (recommended)
RAILWAY_TOKEN_PRODUCTION   # Token for production deployments (recommended)

# Database
SUPABASE_URL         # Supabase project URL
SUPABASE_KEY         # Supabase anon key

# AI Services (for tests)
OPENAI_API_KEY       # OpenAI API key (for tests)
ANTHROPIC_API_KEY    # Anthropic API key (for tests)
```

#### Railway Token Setup

1. Go to https://railway.com/account/tokens
2. Create tokens for each environment:
   - Name: `v0agent-staging-deploy` → Add as `RAILWAY_TOKEN_STAGING`
   - Name: `v0agent-production-deploy` → Add as `RAILWAY_TOKEN_PRODUCTION`
3. The workflows use fallback logic: `RAILWAY_TOKEN_STAGING || RAILWAY_TOKEN`

> **Note**: Using separate tokens per environment provides better security isolation and audit trails.

## Workflows

### 1. CI (`ci.yml`)
**Triggers:** Push to `main` or `dev`, Pull requests

**Jobs:**
- **Lint**: Runs Ruff linter and formatter
- **Test**: Runs pytest with unit tests
- **Build**: Validates Docker build
- **Security**: Checks dependencies for vulnerabilities

### 2. PR Checks (`pr-checks.yml`)
**Triggers:** Pull request to `main` or `dev`

**Features:**
- Smart change detection (only runs affected checks)
- Lint check for source changes
- Test check for source/test changes
- Docker build validation

### 3. Deploy to Staging (`deploy-staging.yml`)
**Triggers:** Push to `dev` branch, Manual trigger

**Process:**
1. Deploy to Railway staging environment
2. Wait for deployment to propagate
3. Health check validation (10 retries)
4. Report deployment status

### 4. Deploy to Production (`deploy-production.yml`)
**Triggers:** Push to `main` branch, Manual trigger

**Process:**
1. Run full CI checks
2. Validate staging environment health
3. **Manual approval required** (via GitHub environment protection)
4. Deploy to Railway production
5. Health check validation (15 retries)
6. Create release tag on success

### 5. Scheduled Checks (`scheduled-checks.yml`)
**Triggers:** Every 6 hours, Manual trigger

**Checks:**
- Staging environment health
- Production environment health
- Dependency security audit

## Deployment Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Development Flow                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Feature Branch                                                    │
│        │                                                            │
│        │  PR opened                                                 │
│        ▼                                                            │
│   ┌─────────────┐                                                   │
│   │  PR Checks  │  (lint, test, docker)                             │
│   └──────┬──────┘                                                   │
│          │ approved & merged                                        │
│          ▼                                                          │
│   ┌─────────────┐                                                   │
│   │  dev branch │                                                   │
│   └──────┬──────┘                                                   │
│          │ auto-deploy                                              │
│          ▼                                                          │
│   ┌─────────────────────┐                                           │
│   │  Staging Deploy     │  → https://v0agent-staging.up.railway.app │
│   └──────┬──────────────┘                                           │
│          │                                                          │
│          │ validated & merged to main                               │
│          ▼                                                          │
│   ┌─────────────┐                                                   │
│   │ main branch │                                                   │
│   └──────┬──────┘                                                   │
│          │ CI checks pass                                           │
│          ▼                                                          │
│   ┌─────────────────────┐                                           │
│   │ Manual Approval     │  (GitHub environment protection)          │
│   └──────┬──────────────┘                                           │
│          │ approved                                                 │
│          ▼                                                          │
│   ┌──────────────────────┐                                          │
│   │  Production Deploy   │ → https://v0agent-production.up.railway.app│
│   └──────────────────────┘                                          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Setting Up Environment Protection

1. Go to GitHub Repository → Settings → Environments
2. Create `production` environment
3. Enable "Required reviewers" protection rule
4. Add required reviewers (e.g., yourself or team leads)
5. Optionally enable "Wait timer" for additional safety

## Local Development Workflow

```bash
# 1. Create feature branch from dev
git checkout dev
git pull origin dev
git checkout -b feature/my-feature

# 2. Make changes and commit
git add -A
git commit -m "feat: my new feature"

# 3. Push and create PR to dev
git push origin feature/my-feature
# Create PR in GitHub

# 4. After PR is merged to dev
#    - Auto-deploys to staging
#    - Validate at https://v0agent-staging.up.railway.app

# 5. Create PR from dev to main
#    - Run tests
#    - Get approval
#    - Merge triggers production deploy

# 6. Merge to main
git checkout main
git pull origin main
# Create PR from dev → main in GitHub
```

## Manual Deployment (Emergency)

```bash
# Deploy to staging
railway link c32f6be2-fe5d-4750-9195-00f9995c7c92 --environment staging
railway up

# Deploy to production
railway link c32f6be2-fe5d-4750-9195-00f9995c7c92 --environment production
railway up
```

## Monitoring

### Health Endpoints
- Staging: https://v0agent-staging.up.railway.app/health
- Production: https://v0agent-production.up.railway.app/health

### Logs
```bash
# View staging logs
railway link c32f6be2-fe5d-4750-9195-00f9995c7c92 --environment staging
railway logs

# View production logs
railway link c32f6be2-fe5d-4750-9195-00f9995c7c92 --environment production
railway logs
```

## Rollback Procedure

If a production deployment fails:

1. **Via GitHub**: Revert the merge commit and push to main
2. **Via Railway CLI**:
   ```bash
   railway link c32f6be2-fe5d-4750-9195-00f9995c7c92 --environment production
   railway rollback
   ```
3. **Via Railway Dashboard**: Go to Deployments → Select previous successful deployment → Redeploy

## Troubleshooting

### CI Checks Failing
1. Check GitHub Actions tab for detailed logs
2. Run locally: `ruff check src/` and `pytest tests/`

### Deployment Health Check Failing
1. Check Railway logs: `railway logs --environment <env>`
2. Verify environment variables are set
3. Check if Supabase is accessible

### Manual Trigger Not Working
1. Ensure RAILWAY_TOKEN secret is set in GitHub
2. Check workflow permissions in repository settings
