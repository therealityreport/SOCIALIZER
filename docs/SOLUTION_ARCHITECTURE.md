# SOCIALIZER Solution Architecture
## LiveThread Sentiment for Reddit (LTSR) - Complete System Design

**Version**: 1.0  
**Last Updated**: October 16, 2025  
**Status**: Production-Ready Design

---

## Table of Contents

1. [Executive Overview](#1-executive-overview)
2. [Architecture Principles](#2-architecture-principles)
3. [High-Level Architecture](#3-high-level-architecture)
4. [Component Architecture](#4-component-architecture)
5. [Data Architecture](#5-data-architecture)
6. [Integration Architecture](#6-integration-architecture)
7. [Security Architecture](#7-security-architecture)
8. [Deployment Architecture](#8-deployment-architecture)
9. [Scalability & Performance](#9-scalability--performance)
10. [Disaster Recovery](#10-disaster-recovery)
11. [Monitoring & Observability](#11-monitoring--observability)
12. [Decision Log](#12-decision-log)

---

## 1. Executive Overview

### 1.1 Purpose

This document describes the complete solution architecture for the SOCIALIZER platform (LTSR), a real-time sentiment analysis system for Reddit live discussion threads with specialized focus on reality TV content.

### 1.2 Architecture Goals

- **Real-time Processing**: Analyze threads with <60s latency during live episodes
- **High Availability**: 99.9% uptime SLA
- **Scalability**: Handle 10-50 concurrent thread analyses
- **Data Privacy**: GDPR/CCPA compliant with 30-day retention
- **Cost Efficiency**: Optimize Reddit API usage and infrastructure costs
- **Maintainability**: Modular design with clear separation of concerns

### 1.3 Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Backend Framework** | FastAPI | Async support, auto-docs, high performance |
| **Frontend Framework** | React + TypeScript | Component reusability, type safety, ecosystem |
| **Database** | PostgreSQL | ACID compliance, JSON support, partitioning |
| **Cache** | Redis | In-memory speed, pub/sub for WebSocket |
| **Task Queue** | Celery + Redis | Mature, Python-native, retry logic |
| **ML Framework** | PyTorch + Transformers | Industry standard, pre-trained models |
| **Container Platform** | Docker + Kubernetes | Portability, orchestration, scaling |
| **Cloud Provider** | AWS (Primary) | Mature services, global presence |

---

## 2. Architecture Principles

### 2.1 Core Principles

#### Separation of Concerns
- **API Layer**: Request handling, validation, authentication
- **Business Logic**: Domain logic, orchestration
- **Data Layer**: Persistence, caching
- **Integration Layer**: External APIs, third-party services

#### Scalability by Design
- **Horizontal Scaling**: Stateless services, containerized
- **Vertical Scaling**: Database read replicas, cache layers
- **Asynchronous Processing**: Background jobs for heavy computation
- **Rate Limiting**: Protect against overload

#### Security First
- **Zero Trust**: Authenticate and authorize every request
- **Encryption**: At rest (AES-256) and in transit (TLS 1.3)
- **Least Privilege**: Minimal permissions for each component
- **Defense in Depth**: Multiple security layers

#### Observability
- **Logging**: Structured JSON logs with correlation IDs
- **Metrics**: Application and business metrics
- **Tracing**: Distributed tracing across services
- **Alerting**: Proactive issue detection

### 2.2 Design Patterns

#### Microservices-Oriented (with pragmatic monolith)
- **Phase 1 (MVP)**: Modular monolith for speed
- **Phase 2 (V1+)**: Extract high-load services (ML inference)
- **Phase 3 (V2+)**: Full microservices as needed

#### Event-Driven Architecture
- **Celery Tasks**: Background processing
- **Redis Pub/Sub**: Real-time WebSocket updates
- **Webhooks**: External integrations (Slack)

#### CQRS Lite (Command Query Responsibility Segregation)
- **Write Path**: API → Celery → Database
- **Read Path**: API → Cache → Database (read replica)
- **Optimization**: Separate read/write models where beneficial

---

## 3. High-Level Architecture

### 3.1 System Context Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL ACTORS                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  [Network Teams]  [Showrunners]  [PR Teams]  [Moderators]          │
│        │               │              │            │                 │
│        └───────────────┴──────────────┴────────────┘                │
│                           │                                          │
│                           ▼                                          │
│                  ┌─────────────────┐                                │
│                  │  Web Dashboard  │                                │
│                  │  (React SPA)    │                                │
│                  └────────┬────────┘                                │
│                           │                                          │
│                           │ HTTPS/WSS                                │
└───────────────────────────┼──────────────────────────────────────────┘
                            │
┌───────────────────────────┼──────────────────────────────────────────┐
│                           ▼              LTSR PLATFORM               │
│                  ┌─────────────────┐                                │
│                  │   API Gateway   │                                │
│                  │   (FastAPI)     │                                │
│                  └────────┬────────┘                                │
│                           │                                          │
│         ┌─────────────────┼─────────────────┐                       │
│         ▼                 ▼                 ▼                        │
│  ┌────────────┐   ┌────────────┐   ┌────────────┐                 │
│  │ Ingestion  │   │ Processing │   │ Analytics  │                  │
│  │  Service   │   │  Service   │   │  Service   │                  │
│  └─────┬──────┘   └─────┬──────┘   └─────┬──────┘                 │
│        │                │                │                           │
│        └────────────────┼────────────────┘                          │
│                         │                                            │
│         ┌───────────────┼───────────────┐                           │
│         ▼               ▼               ▼                            │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                   │
│  │ PostgreSQL │  │   Redis    │  │    S3      │                    │
│  │ (Primary)  │  │  (Cache)   │  │ (Storage)  │                    │
│  └────────────┘  └────────────┘  └────────────┘                    │
│                                                                      │
│         ┌──────────────────────────────────┐                        │
│         │      ML Inference Service        │                        │
│         │  (RoBERTa-large Multi-Task)      │                        │
│         └──────────────────────────────────┘                        │
└──────────────────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────┼──────────────────────────────────────────┐
│                           ▼         EXTERNAL SERVICES                │
│                                                                       │
│  [Reddit API]  [Auth0]  [SendGrid]  [Slack]  [Datadog]  [Sentry]   │
└───────────────────────────────────────────────────────────────────────┘
```

### 3.2 Logical Architecture

```
┌───────────────────────────────────────────────────────────────────────┐
│                         PRESENTATION LAYER                            │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  React Dashboard (TypeScript)                                    │ │
│  │  - Episode Overview │ Cast Details │ Integrity Panel │ Admin    │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└─────────────────────────┬─────────────────────────────────────────────┘
                          │
                          │ REST API / WebSocket
                          │
┌─────────────────────────▼─────────────────────────────────────────────┐
│                        APPLICATION LAYER                              │
│  ┌──────────────────────────────────────────────────────────────────┐│
│  │  API Gateway (FastAPI)                                           ││
│  │  - Authentication │ Authorization │ Rate Limiting │ Validation   ││
│  └──────────────────────────────────────────────────────────────────┘│
│  ┌──────────────────────────────────────────────────────────────────┐│
│  │  Business Logic Layer                                            ││
│  │  - Thread Service │ Cast Service │ Analytics Service │ Export   ││
│  └──────────────────────────────────────────────────────────────────┘│
│  ┌──────────────────────────────────────────────────────────────────┐│
│  │  Background Workers (Celery)                                     ││
│  │  - Ingestion │ ML Inference │ Aggregation │ Alerts │ Cleanup    ││
│  └──────────────────────────────────────────────────────────────────┘│
└─────────────────────────┬─────────────────────────────────────────────┘
                          │
┌─────────────────────────▼─────────────────────────────────────────────┐
│                        PROCESSING LAYER                               │
│                                                                        │
│  Data Ingest → Pre-processing → LLM Sentiment Engine →                │
│                                          ↓                             │
│                                   Signal Extractor → Storage →         │
│                                          ↓                             │
│                                     Aggregation                        │
│                                                                        │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  Provider Evaluation Loop (Automated)                          │  │
│  │                                                                 │  │
│  │  Benchmark → Provider Selection → Active Provider →            │  │
│  │      ↑              ↓                      ↓                    │  │
│  │      │         Config Update          Production               │  │
│  │      │              ↓                      ↓                    │  │
│  │      └─────── Drift QA Monitor ←─────────┘                     │  │
│  │              (Weekly Check)                                     │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  LLM Analysis Path (Semantic Interpretation)                   │  │
│  │  • Primary Sentiment (Positive/Neutral/Negative)               │  │
│  │  • Secondary Attitude (Admiration, Shady, Analytical, etc.)    │  │
│  │  • Emotion Extraction (joy, amusement, disgust, etc.)          │  │
│  │  • Sarcasm Detection (score, label, evidence)                  │  │
│  │  • Provider: OpenAI | Anthropic | Gemini (auto-selected)       │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  Computation Path (Rule-Based Metrics)                         │  │
│  │  • Emoji count & polarity                                      │  │
│  │  • GIF/image/video/domain detection                            │  │
│  │  • Hashtags, punctuation, ALL-CAPS, negations, questions       │  │
│  │  • Engagement metrics (upvotes, replies, velocity, awards)     │  │
│  │  • Controversy index, share of voice, co-mentions              │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │  Reddit          │  │  Entity          │  │  Vote-Weighted   │  │
│  │  Ingestion       │  │  Linking         │  │  Aggregation     │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │  Time            │  │  Integrity       │  │  Signal          │  │
│  │  Slicing         │  │  Detection       │  │  Extraction      │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
└─────────────────────────┬─────────────────────────────────────────────┘
                          │
┌─────────────────────────▼─────────────────────────────────────────────┐
│                          DATA LAYER                                   │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │  PostgreSQL      │  │  Redis           │  │  S3 / GCS        │  │
│  │  - Threads       │  │  - Cache         │  │  - Raw JSON      │  │
│  │  - Comments      │  │  - Queue         │  │  - Models        │  │
│  │  - Aggregates    │  │  - Pub/Sub       │  │  - Exports       │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
└───────────────────────────────────────────────────────────────────────┘
```

---

## 4. Component Architecture

### 4.1 API Gateway (FastAPI)

#### 4.1.1 Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI Application                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │              Middleware Stack                           │    │
│  │  ┌──────────────────────────────────────────────────┐  │    │
│  │  │  CORS Middleware                                  │  │    │
│  │  └──────────────────────────────────────────────────┘  │    │
│  │  ┌──────────────────────────────────────────────────┐  │    │
│  │  │  Authentication Middleware (JWT Validation)      │  │    │
│  │  └──────────────────────────────────────────────────┘  │    │
│  │  ┌──────────────────────────────────────────────────┐  │    │
│  │  │  Rate Limiting Middleware                        │  │    │
│  │  └──────────────────────────────────────────────────┘  │    │
│  │  ┌──────────────────────────────────────────────────┐  │    │
│  │  │  Logging Middleware (Request/Response)           │  │    │
│  │  └──────────────────────────────────────────────────┘  │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │                  API Routes                             │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │    │
│  │  │  /threads    │  │  /cast       │  │  /exports   │ │    │
│  │  │  - POST      │  │  - GET       │  │  - POST     │ │    │
│  │  │  - GET       │  │  - GET /:id  │  │  - GET      │ │    │
│  │  │  - GET /:id  │  └──────────────┘  └─────────────┘ │    │
│  │  └──────────────┘                                      │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │    │
│  │  │  /analytics  │  │  /admin      │  │  /health    │ │    │
│  │  │  - GET       │  │  - POST      │  │  - GET      │ │    │
│  │  └──────────────┘  │  - PUT       │  └─────────────┘ │    │
│  │                    │  - DELETE    │                   │    │
│  │                    └──────────────┘                   │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │              WebSocket Endpoints                        │    │
│  │  ┌──────────────────────────────────────────────────┐  │    │
│  │  │  /ws/thread/:id  (Real-time updates)             │  │    │
│  │  └──────────────────────────────────────────────────┘  │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │              Dependency Injection                       │    │
│  │  - Database Session │ Redis Client │ Auth Service      │    │
│  └────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

#### 4.1.2 API Endpoints Specification

**Thread Management**:
```
POST   /api/v1/threads
GET    /api/v1/threads
GET    /api/v1/threads/{thread_id}
DELETE /api/v1/threads/{thread_id}
POST   /api/v1/threads/{thread_id}/backfill
```

**Cast Analytics**:
```
GET    /api/v1/threads/{thread_id}/cast
GET    /api/v1/threads/{thread_id}/cast/{cast_name}
GET    /api/v1/cast/{cast_name}/history
```

**Exports**:
```
POST   /api/v1/exports/csv
POST   /api/v1/exports/json
POST   /api/v1/exports/png
GET    /api/v1/exports/{export_id}
```

**Admin**:
```
GET    /api/v1/admin/cast-roster
POST   /api/v1/admin/cast-roster
PUT    /api/v1/admin/cast-roster/{cast_id}
DELETE /api/v1/admin/cast-roster/{cast_id}
GET    /api/v1/admin/model-versions
POST   /api/v1/admin/model-versions/deploy
```

**System**:
```
GET    /health         (Health check)
GET    /ready          (Readiness check)
GET    /metrics        (Prometheus metrics)
GET    /api/docs       (Swagger UI)
```

### 4.2 Background Workers (Celery)

#### 4.2.1 Task Flow Diagram

```
                          ┌──────────────────┐
                          │  API Receives    │
                          │  Thread URL      │
                          └────────┬─────────┘
                                   │
                                   ▼
                          ┌──────────────────┐
                          │  Queue Task:     │
                          │  fetch_thread    │
                          └────────┬─────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        │                          │                           │
        ▼                          ▼                           ▼
┌────────────────┐      ┌────────────────┐        ┌────────────────┐
│  INGESTION     │      │  PROCESSING    │        │  ANALYTICS     │
│  Queue         │      │  Queue         │        │  Queue         │
└───────┬────────┘      └───────┬────────┘        └───────┬────────┘
        │                       │                         │
        ▼                       ▼                         ▼
┌────────────────┐      ┌────────────────┐        ┌────────────────┐
│ fetch_thread   │      │ classify_      │        │ compute_       │
│ - Call Reddit  │──────│ comments       │────────│ aggregates     │
│   API          │      │ - Entity link  │        │ - Vote weight  │
│ - Parse JSON   │      │ - Sentiment    │        │ - Time slice   │
│ - Store raw    │      │ - Sarcasm      │        │ - Statistics   │
└────────────────┘      │ - Toxicity     │        └────────────────┘
                        └────────────────┘                 │
                                                           ▼
                        ┌────────────────┐        ┌────────────────┐
                        │ poll_thread    │        │ check_alerts   │
                        │ - Incremental  │        │ - Thresholds   │
                        │ - Every 60s    │        │ - Send Slack   │
                        └────────────────┘        │ - Send Email   │
                                                  └────────────────┘
                                                           │
                                                           ▼
                        ┌────────────────┐        ┌────────────────┐
                        │ backfill_      │        │ cleanup_data   │
                        │ thread         │        │ - Delete old   │
                        │ - After 24h    │        │ - GDPR comply  │
                        │ - Real scores  │        └────────────────┘
                        └────────────────┘
```

#### 4.2.2 Task Definitions

**Ingestion Tasks**:
```python
@celery_app.task(name="ltsr.ingestion.fetch_thread")
def fetch_thread(thread_url: str, thread_id: int):
    """Fetch complete thread from Reddit API"""
    # Priority: High
    # Retry: 3 times with exponential backoff
    # Timeout: 10 minutes

@celery_app.task(name="ltsr.ingestion.poll_thread")
def poll_thread(thread_id: int):
    """Poll for new comments (live monitoring)"""
    # Priority: High
    # Retry: 1 time
    # Timeout: 2 minutes
    # Schedule: Every 60s during live window
```

**Processing Tasks**:
```python
@celery_app.task(name="ltsr.processing.classify_comments")
def classify_comments(comment_ids: List[int]):
    """Run ML inference on comments"""
    # Priority: High
    # Retry: 2 times
    # Timeout: 15 minutes
    # Batch size: 32 comments

@celery_app.task(name="ltsr.processing.link_entities")
def link_entities(comment_ids: List[int]):
    """Extract cast mentions"""
    # Priority: High
    # Retry: 2 times
    # Timeout: 5 minutes
```

**Analytics Tasks**:
```python
@celery_app.task(name="ltsr.analytics.compute_aggregates")
def compute_aggregates(thread_id: int):
    """Compute vote-weighted sentiment"""
    # Priority: Medium
    # Retry: 2 times
    # Timeout: 10 minutes

@celery_app.task(name="ltsr.analytics.check_alerts")
def check_alerts(thread_id: int):
    """Check alert conditions"""
    # Priority: High
    # Retry: 1 time
    # Timeout: 2 minutes
```

**Maintenance Tasks**:
```python
@celery_app.task(name="ltsr.maintenance.backfill_thread")
def backfill_thread(thread_id: int):
    """Re-run with revealed scores"""
    # Priority: Low
    # Retry: 1 time
    # Timeout: 20 minutes
    # Schedule: 24h after thread creation

@celery_app.task(name="ltsr.maintenance.cleanup_data")
def cleanup_data():
    """Delete expired data"""
    # Priority: Low
    # Retry: 0 times
    # Timeout: 30 minutes
    # Schedule: Daily at 3am UTC
```

### 4.3 ML Inference Service

#### 4.3.1 Service Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              ML Inference Service (FastAPI)                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │              Request Handler                        │    │
│  │  POST /predict  (Batch inference)                   │    │
│  │  GET  /health   (Service health)                    │    │
│  │  GET  /model    (Model info)                        │    │
│  └────────────────────────────────────────────────────┘    │
│                         │                                    │
│                         ▼                                    │
│  ┌────────────────────────────────────────────────────┐    │
│  │         Request Validation & Batching               │    │
│  │  - Validate input text                              │    │
│  │  - Batch up to 32 items                             │    │
│  │  - Queue for processing                             │    │
│  └────────────────────────────────────────────────────┘    │
│                         │                                    │
│                         ▼                                    │
│  ┌────────────────────────────────────────────────────┐    │
│  │           Tokenization (RoBERTa)                    │    │
│  │  - Load tokenizer (cached)                          │    │
│  │  - Tokenize batch                                   │    │
│  │  - Padding & truncation (max 512 tokens)            │    │
│  └────────────────────────────────────────────────────┘    │
│                         │                                    │
│                         ▼                                    │
│  ┌────────────────────────────────────────────────────┐    │
│  │        Model Inference (GPU/CPU)                    │    │
│  │  ┌──────────────────────────────────────────────┐  │    │
│  │  │  RoBERTa-large Encoder (355M params)        │  │    │
│  │  │  - Load model weights (cached)               │  │    │
│  │  │  - Forward pass                              │  │    │
│  │  │  - Extract [CLS] token representation        │  │    │
│  │  └──────────────────┬───────────────────────────┘  │    │
│  │                     │                               │    │
│  │  ┌──────────────────┼───────────────────────────┐  │    │
│  │  │  Multi-Task Heads                            │  │    │
│  │  │  ┌────────────┐ ┌────────────┐ ┌──────────┐ │  │    │
│  │  │  │ Sentiment  │ │  Sarcasm   │ │ Toxicity │ │  │    │
│  │  │  │   Head     │ │   Head     │ │   Head   │ │  │    │
│  │  │  │ (3-class)  │ │ (binary)   │ │ (binary) │ │  │    │
│  │  │  └────────────┘ └────────────┘ └──────────┘ │  │    │
│  │  └──────────────────────────────────────────────┘  │    │
│  └────────────────────────────────────────────────────┘    │
│                         │                                    │
│                         ▼                                    │
│  ┌────────────────────────────────────────────────────┐    │
│  │           Post-Processing                           │    │
│  │  - Softmax for sentiment                            │    │
│  │  - Sigmoid for sarcasm/toxicity                     │    │
│  │  - Apply thresholds                                 │    │
│  │  - Format response                                  │    │
│  └────────────────────────────────────────────────────┘    │
│                         │                                    │
│                         ▼                                    │
│  ┌────────────────────────────────────────────────────┐    │
│  │              Response                               │    │
│  │  {                                                  │    │
│  │    "predictions": [                                 │    │
│  │      {                                              │    │
│  │        "sentiment": {"label": "positive", ...},     │    │
│  │        "sarcasm": {"is_sarcastic": false, ...},     │    │
│  │        "toxicity": {"is_toxic": false, ...}         │    │
│  │      }                                               │    │
│  │    ]                                                 │    │
│  │  }                                                  │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

#### 4.3.2 Model Loading Strategy

```python
# Singleton pattern for model loading
class ModelManager:
    _instance = None
    _model = None
    _tokenizer = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_model()
        return cls._instance
    
    def _load_model(self):
        """Load model once at startup"""
        model_path = os.getenv("MODEL_PATH")
        
        # Load tokenizer
        self._tokenizer = RobertaTokenizer.from_pretrained('roberta-large')
        
        # Load model
        self._model = RobertaMultiTask()
        self._model.load_state_dict(torch.load(model_path))
        self._model.eval()
        
        # Move to GPU if available
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self._model.to(device)
    
    def predict(self, texts: List[str]):
        """Batch inference"""
        # Tokenize
        encoded = self._tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors='pt'
        )
        
        # Inference
        with torch.no_grad():
            outputs = self._model(
                encoded['input_ids'],
                encoded['attention_mask']
            )
        
        return outputs
```

### 4.4 Frontend Dashboard

#### 4.4.1 Component Hierarchy

```
App
├── Router
│   ├── DashboardPage
│   │   ├── Header
│   │   ├── EpisodeOverview
│   │   │   ├── EpisodeSummaryCard
│   │   │   ├── CastGrid
│   │   │   │   └── CastCard (×8)
│   │   │   ├── TimelineChart
│   │   │   └── MomentDetection
│   │   └── Footer
│   │
│   ├── CastDetailPage
│   │   ├── CastHeader
│   │   ├── SentimentTrajectory
│   │   ├── TopicClusters
│   │   ├── TopComments
│   │   └── AllMentionsTable
│   │
│   ├── IntegrityPage
│   │   ├── BrigadingPanel
│   │   ├── BotDetectionPanel
│   │   ├── ScoreReliabilityPanel
│   │   └── AlertHistory
│   │
│   └── AdminPage
│       ├── CastRosterManager
│       ├── ModelVersionControl
│       ├── UserManagement
│       └── SystemHealth
│
├── Shared Components
│   ├── Button
│   ├── Card
│   ├── Modal
│   ├── Spinner
│   ├── Alert
│   └── DataTable
│
├── Hooks
│   ├── useThread
│   ├── useCast
│   ├── useWebSocket
│   ├── useAuth
│   └── useExport
│
└── Services
    ├── api.ts
    ├── threadService.ts
    ├── castService.ts
    ├── exportService.ts
    └── adminService.ts
```

#### 4.4.2 State Management

```typescript
// Zustand Store Structure
interface AppState {
  // UI State
  ui: {
    sidebarOpen: boolean
    darkMode: boolean
    selectedThread: string | null
  }
  
  // Thread State (React Query)
  threads: {
    list: Thread[]
    current: Thread | null
    loading: boolean
    error: Error | null
  }
  
  // Cast State (React Query)
  cast: {
    data: CastAnalytics[]
    loading: boolean
    error: Error | null
  }
  
  // WebSocket State
  realTime: {
    connected: boolean
    lastUpdate: Date | null
    updates: Update[]
  }
  
  // User State
  user: {
    profile: User | null
    permissions: Permission[]
    preferences: UserPreferences
  }
}
```

---

## 5. Data Architecture

### 5.1 Database Schema (PostgreSQL)

#### 5.1.1 Entity Relationship Diagram

```
┌─────────────────┐
│     threads     │
├─────────────────┤
│ id (PK)         │◄────┐
│ reddit_id       │     │
│ subreddit       │     │
│ title           │     │
│ air_time_utc    │     │
│ created_utc     │     │
│ status          │     │
│ total_comments  │     │
└─────────────────┘     │
                        │ 1:N
                        │
┌─────────────────┐     │
│    comments     │─────┘
├─────────────────┤
│ id (PK)         │◄────┐
│ thread_id (FK)  │     │
│ reddit_id       │     │
│ author_hash     │     │
│ text            │     │
│ created_utc     │     │
│ score           │     │
│ parent_id       │     │
│ reply_count     │     │
│ time_window     │     │
└─────────────────┘     │
                        │ 1:N
                        │
┌─────────────────┐     │
│    mentions     │─────┘
├─────────────────┤
│ id (PK)         │
│ comment_id (FK) │
│ cast_member     │
│ sentiment_label │
│ sentiment_score │
│ confidence      │
│ is_sarcastic    │
│ is_toxic        │
│ weight          │
│ method          │
└─────────────────┘

┌─────────────────┐
│   aggregates    │
├─────────────────┤
│ id (PK)         │
│ thread_id (FK)  │──┐
│ cast_member     │  │
│ time_window     │  │ N:1
│ net_sentiment   │  │
│ ci_lower        │  │
│ ci_upper        │  ▼
│ positive_pct    │ ┌─────────────────┐
│ neutral_pct     │ │     threads     │
│ negative_pct    │ └─────────────────┘
│ agreement_score │
│ mention_count   │
│ computed_at     │
└─────────────────┘

┌─────────────────┐
│      users      │
├─────────────────┤
│ id (PK)         │
│ email           │
│ auth0_id        │
│ role            │
│ created_at      │
│ last_login      │
└─────────────────┘

┌─────────────────┐
│ model_versions  │
├─────────────────┤
│ id (PK)         │
│ version         │
│ deployed_at     │
│ accuracy        │
│ sarcasm_f1      │
│ notes           │
└─────────────────┘
```

#### 5.1.2 Partitioning Strategy

**Comments Table Partitioning** (by created_at):
```sql
-- Partition by month for 30-day retention
CREATE TABLE comments (
    id BIGSERIAL,
    thread_id INT,
    created_at TIMESTAMP,
    -- other fields...
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- Create monthly partitions
CREATE TABLE comments_2025_10 PARTITION OF comments
    FOR VALUES FROM ('2025-10-01') TO ('2025-11-01');

CREATE TABLE comments_2025_11 PARTITION OF comments
    FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');

-- Auto-create partitions with pg_partman extension
-- Drop old partitions automatically after 30 days
```

**Benefits**:
- **Query Performance**: Partition pruning reduces scan size
- **Retention Management**: Drop entire partitions instead of DELETE
- **Maintenance**: VACUUM, ANALYZE per partition
- **Storage**: Archive old partitions to cold storage

#### 5.1.3 Indexing Strategy

```sql
-- Threads
CREATE UNIQUE INDEX idx_threads_reddit_id ON threads(reddit_id);
CREATE INDEX idx_threads_status ON threads(status) WHERE status != 'completed';
CREATE INDEX idx_threads_air_time ON threads(air_time_utc);

-- Comments
CREATE INDEX idx_comments_thread ON comments(thread_id);
CREATE INDEX idx_comments_created ON comments(created_utc);
CREATE INDEX idx_comments_author ON comments(author_hash);
CREATE INDEX idx_comments_time_window ON comments(time_window);

-- Mentions
CREATE INDEX idx_mentions_comment ON mentions(comment_id);
CREATE INDEX idx_mentions_cast ON mentions(cast_member);
CREATE INDEX idx_mentions_sentiment ON mentions(sentiment_label);

-- Aggregates
CREATE INDEX idx_aggregates_thread_cast ON aggregates(thread_id, cast_member);
CREATE INDEX idx_aggregates_window ON aggregates(time_window);

-- Composite indexes for common queries
CREATE INDEX idx_comments_thread_window ON comments(thread_id, time_window);
CREATE INDEX idx_mentions_cast_sentiment ON mentions(cast_member, sentiment_label);
```

### 5.2 Cache Architecture (Redis)

#### 5.2.1 Cache Key Design

```
Pattern: {namespace}:{entity}:{id}:{attribute}

Examples:
thread:abc123                           # Thread metadata
thread:abc123:comments                  # Comment IDs list
thread:abc123:aggregates               # All aggregates
aggregate:abc123:Lisa_Barlow:live      # Specific aggregate
cast:Lisa_Barlow:history               # Cast history across threads
ratelimit:user:123                     # Rate limit counter
session:xyz789                         # User session
ws:thread:abc123                       # WebSocket pub/sub channel
```

#### 5.2.2 TTL Strategy

| Cache Type | TTL | Rationale |
|------------|-----|-----------|
| Thread metadata | 15 min | Updates during live monitoring |
| Aggregates (live) | 5 min | Frequent recomputation |
| Aggregates (final) | 1 hour | Stable after backfill |
| Cast history | 1 hour | Changes infrequently |
| User session | 1 hour | Extend on activity |
| Rate limit counters | 1 min | Rolling window |
| Model predictions | N/A | Never cached (vary by comment) |

#### 5.2.3 Cache Patterns

**Cache-Aside (Lazy Loading)**:
```python
def get_thread_aggregates(thread_id: str):
    # Check cache
    cache_key = f"aggregate:{thread_id}"
    cached = redis.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # Cache miss - query database
    aggregates = db.query(Aggregate).filter_by(thread_id=thread_id).all()
    
    # Store in cache
    redis.setex(cache_key, 300, json.dumps(aggregates))
    
    return aggregates
```

**Write-Through**:
```python
def update_aggregate(aggregate: Aggregate):
    # Update database
    db.session.add(aggregate)
    db.session.commit()
    
    # Update cache immediately
    cache_key = f"aggregate:{aggregate.thread_id}"
    redis.setex(cache_key, 300, json.dumps(aggregate))
```

**Cache Invalidation**:
```python
def invalidate_thread_cache(thread_id: str):
    # Delete all cache keys related to thread
    pattern = f"thread:{thread_id}:*"
    keys = redis.keys(pattern)
    if keys:
        redis.delete(*keys)
```

### 5.3 Object Storage (S3)

#### 5.3.1 Bucket Structure

```
ltsr-data-bucket/
├── raw/
│   ├── 2025/
│   │   ├── 10/
│   │   │   ├── 16/
│   │   │   │   ├── thread_abc123.json.gz
│   │   │   │   ├── thread_def456.json.gz
│   │   │   │   └── ...
│   │   │   └── ...
│   │   └── ...
│   └── ...
│
├── models/
│   ├── roberta-multitask-v2025.03.1/
│   │   ├── model.pt
│   │   ├── config.json
│   │   └── tokenizer/
│   ├── roberta-multitask-v2025.04.1/
│   └── ...
│
├── exports/
│   ├── csv/
│   │   ├── thread_abc123_2025-10-16.csv
│   │   └── ...
│   ├── json/
│   │   ├── thread_abc123_2025-10-16.json
│   │   └── ...
│   └── png/
│       ├── thread_abc123_cast_grid.png
│       └── ...
│
└── backups/
    ├── database/
    │   ├── ltsr_2025-10-16.sql.gz
    │   └── ...
    └── config/
        └── cast_dictionary_2025-10-16.json
```

#### 5.3.2 Lifecycle Policies

```json
{
  "Rules": [
    {
      "Id": "ArchiveRawDataAfter30Days",
      "Filter": {"Prefix": "raw/"},
      "Status": "Enabled",
      "Transitions": [
        {
          "Days": 30,
          "StorageClass": "GLACIER"
        }
      ],
      "Expiration": {
        "Days": 365
      }
    },
    {
      "Id": "DeleteExportsAfter7Days",
      "Filter": {"Prefix": "exports/"},
      "Status": "Enabled",
      "Expiration": {
        "Days": 7
      }
    },
    {
      "Id": "ArchiveBackupsAfter7Days",
      "Filter": {"Prefix": "backups/"},
      "Status": "Enabled",
      "Transitions": [
        {
          "Days": 7,
          "StorageClass": "GLACIER"
        }
      ]
    }
  ]
}
```

---

## 6. Integration Architecture

### 6.1 Reddit API Integration

#### 6.1.1 Integration Flow

```
┌────────────────┐
│  LTSR Backend  │
└────────┬───────┘
         │
         │ 1. Fetch Thread
         ▼
┌────────────────────────────────────────────────────────┐
│          Reddit API Client (PRAW Wrapper)              │
├────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────────────────────────────────────────┐ │
│  │  Rate Limiter (5000 calls/min Enterprise)       │ │
│  │  - Track API calls in Redis                      │ │
│  │  - Exponential backoff on 429 errors             │ │
│  └──────────────────────────────────────────────────┘ │
│                      │                                  │
│                      │ 2. OAuth2 Auth                   │
│                      ▼                                  │
│  ┌──────────────────────────────────────────────────┐ │
│  │  Authentication Handler                           │ │
│  │  - Client ID + Secret                            │ │
│  │  - Refresh token flow                            │ │
│  └──────────────────────────────────────────────────┘ │
│                      │                                  │
│                      │ 3. API Request                   │
│                      ▼                                  │
└──────────────────────┼──────────────────────────────────┘
                       │
                       ▼
            ┌──────────────────┐
            │   Reddit API     │
            │  (api.reddit.com)│
            └──────────┬───────┘
                       │
                       │ 4. JSON Response
                       ▼
┌────────────────────────────────────────────────────────┐
│          Response Handler                              │
├────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────┐ │
│  │  Parse & Validate                                 │ │
│  │  - Check for errors                               │ │
│  │  - Validate JSON structure                        │ │
│  └──────────────────────────────────────────────────┘ │
│                      │                                  │
│                      │ 5. Store Raw                     │
│                      ▼                                  │
│  ┌──────────────────────────────────────────────────┐ │
│  │  S3 Storage (Compressed JSON)                     │ │
│  │  - Audit trail                                    │ │
│  │  - 30-day retention → Glacier                     │ │
│  └──────────────────────────────────────────────────┘ │
│                      │                                  │
│                      │ 6. Process                       │
│                      ▼                                  │
│  ┌──────────────────────────────────────────────────┐ │
│  │  Normalize & Store in PostgreSQL                  │ │
│  │  - Extract comments                               │ │
│  │  - Hash usernames                                 │ │
│  │  - Store metadata                                 │ │
│  └──────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────┘
                       │
                       │ 7. Trigger Processing
                       ▼
            ┌──────────────────┐
            │  Celery Task:    │
            │  process_thread  │
            └──────────────────┘
```

#### 6.1.2 Error Handling Strategy

| Error Type | HTTP Code | Action | Retry |
|------------|-----------|--------|-------|
| Rate Limit | 429 | Wait (Retry-After header) | Yes (3x) |
| Invalid Token | 401 | Refresh OAuth token | Yes (1x) |
| Not Found | 404 | Mark thread as invalid | No |
| Server Error | 500-503 | Exponential backoff | Yes (5x) |
| Timeout | N/A | Retry with increased timeout | Yes (3x) |
| Deleted Thread | 403/404 | Mark as deleted, stop polling | No |

#### 6.1.3 Incremental Fetch Strategy

```python
def fetch_new_comments(thread_id: str, last_fetch_utc: int):
    """
    Fetch only comments created after last fetch
    More efficient than fetching entire thread
    """
    submission = reddit.submission(id=thread_id)
    
    # Get all comments (flattened)
    submission.comments.replace_more(limit=0)  # Don't load "more comments"
    all_comments = submission.comments.list()
    
    # Filter by created_utc
    new_comments = [
        c for c in all_comments
        if c.created_utc > last_fetch_utc
    ]
    
    return new_comments
```

### 6.2 Authentication Integration (Auth0)

#### 6.2.1 Auth Flow

```
┌──────────────┐                               ┌──────────────┐
│   Browser    │                               │  Auth0       │
└──────┬───────┘                               └──────┬───────┘
       │                                              │
       │ 1. Login Button Click                        │
       ├──────────────────────────────────────────────▶
       │                                              │
       │                                              │ 2. Redirect to
       │                                              │    Auth0 Login
       ◀──────────────────────────────────────────────┤
       │                                              │
       │ 3. Enter Credentials                         │
       ├──────────────────────────────────────────────▶
       │                                              │
       │                                              │ 4. Validate
       │                                              │    Credentials
       │                                              │
       │                                              │ 5. Generate
       │                                              │    Tokens (JWT)
       ◀──────────────────────────────────────────────┤
       │                                              │
       │ 6. Redirect to App                           │
       │    (with Authorization Code)                 │
       │                                              │
       ▼                                              │
┌──────────────┐                                     │
│  LTSR        │                                     │
│  Frontend    │                                     │
└──────┬───────┘                                     │
       │                                              │
       │ 7. Exchange Code for Tokens                  │
       ├──────────────────────────────────────────────▶
       │                                              │
       ◀──────────────────────────────────────────────┤
       │ 8. Access Token + ID Token                   │
       │                                              │
       │                                              │
       │ 9. API Request (with Access Token)           │
       ▼                                              │
┌──────────────┐                                     │
│  LTSR API    │                                     │
│  (FastAPI)   │                                     │
└──────┬───────┘                                     │
       │                                              │
       │ 10. Validate Token                           │
       ├──────────────────────────────────────────────▶
       │                                              │
       ◀──────────────────────────────────────────────┤
       │ 11. Token Valid (Public Key)                 │
       │                                              │
       │ 12. Authorize Request                        │
       │     (Check Permissions)                      │
       │                                              │
       │ 13. Response                                 │
       ▼                                              │
```

#### 6.2.2 Token Validation

```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt import PyJWKClient

security = HTTPBearer()
jwks_client = PyJWKClient(f"https://{AUTH0_DOMAIN}/.well-known/jwks.json")

async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Verify JWT token from Auth0
    """
    token = credentials.credentials
    
    try:
        # Get signing key
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        
        # Verify token
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=AUTH0_AUDIENCE,
            issuer=f"https://{AUTH0_DOMAIN}/"
        )
        
        return payload
    
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

### 6.3 Alert Integrations

#### 6.3.1 Slack Integration

```python
import httpx

async def send_slack_alert(thread_id: str, cast_member: str, sentiment_drop: float):
    """
    Send alert to Slack via webhook
    """
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    
    payload = {
        "text": f"🚨 LTSR Alert: Sentiment Drop Detected",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🚨 Sentiment Alert: {cast_member}"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Thread:*\n{thread_id}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Cast Member:*\n{cast_member}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Sentiment Drop:*\n{sentiment_drop:.2f}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Time:*\n<!date^{int(time.time())}^{{time}}|{datetime.now()}>"
                    }
                ]
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View Dashboard"
                        },
                        "url": f"https://ltsr.app/threads/{thread_id}"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Dismiss"
                        },
                        "action_id": f"dismiss_{thread_id}"
                    }
                ]
            }
        ]
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(webhook_url, json=payload)
        response.raise_for_status()
```

#### 6.3.2 Email Integration (SendGrid)

```python
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

async def send_email_alert(
    recipient: str,
    thread_id: str,
    cast_member: str,
    sentiment_data: dict
):
    """
    Send email alert via SendGrid
    """
    message = Mail(
        from_email=os.getenv("FROM_EMAIL"),
        to_emails=recipient,
        subject=f"LTSR Alert: {cast_member} Sentiment Drop",
        html_content=f"""
        <html>
        <body>
            <h2>LTSR Sentiment Alert</h2>
            <p>A significant sentiment drop has been detected:</p>
            <ul>
                <li><strong>Cast Member:</strong> {cast_member}</li>
                <li><strong>Current Sentiment:</strong> {sentiment_data['current']:.2f}</li>
                <li><strong>Previous Sentiment:</strong> {sentiment_data['previous']:.2f}</li>
                <li><strong>Change:</strong> {sentiment_data['change']:.2f}</li>
            </ul>
            <p>
                <a href="https://ltsr.app/threads/{thread_id}">View Full Analysis</a>
            </p>
        </body>
        </html>
        """
    )
    
    try:
        sg = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))
        response = sg.send(message)
        return response.status_code
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        raise
```

---

## 7. Security Architecture

### 7.1 Security Layers

```
┌─────────────────────────────────────────────────────────────┐
│              Layer 7: Application Security                   │
│  - Input Validation                                          │
│  - SQL Injection Prevention (Parameterized Queries)          │
│  - XSS Prevention (Content Security Policy)                  │
│  - CSRF Protection (SameSite Cookies)                        │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│              Layer 6: Authentication & Authorization         │
│  - Auth0 JWT Validation                                      │
│  - Role-Based Access Control (RBAC)                          │
│  - API Key Management                                        │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│              Layer 5: API Security                           │
│  - Rate Limiting (100 req/min/user)                         │
│  - Request Size Limits (10MB max)                           │
│  - API Versioning                                           │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│              Layer 4: Transport Security                     │
│  - TLS 1.3 Encryption                                       │
│  - Certificate Management (Let's Encrypt)                   │
│  - HSTS (HTTP Strict Transport Security)                   │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│              Layer 3: Network Security                       │
│  - WAF (Web Application Firewall)                           │
│  - DDoS Protection (Cloudflare / AWS Shield)                │
│  - VPC (Virtual Private Cloud)                              │
│  - Security Groups / Network ACLs                           │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│              Layer 2: Data Security                          │
│  - Encryption at Rest (AES-256)                             │
│  - Database Encryption (PostgreSQL TDE)                     │
│  - Secrets Management (AWS Secrets Manager)                 │
│  - PII Hashing (SHA-256 + Salt)                             │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│              Layer 1: Infrastructure Security                │
│  - Container Security Scanning (Trivy)                      │
│  - Vulnerability Management (Snyk)                          │
│  - Access Logging & Monitoring                              │
│  - Intrusion Detection (AWS GuardDuty)                      │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 Data Privacy Architecture

#### 7.2.1 PII Handling

```
┌──────────────────────────────────────────────────────────┐
│           Reddit Comment Ingestion                        │
│  "Great episode! - Posted by user_john_doe"              │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │  Username Detection   │
         │  - Extract: john_doe  │
         └───────────┬───────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │  Hash with Salt       │
         │  SHA-256(john_doe +   │
         │          SALT_KEY)    │
         │  = a1b2c3d4e5...      │
         └───────────┬───────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │  Store in Database    │
         │  author_hash:         │
         │  a1b2c3d4e5...        │
         │  (Original username   │
         │   NOT stored)         │
         └───────────┬───────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │  30-Day Retention     │
         │  - Auto-delete after  │
         │    30 days            │
         │  - GDPR/CCPA compliant│
         └───────────────────────┘
```

#### 7.2.2 Data Retention Flow

```
Day 0: Comment ingested
  ├─> Raw JSON stored in S3 (compressed)
  ├─> Comment text stored in PostgreSQL
  └─> Username hashed and stored

Day 30: Retention policy triggered
  ├─> Raw JSON moved to Glacier (S3 lifecycle)
  ├─> Comment text deleted from PostgreSQL
  ├─> Username hash deleted
  └─> Aggregates retained (anonymized)

Day 365: Archive retention expires
  └─> Raw JSON deleted from Glacier

Aggregates: Retained for 2 years
  ├─> No PII (only statistics)
  ├─> Cannot be linked back to individuals
  └─> Used for historical analysis
```

### 7.3 Compliance Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    GDPR/CCPA Compliance                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Right to Access (GDPR Art. 15)                     │    │
│  │  - User requests their data                         │    │
│  │  - Export all comments, sentiment scores, timestamps│    │
│  │  - Delivered within 30 days                         │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Right to Erasure (GDPR Art. 17)                    │    │
│  │  - User requests deletion                            │    │
│  │  - Verify identity                                  │    │
│  │  - Delete: raw text, username hash                  │    │
│  │  - Retain: anonymized aggregates (exception)        │    │
│  │  - Completed within 30 days                         │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Right to Rectification (GDPR Art. 16)              │    │
│  │  - User flags incorrect sentiment                   │    │
│  │  - Manual review by analyst                         │    │
│  │  - Correction within 30 days                        │    │
│  │  - Update training data                             │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Data Minimization (GDPR Art. 5)                    │    │
│  │  - Collect only necessary data                      │    │
│  │  - No email/phone/address                           │    │
│  │  - Username hashed immediately                      │    │
│  │  - No cross-platform linking                        │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Audit Trail (GDPR Art. 30)                         │    │
│  │  - Log all data access                              │    │
│  │  - Who viewed what thread, when                     │    │
│  │  - Retained for 2 years                             │    │
│  │  - Encrypted at rest                                │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

[Due to length constraints, this is the first part of the Solution Architecture document. Would you like me to continue with sections 8-12 (Deployment Architecture, Scalability, Disaster Recovery, Monitoring, and Decision Log)?]