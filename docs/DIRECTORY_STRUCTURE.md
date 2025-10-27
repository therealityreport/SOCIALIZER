# SOCIALIZER Directory Structure

## Overview
This document outlines the complete directory structure for the SOCIALIZER project (LiveThread Sentiment for Reddit - LTSR).

## Root Directory Structure

```
SOCIALIZER/
├── README.md                          # Project overview and quick start
├── LICENSE                            # Software license
├── .gitignore                        # Git ignore patterns
├── .env.example                      # Environment variables template
├── docker-compose.yml                # Docker orchestration
├── Makefile                          # Build and deployment commands
│
├── docs/                             # Documentation
│   ├── PRD.md                        # Complete Product Requirements Document
│   ├── DIRECTORY_STRUCTURE.md        # This file
│   ├── TECH_STACK.md                 # Technical specifications
│   ├── API_DOCUMENTATION.md          # API reference
│   ├── USER_GUIDE.md                 # End-user documentation
│   ├── DEPLOYMENT_GUIDE.md           # Deployment instructions
│   ├── PRIVACY_POLICY.md             # Privacy policy
│   ├── TERMS_OF_SERVICE.md           # Terms of service
│   └── CONTRIBUTING.md               # Contribution guidelines
│
├── src/                              # Source code
│   ├── backend/                      # Backend application
│   ├── frontend/                     # Frontend application
│   ├── ml/                           # Machine learning models
│   └── scripts/                      # Utility scripts
│
├── tests/                            # Test suite
│   ├── unit/                         # Unit tests
│   ├── integration/                  # Integration tests
│   ├── e2e/                          # End-to-end tests
│   └── fixtures/                     # Test data and fixtures
│
├── config/                           # Configuration files
│   ├── dev/                          # Development environment
│   ├── staging/                      # Staging environment
│   └── production/                   # Production environment
│
├── data/                             # Data storage
│   ├── raw/                          # Raw Reddit JSON responses
│   ├── processed/                    # Processed data
│   ├── models/                       # Trained model files
│   └── cache/                        # Cache files
│
├── infra/                            # Infrastructure as code
│   ├── terraform/                    # Terraform configurations
│   ├── kubernetes/                   # Kubernetes manifests
│   └── ansible/                      # Ansible playbooks
│
└── scripts/                          # Project scripts
    ├── setup.sh                      # Initial setup
    ├── migrate.sh                    # Database migrations
    └── deploy.sh                     # Deployment script
```

## Detailed Structure

### Backend (`src/backend/`)

```
src/backend/
├── __init__.py
├── main.py                           # FastAPI application entry
├── config.py                         # Configuration management
├── requirements.txt                  # Python dependencies
├── Dockerfile                        # Docker image
│
├── api/                              # API layer
│   ├── __init__.py
│   ├── routes/                       # API routes
│   │   ├── __init__.py
│   │   ├── threads.py               # Thread endpoints
│   │   ├── cast.py                  # Cast-specific endpoints
│   │   ├── exports.py               # Export endpoints
│   │   ├── admin.py                 # Admin endpoints
│   │   └── health.py                # Health check endpoints
│   ├── schemas/                     # Pydantic models
│   │   ├── __init__.py
│   │   ├── thread.py
│   │   ├── cast.py
│   │   ├── comment.py
│   │   └── analytics.py
│   ├── dependencies.py              # Dependency injection
│   └── middleware.py                # Custom middleware
│
├── core/                            # Core business logic
│   ├── __init__.py
│   ├── ingestion/                   # Reddit API ingestion
│   │   ├── __init__.py
│   │   ├── reddit_client.py        # Reddit API wrapper
│   │   ├── rate_limiter.py         # Rate limiting logic
│   │   └── parser.py               # JSON parsing
│   ├── processing/                  # Data processing
│   │   ├── __init__.py
│   │   ├── normalizer.py           # Text normalization
│   │   ├── entity_linker.py        # Cast entity linking
│   │   ├── aggregator.py           # Vote-weighted aggregation
│   │   └── time_slicer.py          # Time window assignment
│   ├── analytics/                   # Analytics generation
│   │   ├── __init__.py
│   │   ├── cast_analytics.py       # Per-cast metrics
│   │   ├── episode_analytics.py    # Episode metrics
│   │   ├── audience_analytics.py   # Audience segmentation
│   │   └── integrity.py            # Brigading/bot detection
│   └── alerts/                      # Alert engine
│       ├── __init__.py
│       ├── triggers.py             # Alert conditions
│       └── notifiers.py            # Slack/email notifications
│
├── models/                          # Database models
│   ├── __init__.py
│   ├── thread.py                   # Thread model
│   ├── comment.py                  # Comment model
│   ├── mention.py                  # Mention model
│   ├── aggregate.py                # Aggregate model
│   └── user.py                     # User model
│
├── services/                        # Service layer
│   ├── __init__.py
│   ├── thread_service.py           # Thread operations
│   ├── analytics_service.py        # Analytics operations
│   ├── export_service.py           # Export generation
│   └── cache_service.py            # Redis caching
│
├── workers/                         # Background workers
│   ├── __init__.py
│   ├── celery_app.py               # Celery configuration
│   ├── tasks.py                    # Celery tasks
│   └── scheduler.py                # Scheduled jobs
│
├── db/                              # Database
│   ├── __init__.py
│   ├── session.py                  # Database session
│   ├── migrations/                 # Alembic migrations
│   │   ├── versions/
│   │   └── env.py
│   └── seeds/                      # Seed data
│       └── cast_dictionary.json
│
└── utils/                           # Utilities
    ├── __init__.py
    ├── logger.py                   # Logging configuration
    ├── errors.py                   # Custom exceptions
    └── helpers.py                  # Helper functions
```

### Frontend (`src/frontend/`)

```
src/frontend/
├── package.json                     # Node dependencies
├── tsconfig.json                    # TypeScript config
├── vite.config.ts                   # Vite bundler config
├── tailwind.config.js               # Tailwind CSS config
├── Dockerfile                       # Docker image
├── .eslintrc.js                     # ESLint config
│
├── public/                          # Static assets
│   ├── favicon.ico
│   ├── logo.svg
│   └── robots.txt
│
└── src/
    ├── main.tsx                     # React entry point
    ├── App.tsx                      # Root component
    ├── index.css                    # Global styles
    │
    ├── components/                  # React components
    │   ├── shared/                  # Shared components
    │   │   ├── Button.tsx
    │   │   ├── Card.tsx
    │   │   ├── Spinner.tsx
    │   │   └── Modal.tsx
    │   ├── layout/                  # Layout components
    │   │   ├── Header.tsx
    │   │   ├── Sidebar.tsx
    │   │   └── Footer.tsx
    │   ├── dashboard/               # Dashboard components
    │   │   ├── EpisodeOverview.tsx
    │   │   ├── CastGrid.tsx
    │   │   ├── TimelineChart.tsx
    │   │   └── MomentDetection.tsx
    │   ├── cast/                    # Cast-specific components
    │   │   ├── CastCard.tsx
    │   │   ├── CastDeepDive.tsx
    │   │   ├── TopicClusters.tsx
    │   │   └── Trajectory.tsx
    │   ├── integrity/               # Integrity panel
    │   │   ├── BrigadingAlert.tsx
    │   │   ├── BotDetection.tsx
    │   │   └── ScoreReliability.tsx
    │   └── admin/                   # Admin components
    │       ├── CastRoster.tsx
    │       ├── ModelVersions.tsx
    │       └── UserManagement.tsx
    │
    ├── pages/                       # Page components
    │   ├── Dashboard.tsx
    │   ├── ThreadAnalysis.tsx
    │   ├── CastDetails.tsx
    │   ├── AudienceInsights.tsx
    │   ├── LanguageInsights.tsx
    │   ├── IntegrityPanel.tsx
    │   └── Admin.tsx
    │
    ├── hooks/                       # Custom React hooks
    │   ├── useThread.ts
    │   ├── useCast.ts
    │   ├── useWebSocket.ts
    │   └── useAuth.ts
    │
    ├── services/                    # API services
    │   ├── api.ts                   # Axios instance
    │   ├── threadService.ts
    │   ├── castService.ts
    │   ├── exportService.ts
    │   └── adminService.ts
    │
    ├── store/                       # State management
    │   ├── index.ts                 # Store configuration
    │   ├── slices/                  # Zustand slices
    │   │   ├── threadSlice.ts
    │   │   ├── castSlice.ts
    │   │   └── uiSlice.ts
    │   └── types.ts                 # Type definitions
    │
    ├── utils/                       # Utility functions
    │   ├── formatters.ts            # Data formatters
    │   ├── validators.ts            # Input validation
    │   └── constants.ts             # Constants
    │
    └── types/                       # TypeScript types
        ├── thread.ts
        ├── cast.ts
        └── analytics.ts
```

### Machine Learning (`src/ml/`)

```
src/ml/
├── __init__.py
├── requirements.txt                 # ML dependencies
├── Dockerfile                       # Docker image
│
├── models/                          # Model code
│   ├── __init__.py
│   ├── roberta_multitask.py        # RoBERTa multi-task model
│   ├── entity_linker.py            # Cast entity linker
│   └── lexicon.py                  # Slang lexicon
│
├── training/                        # Training scripts
│   ├── __init__.py
│   ├── train_sentiment.py          # Sentiment training
│   ├── train_sarcasm.py            # Sarcasm training
│   ├── train_multitask.py          # Multi-task training
│   └── active_learning.py          # Active learning loop
│
├── evaluation/                      # Evaluation scripts
│   ├── __init__.py
│   ├── evaluate.py                 # Model evaluation
│   ├── regression_tests.py         # Edge case tests
│   └── benchmark.py                # Benchmarking
│
├── inference/                       # Inference server
│   ├── __init__.py
│   ├── server.py                   # FastAPI inference server
│   └── batch_inference.py          # Batch processing
│
├── data/                            # Data processing
│   ├── __init__.py
│   ├── preprocessing.py            # Text preprocessing
│   ├── augmentation.py             # Data augmentation
│   └── annotation.py               # Annotation tools
│
└── notebooks/                       # Jupyter notebooks
    ├── exploratory_analysis.ipynb
    ├── model_experiments.ipynb
    └── error_analysis.ipynb
```

### Tests (`tests/`)

```
tests/
├── __init__.py
├── conftest.py                      # Pytest fixtures
│
├── unit/                            # Unit tests
│   ├── __init__.py
│   ├── test_normalizer.py
│   ├── test_entity_linker.py
│   ├── test_aggregator.py
│   ├── test_weighting.py
│   └── test_time_slicer.py
│
├── integration/                     # Integration tests
│   ├── __init__.py
│   ├── test_api.py
│   ├── test_ingestion.py
│   ├── test_processing_pipeline.py
│   └── test_database.py
│
├── e2e/                             # End-to-end tests
│   ├── __init__.py
│   ├── test_thread_analysis.py
│   └── test_export.py
│
└── fixtures/                        # Test data
    ├── reddit_responses/
    │   ├── thread_sample.json
    │   └── comments_sample.json
    ├── cast_dictionary.json
    └── gold_labels.json
```

### Config (`config/`)

```
config/
├── dev/
│   ├── .env                         # Development environment vars
│   ├── docker-compose.yml           # Dev docker compose
│   └── redis.conf                   # Redis configuration
│
├── staging/
│   ├── .env
│   ├── kubernetes/                  # K8s manifests
│   └── nginx.conf
│
└── production/
    ├── .env
    ├── kubernetes/
    └── nginx.conf
```

### Infrastructure (`infra/`)

```
infra/
├── terraform/                       # Infrastructure as code
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── modules/
│   │   ├── vpc/
│   │   ├── rds/
│   │   ├── ecs/
│   │   └── s3/
│   └── environments/
│       ├── dev/
│       ├── staging/
│       └── production/
│
├── kubernetes/                      # K8s configurations
│   ├── backend/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   └── ingress.yaml
│   ├── frontend/
│   ├── ml/
│   └── workers/
│
└── ansible/                         # Configuration management
    ├── playbooks/
    │   ├── setup.yml
    │   └── deploy.yml
    └── roles/
        ├── common/
        ├── backend/
        └── frontend/
```

### Scripts (`scripts/`)

```
scripts/
├── setup.sh                         # Initial project setup
├── install_dependencies.sh          # Install all dependencies
├── run_dev.sh                       # Start development servers
├── run_tests.sh                     # Run test suite
├── migrate.sh                       # Run database migrations
├── seed_data.sh                     # Seed initial data
├── backup.sh                        # Backup database
├── deploy.sh                        # Deploy to environment
├── monitor.sh                       # Check service health
└── cleanup.sh                       # Clean temporary files
```

## File Naming Conventions

### General Rules
- **Python**: `snake_case.py`
- **TypeScript/React**: `PascalCase.tsx` for components, `camelCase.ts` for utilities
- **Configuration**: `lowercase.config.js` or `UPPERCASE.md`
- **Tests**: `test_*.py` or `*.test.ts`

### Directory Names
- All lowercase with hyphens for multi-word names (not common in this project)
- Plural for collections: `models/`, `services/`, `tests/`

## Data Storage

### Database (PostgreSQL)
- `threads` - Thread metadata
- `comments` - Normalized comments (30-day retention)
- `mentions` - Cast mentions with sentiment
- `aggregates` - Computed analytics (2-year retention)
- `users` - LTSR users
- `model_versions` - Model tracking

### Object Storage (S3/GCS)
- `raw/` - Raw Reddit JSON (30 days)
- `exports/` - Generated exports (7 days)
- `models/` - Trained model checkpoints
- `backups/` - Database backups

### Cache (Redis)
- Thread metadata (15-min TTL)
- Computed aggregates (5-min TTL)
- Rate limit counters
- WebSocket pub/sub channels

## Environment Variables

Required environment variables (see `.env.example`):

```bash
# Application
ENV=development                      # development | staging | production
DEBUG=true
SECRET_KEY=your-secret-key

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/ltsr
DATABASE_POOL_SIZE=20

# Redis
REDIS_URL=redis://localhost:6379/0

# Reddit API
REDDIT_CLIENT_ID=your-client-id
REDDIT_CLIENT_SECRET=your-secret
REDDIT_USER_AGENT=LTSR/1.0

# Object Storage
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_S3_BUCKET=ltsr-data

# ML Model
MODEL_PATH=/data/models/roberta-multitask-v2025.03.1

# Monitoring
SENTRY_DSN=your-sentry-dsn
DATADOG_API_KEY=your-datadog-key

# Alerts
SLACK_WEBHOOK_URL=your-slack-webhook
SENDGRID_API_KEY=your-sendgrid-key
```

## Version Control

### Git Branching Strategy
- `main` - Production-ready code
- `develop` - Integration branch
- `feature/*` - Feature branches
- `bugfix/*` - Bug fix branches
- `release/*` - Release preparation

### Ignored Files (`.gitignore`)
```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/

# Node
node_modules/
dist/
build/

# Environment
.env
.env.local

# Data
/data/raw/
/data/cache/
*.csv
*.json (except configs)

# Models
*.pth
*.pt
*.ckpt

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db
```

## Documentation Standards

### Code Documentation
- **Python**: Google-style docstrings
- **TypeScript**: JSDoc comments
- **Functions**: Purpose, parameters, returns, examples
- **Classes**: Purpose, attributes, methods

### README Files
Each major directory should have a `README.md`:
- Purpose of the directory
- Key files and their roles
- How to run/test components
- Dependencies

## Development Workflow

1. **Setup**: Run `scripts/setup.sh`
2. **Install**: Run `scripts/install_dependencies.sh`
3. **Configure**: Copy `.env.example` to `.env`, fill in values
4. **Migrate**: Run `scripts/migrate.sh`
5. **Seed**: Run `scripts/seed_data.sh`
6. **Develop**: Run `scripts/run_dev.sh`
7. **Test**: Run `scripts/run_tests.sh`
8. **Deploy**: Run `scripts/deploy.sh <environment>`

## Deployment Structure

### Development
- Local Docker Compose
- Hot reload enabled
- Debug logging
- Mock Reddit API for testing

### Staging
- AWS ECS or Kubernetes
- Replica of production config
- Lower resource limits
- Synthetic data testing

### Production
- Multi-AZ deployment
- Auto-scaling enabled
- Full monitoring
- Blue-green deployments

## Monitoring & Logging

### Log Locations
- Application: `/var/log/ltsr/app.log`
- Access: `/var/log/ltsr/access.log`
- Errors: `/var/log/ltsr/error.log`
- Celery: `/var/log/ltsr/celery.log`

### Metrics
- Datadog dashboards
- Prometheus + Grafana
- CloudWatch (AWS)
- Custom application metrics

---

**Last Updated**: October 16, 2025  
**Version**: 1.0  
**Maintained By**: Product & Engineering Teams
