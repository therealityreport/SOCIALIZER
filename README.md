# SOCIALIZER - LiveThread Sentiment for Reddit (LTSR)

Real-time, cast-specific sentiment analysis for Reddit live episode threads with vote-weighted aggregation and integrity monitoring.

## 🎯 Project Overview

SOCIALIZER (LTSR) is a production-grade sentiment analysis platform designed specifically for Reddit live discussion threads, with deep expertise in reality TV discourse (Bravo shows). It provides:

- **Real-time monitoring** during live episodes (30-60s refresh)
- **Cast-level analytics** with vote-weighted sentiment
- **Integrity diagnostics** (brigading detection, bot identification)
- **Multi-task AI** (sentiment + sarcasm + toxicity)
- **Time intelligence** (Live/Day-Of/After windows)

## 📚 Documentation

- **[PRD.md](docs/PRD.md)** - Complete Product Requirements Document (Executive Summary - full version in artifact)
- **[DIRECTORY_STRUCTURE.md](docs/DIRECTORY_STRUCTURE.md)** - Complete project structure and organization
- **[TECH_STACK.md](docs/TECH_STACK.md)** - Technical specifications and development stack
- **[BranchingStrategy.md](docs/BranchingStrategy.md)** - Git workflow and protection rules
- **[EnvironmentVariables.md](docs/EnvironmentVariables.md)** - Full environment variable reference

> **Note**: The full 95,000-word PRD is available in the Claude artifact. The docs/PRD.md file contains the executive summary and table of contents.

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 20+
- Docker 24+
- PostgreSQL 15+
- Redis 7+

### Setup

```bash
# Clone repository
git clone https://github.com/your-org/socializer.git
cd socializer

# Copy base environment file and adjust as needed
cp .env.example .env
# Required for Instagram ingestion: set `APIFY_TOKEN` in `.env` to an Apify API token that can run `apify/instagram-profile-scraper`.

# Backend dependencies
python -m venv .venv
source .venv/bin/activate
pip install -r src/backend/requirements/dev.txt

# Frontend dependencies
npm install --prefix src/frontend

# Launch the local stack (FastAPI, Vite, Celery worker, Flower, Postgres, Redis)
docker compose up --build

# Apply database migrations once the containers are running
docker compose exec backend alembic upgrade head

```

> **Heads up:** The sentiment pipeline now relies on `transformers`, `torch`, and `azure-ai-textanalytics`; these are included in the updated backend requirements file.

### Access Points
- **Backend API**: http://localhost:8000
- **Frontend Dashboard**: http://localhost:5173
- **API Documentation**: http://localhost:8000/docs
- **Celery Flower** (Task Monitor): http://localhost:5555

## 🌐 Staging Deployment

Ready to move past local development? Follow the [Staging Deployment Guide](docs/deployment/STAGING_SETUP.md) for TLS termination, staging configuration, and baseline monitoring using the `docker-compose.staging.yml` override.

## 🧰 Workflow Tooling

- **Celery Flower** ships in the default stack (`http://localhost:5555`) for queue monitoring.
- **Bulk ingestion**: `python scripts/bulk_enqueue_threads.py threads.txt --subreddit BravoRealHousewives` enqueues every Reddit thread in the file; pass `--dry-run` to preview.
- **Instagram ingest**: Visit `/instagram/ingest` to run Apify pulls with hashtag/date filters once `APIFY_TOKEN` is configured.

## 🏗️ Architecture

```
SOCIALIZER/
├── src/
│   ├── backend/        # FastAPI application
│   ├── frontend/       # React + TypeScript dashboard
│   ├── ml/             # Machine learning models (RoBERTa-large)
│   └── scripts/        # Utility scripts
├── tests/              # Test suite
├── config/             # Configuration files
├── data/               # Data storage
├── infra/              # Infrastructure as code
└── docs/               # Documentation
```

## 🔑 Key Features

### Analytics
- **Per-Cast**: Share of voice, sentiment trajectory, topic clusters, controversy metrics
- **Episode**: Overall sentiment, engagement curves, moment detection
- **Audience**: New vs returning, super-commenters, locale proxies
- **Language**: Slang tracking (200+ terms), emoji analysis, comparatives

### Integrity
- **Brigading Detection**: Cross-sub influx, synchronized voting patterns
- **Bot Identification**: Account age, activity bursts, repetition patterns
- **Score Reliability**: Provisional vs final results (handles Reddit's score hiding)

### Real-Time
- **30-60s Dashboard Refresh**: WebSocket-based updates
- **Alerts**: Slack/email notifications for sentiment drops
- **Live Monitoring**: Active during episode air windows (T0-1h to T0+3h)

## 🧠 Machine Learning

### Model Architecture
- **Primary**: `cardiffnlp/twitter-roberta-base-topic-sentiment-latest` (Hugging Face)
- **Fallback**: Azure Text Analytics Opinion Mining (aspect-level sentiment when confidence is low)
- **Tasks**: Sentiment (3-class) + Sarcasm (binary) + Toxicity (binary)
- **Training**: 50K-100K labeled comments with active learning
- **Accuracy**: ≥80% sentiment, ≥70% sarcasm F1

### Pipeline Flow
- **Pre-processing**: Entity linker detects cast mentions & aliases
- **Primary Inference**: Hugging Face model assigns comment & mention sentiment, logging scores/source
- **Fallback Trigger**: Confidence `< 0.75` or inference error invokes Azure Opinion Mining
- **Normalization**: Outputs unified as `{cast_member, sentiment_label, sentiment_score, source_model}`

### Domain Expertise
- **Slang Lexicon**: 200+ Bravo/reality TV terms ("ate", "served", "dragged", "flop")
- **Sarcasm Detection**: Multi-signal approach with context windows
- **Entity Linking**: Fuzzy matching for cast names, nicknames, misspellings

## 🔐 Privacy & Security

- **GDPR/CCPA Compliant**: 30-day raw data retention, right to deletion
- **Reddit TOS Compliant**: Enterprise API agreement, no foundation model training
- **Data Minimization**: Username hashing only, no cross-platform linking
- **Encryption**: AES-256 at rest, TLS 1.3 in transit

## 📊 Tech Stack

### Backend
- Python 3.11 + FastAPI + Celery
- PostgreSQL 15 + Redis 7
- PyTorch 2.1 + Hugging Face Transformers

### Frontend
- React 18 + TypeScript + Vite
- Tailwind CSS + shadcn/ui
- Recharts + WebSocket

### Infrastructure
- Docker + Kubernetes
- AWS (or GCP)
- GitHub Actions CI/CD

## 📈 Success Metrics

- **Coverage**: ≥95% of comments fetched
- **Accuracy**: ≥80% sentiment, ≥90% cast mention F1
- **Latency**: <60s for 2K-comment thread
- **Adoption**: 30+ threads/month, 40+ active users by Month 6
- **Impact**: 3-10+ documented decisions/month, 80+ hours saved/month

## 🛣️ Roadmap

### MVP (Week 6)
- Single-thread analysis
- Per-cast sentiment cards
- Day-Of vs After split
- CSV export

### V1 (Week 12)
- Real-time dashboard
- Timeline charts
- Email/Slack alerts
- Integrity panel

### V2 (Week 20-22)
- Multi-thread comparison
- Topic mining
- API access
- PowerPoint exports

## 🧪 Testing

```bash
# Run all tests
./scripts/run_tests.sh

# Run specific test suite
pytest tests/unit/
pytest tests/integration/
pytest tests/e2e/

# Coverage report
pytest --cov=src/ --cov-report=html
```

## ⏱️ Task Time Tracking

- Use `python3 scripts/task_time_tracker.py start <TASK_ID>` to begin timing (e.g., `INFRA-001`).
- Stop with `python3 scripts/task_time_tracker.py stop <TASK_ID>` and view active timers via `python3 scripts/task_time_tracker.py active`.
- Generate summaries per phase with `python3 scripts/task_time_tracker.py summary`, optionally exporting to Markdown via `--output docs/TaskTimeLog.md`.
- Raw timing data is persisted to `data/processed/task_time_tracking.json` so the whole team can share accurate phase durations.

## 📝 License

[To be determined]

## 🤝 Contributing

See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines.

## 📞 Contact

- **Product Team**: product@[company].com
- **Engineering**: engineering@[company].com
- **Support**: support@[company].com

## 🙏 Acknowledgments

- Reddit API for data access
- Hugging Face for transformer models
- Open source community

---

**Version**: 1.0  
**Last Updated**: October 16, 2025  
**Status**: Development Phase - Documentation Complete
# SOCIALIZER
