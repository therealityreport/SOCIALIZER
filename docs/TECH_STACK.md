# SOCIALIZER Technical Stack & Development Specifications

## Overview
This document details the complete technical stack, architecture decisions, and development specifications for the SOCIALIZER project (LiveThread Sentiment for Reddit - LTSR).

---

## Tech Stack Summary

### Backend
- **Language**: Python 3.11+
- **Framework**: FastAPI 0.104+
- **Task Queue**: Celery 5.3+ with Redis broker
- **Database**: PostgreSQL 15+
- **Cache**: Redis 7+
- **ORM**: SQLAlchemy 2.0+ with Alembic migrations

### Frontend
- **Language**: TypeScript 5.2+
- **Framework**: React 18+ with Vite
- **UI Library**: Tailwind CSS 3.3+ with shadcn/ui components
- **State Management**: Zustand 4.4+ and React Query 5.0+
- **Charts**: Recharts 2.8+
- **Real-time**: WebSocket (native browser API)

### Machine Learning
- **Framework**: PyTorch 2.1+
- **Transformers**: Hugging Face Transformers 4.35+
- **Base Model**: RoBERTa-large (355M parameters)
- **NLP**: spaCy 3.7+ with en_core_web_lg
- **Training**: Weights & Biases for experiment tracking

### Infrastructure
- **Cloud Provider**: AWS (primary) or Google Cloud Platform
- **Container**: Docker 24+ with Docker Compose
- **Orchestration**: Kubernetes 1.28+ or AWS ECS
- **CI/CD**: GitHub Actions
- **Monitoring**: Datadog or New Relic
- **Logging**: Sentry for errors, CloudWatch for logs

### External Services
- **Reddit API**: OAuth2 Enterprise tier
- **Authentication**: Auth0 or Clerk
- **Email**: SendGrid
- **Alerts**: Slack Webhooks
- **Object Storage**: AWS S3 or Google Cloud Storage

---

## Detailed Stack Specifications

### 1. Backend Stack

#### Core Framework: FastAPI
```python
# Dependencies (requirements.txt)
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
pydantic-settings==2.1.0
```

**Why FastAPI?**
- Async/await support (non-blocking I/O for Reddit API)
- Automatic OpenAPI/Swagger documentation
- Fast performance (~3x faster than Django)
- Built-in data validation with Pydantic
- WebSocket support for real-time dashboard

**Configuration**:
```python
# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="LTSR API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Frontend dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

#### Database: PostgreSQL 15
```python
# Dependencies
sqlalchemy==2.0.23
alembic==1.12.1
psycopg2-binary==2.9.9
```

**Schema Design**:
```sql
-- Core tables with retention policies
CREATE TABLE threads (
    id SERIAL PRIMARY KEY,
    reddit_id VARCHAR(10) UNIQUE NOT NULL,
    subreddit VARCHAR(50),
    title TEXT,
    air_time_utc TIMESTAMP,
    created_utc TIMESTAMP,
    url TEXT,
    total_comments INT,
    status VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Partition comments by month for 30-day retention
CREATE TABLE comments (
    id BIGSERIAL PRIMARY KEY,
    thread_id INT REFERENCES threads(id) ON DELETE CASCADE,
    reddit_id VARCHAR(10) UNIQUE NOT NULL,
    author_hash VARCHAR(64),
    text TEXT,
    created_utc TIMESTAMP,
    score INT,
    time_window VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- Monthly partitions
CREATE TABLE comments_2025_10 PARTITION OF comments
    FOR VALUES FROM ('2025-10-01') TO ('2025-11-01');
```

**Performance Optimization**:
- B-tree indexes on foreign keys
- GIN indexes for full-text search (if needed)
- Connection pooling (20-50 connections)
- Prepared statements for common queries
- Read replicas for analytics queries

#### Cache: Redis 7
```python
# Dependencies
redis==5.0.1
aioredis==2.0.1  # Async support
```

**Usage Patterns**:
```python
# Cache keys structure
thread:{reddit_id}              # Thread metadata (15-min TTL)
aggregates:{reddit_id}:{cast}   # Cast aggregates (5-min TTL)
ratelimit:{client_id}           # Reddit API rate limits
websocket:channel:{thread_id}   # WebSocket pub/sub
```

**Configuration**:
```python
# config.py
REDIS_CONFIG = {
    "host": os.getenv("REDIS_HOST", "localhost"),
    "port": int(os.getenv("REDIS_PORT", 6379)),
    "db": 0,
    "decode_responses": True,
    "max_connections": 50,
    "socket_keepalive": True,
    "socket_keepalive_options": {6: 1, 4: 10, 5: 3}
}
```

#### Task Queue: Celery
```python
# Dependencies
celery==5.3.4
celery[redis]==5.3.4
flower==2.0.1  # Monitoring UI
```

**Task Types**:
1. **Reddit Ingestion**: Fetch comments from Reddit API
2. **ML Inference**: Batch sentiment classification
3. **Aggregation**: Compute vote-weighted stats
4. **Backfill**: Re-run with revealed scores
5. **Alerts**: Check thresholds, send notifications
6. **Cleanup**: Delete expired data (GDPR)

**Celery Configuration**:
```python
# celery_app.py
from celery import Celery

app = Celery(
    "ltsr",
    broker=os.getenv("REDIS_URL"),
    backend=os.getenv("REDIS_URL")
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes max
    worker_prefetch_multiplier=1,  # One task at a time
    worker_max_tasks_per_child=100,  # Restart after 100 tasks (memory)
)

# Task routing
app.conf.task_routes = {
    "ltsr.ingestion.*": {"queue": "ingestion"},
    "ltsr.ml.*": {"queue": "ml"},
    "ltsr.alerts.*": {"queue": "alerts"},
}
```

#### Reddit API Client
```python
# Dependencies
praw==7.7.1  # Python Reddit API Wrapper
aiohttp==3.9.1  # Async HTTP client
tenacity==8.2.3  # Retry logic
```

**Implementation**:
```python
# reddit_client.py
import praw
from tenacity import retry, stop_after_attempt, wait_exponential

class RedditClient:
    def __init__(self):
        self.reddit = praw.Reddit(
            client_id=os.getenv("REDDIT_CLIENT_ID"),
            client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
            user_agent=os.getenv("REDDIT_USER_AGENT")
        )
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=60)
    )
    def fetch_thread(self, submission_id: str):
        submission = self.reddit.submission(id=submission_id)
        submission.comments.replace_more(limit=None)  # Expand all comments
        return submission
    
    def get_comments_incremental(self, submission_id: str, after_utc: int):
        """Fetch only new comments since last check"""
        submission = self.reddit.submission(id=submission_id)
        comments = [
            c for c in submission.comments.list()
            if c.created_utc > after_utc
        ]
        return comments
```

**Rate Limiting**:
```python
# rate_limiter.py
import time
from collections import deque

class RateLimiter:
    def __init__(self, max_calls: int, period: int):
        self.max_calls = max_calls  # e.g., 5000
        self.period = period  # e.g., 60 seconds
        self.calls = deque()
    
    def wait_if_needed(self):
        now = time.time()
        
        # Remove calls outside the window
        while self.calls and self.calls[0] < now - self.period:
            self.calls.popleft()
        
        # If at limit, wait
        if len(self.calls) >= self.max_calls:
            sleep_time = self.period - (now - self.calls[0])
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        self.calls.append(now)
```

---

### 2. Frontend Stack

#### Framework: React 18 + TypeScript + Vite

**Dependencies** (`package.json`):
```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.20.0",
    "@tanstack/react-query": "^5.8.4",
    "zustand": "^4.4.7",
    "recharts": "^2.8.0",
    "lucide-react": "^0.294.0",
    "axios": "^1.6.2",
    "date-fns": "^2.30.0",
    "clsx": "^2.0.0",
    "tailwind-merge": "^2.1.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.43",
    "@types/react-dom": "^18.2.17",
    "@vitejs/plugin-react": "^4.2.1",
    "typescript": "^5.3.3",
    "vite": "^5.0.7",
    "tailwindcss": "^3.3.6",
    "postcss": "^8.4.32",
    "autoprefixer": "^10.4.16",
    "eslint": "^8.55.0",
    "prettier": "^3.1.1"
  }
}
```

**Why Vite?**
- 10-100x faster than Create React App
- Native ES modules (no bundling in dev)
- Hot Module Replacement (HMR) <50ms
- Optimized production builds with Rollup

**Vite Configuration**:
```typescript
// vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
})
```

#### UI Library: Tailwind CSS + shadcn/ui

**Tailwind Configuration**:
```javascript
// tailwind.config.js
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#f0f9ff',
          // ... (full palette)
          900: '#0c4a6e',
        },
        // Custom colors for sentiment
        sentiment: {
          positive: '#10b981',
          neutral: '#6b7280',
          negative: '#ef4444',
        },
      },
    },
  },
  plugins: [],
}
```

**shadcn/ui Components**:
```bash
# Install components
npx shadcn-ui@latest init
npx shadcn-ui@latest add button
npx shadcn-ui@latest add card
npx shadcn-ui@latest add dialog
npx shadcn-ui@latest add dropdown-menu
npx shadcn-ui@latest add table
```

#### State Management: Zustand + React Query

**Zustand Store** (Client State):
```typescript
// store/uiSlice.ts
import { create } from 'zustand'

interface UIState {
  sidebarOpen: boolean
  darkMode: boolean
  selectedThread: string | null
  setSidebarOpen: (open: boolean) => void
  toggleDarkMode: () => void
  setSelectedThread: (threadId: string | null) => void
}

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: true,
  darkMode: false,
  selectedThread: null,
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  toggleDarkMode: () => set((state) => ({ darkMode: !state.darkMode })),
  setSelectedThread: (threadId) => set({ selectedThread: threadId }),
}))
```

**React Query** (Server State):
```typescript
// hooks/useThread.ts
import { useQuery } from '@tanstack/react-query'
import { threadService } from '@/services/threadService'

export function useThread(threadId: string) {
  return useQuery({
    queryKey: ['thread', threadId],
    queryFn: () => threadService.getThread(threadId),
    refetchInterval: 60000, // Refresh every 60s for live threads
    staleTime: 30000, // Consider data stale after 30s
  })
}
```

#### Charts: Recharts

**Timeline Chart Example**:
```typescript
// components/dashboard/TimelineChart.tsx
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts'

interface TimelineChartProps {
  data: Array<{
    time: string
    [castMember: string]: number | string
  }>
  castMembers: string[]
}

export function TimelineChart({ data, castMembers }: TimelineChartProps) {
  const colors = ['#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#3b82f6']
  
  return (
    <LineChart width={1200} height={400} data={data}>
      <CartesianGrid strokeDasharray="3 3" />
      <XAxis dataKey="time" />
      <YAxis domain={[-1, 1]} />
      <Tooltip />
      <Legend />
      {castMembers.map((cast, idx) => (
        <Line
          key={cast}
          type="monotone"
          dataKey={cast}
          stroke={colors[idx % colors.length]}
          strokeWidth={2}
        />
      ))}
    </LineChart>
  )
}
```

#### WebSocket Integration

**Client-side WebSocket**:
```typescript
// hooks/useWebSocket.ts
import { useEffect, useState } from 'react'

export function useWebSocket(threadId: string) {
  const [data, setData] = useState(null)
  const [isConnected, setIsConnected] = useState(false)

  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/ws/thread/${threadId}`)

    ws.onopen = () => setIsConnected(true)
    ws.onmessage = (event) => {
      const update = JSON.parse(event.data)
      setData(update)
    }
    ws.onclose = () => setIsConnected(false)

    return () => ws.close()
  }, [threadId])

  return { data, isConnected }
}
```

**Server-side WebSocket** (FastAPI):
```python
# api/routes/websocket.py
from fastapi import WebSocket, WebSocketDisconnect
from typing import List

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, thread_id: str, websocket: WebSocket):
        await websocket.accept()
        if thread_id not in self.active_connections:
            self.active_connections[thread_id] = []
        self.active_connections[thread_id].append(websocket)

    async def broadcast(self, thread_id: str, message: dict):
        if thread_id in self.active_connections:
            for connection in self.active_connections[thread_id]:
                await connection.send_json(message)

manager = ConnectionManager()

@app.websocket("/ws/thread/{thread_id}")
async def websocket_endpoint(websocket: WebSocket, thread_id: str):
    await manager.connect(thread_id, websocket)
    try:
        while True:
            await websocket.receive_text()  # Keep connection alive
    except WebSocketDisconnect:
        manager.active_connections[thread_id].remove(websocket)
```

---

### 3. Machine Learning Stack

#### Model: RoBERTa-large Multi-Task

**Dependencies**:
```python
# requirements-ml.txt
torch==2.1.0
transformers==4.35.2
datasets==2.15.0
accelerate==0.25.0
scikit-learn==1.3.2
spacy==3.7.2
wandb==0.16.1  # Weights & Biases for experiment tracking
```

**Model Architecture**:
```python
# models/roberta_multitask.py
import torch
import torch.nn as nn
from transformers import RobertaModel, RobertaTokenizer

class RobertaMultiTask(nn.Module):
    def __init__(self):
        super().__init__()
        self.roberta = RobertaModel.from_pretrained('roberta-large')
        self.dropout = nn.Dropout(0.3)
        
        # Task-specific heads
        self.sentiment_head = nn.Linear(1024, 3)  # Pos/Neu/Neg
        self.sarcasm_head = nn.Linear(1024, 1)    # Binary
        self.toxicity_head = nn.Linear(1024, 1)   # Binary
    
    def forward(self, input_ids, attention_mask):
        outputs = self.roberta(input_ids=input_ids, attention_mask=attention_mask)
        pooled = outputs.last_hidden_state[:, 0, :]  # [CLS] token
        pooled = self.dropout(pooled)
        
        sentiment_logits = self.sentiment_head(pooled)
        sarcasm_logits = self.sarcasm_head(pooled)
        toxicity_logits = self.toxicity_head(pooled)
        
        return {
            'sentiment': sentiment_logits,
            'sarcasm': sarcasm_logits,
            'toxicity': toxicity_logits
        }
```

**Training Script**:
```python
# training/train_multitask.py
import torch
from torch.utils.data import DataLoader
from transformers import AdamW, get_linear_schedule_with_warmup
import wandb

def train_model(model, train_loader, val_loader, epochs=3):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model.to(device)
    
    optimizer = AdamW(model.parameters(), lr=2e-5)
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=len(train_loader) // 10,
        num_training_steps=len(train_loader) * epochs
    )
    
    # Loss functions
    sentiment_criterion = nn.CrossEntropyLoss()
    sarcasm_criterion = nn.BCEWithLogitsLoss()
    toxicity_criterion = nn.BCEWithLogitsLoss()
    
    wandb.init(project="ltsr-sentiment", name="roberta-multitask-v1")
    
    for epoch in range(epochs):
        model.train()
        total_loss = 0
        
        for batch in train_loader:
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            sentiment_labels = batch['sentiment'].to(device)
            sarcasm_labels = batch['sarcasm'].to(device)
            toxicity_labels = batch['toxicity'].to(device)
            
            outputs = model(input_ids, attention_mask)
            
            # Multi-task loss
            loss_sentiment = sentiment_criterion(outputs['sentiment'], sentiment_labels)
            loss_sarcasm = sarcasm_criterion(outputs['sarcasm'].squeeze(), sarcasm_labels.float())
            loss_toxicity = toxicity_criterion(outputs['toxicity'].squeeze(), toxicity_labels.float())
            
            # Weighted sum (can tune weights)
            loss = loss_sentiment + 0.5 * loss_sarcasm + 0.3 * loss_toxicity
            
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            
            total_loss += loss.item()
            wandb.log({
                'loss': loss.item(),
                'loss_sentiment': loss_sentiment.item(),
                'loss_sarcasm': loss_sarcasm.item(),
                'loss_toxicity': loss_toxicity.item()
            })
        
        # Validation
        val_metrics = evaluate_model(model, val_loader, device)
        wandb.log(val_metrics)
        
        print(f"Epoch {epoch+1}/{epochs}, Loss: {total_loss/len(train_loader):.4f}")
```

#### Inference Server

**FastAPI ML Server**:
```python
# inference/server.py
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import torch

app = FastAPI()

# Load model at startup
model = RobertaMultiTask()
model.load_state_dict(torch.load('/models/roberta-multitask-latest.pt'))
model.eval()
tokenizer = RobertaTokenizer.from_pretrained('roberta-large')

class PredictionRequest(BaseModel):
    texts: List[str]

class PredictionResponse(BaseModel):
    predictions: List[dict]

@app.post("/predict", response_model=PredictionResponse)
async def predict(request: PredictionRequest):
    # Tokenize
    encoded = tokenizer(
        request.texts,
        padding=True,
        truncation=True,
        max_length=512,
        return_tensors='pt'
    )
    
    # Inference
    with torch.no_grad():
        outputs = model(encoded['input_ids'], encoded['attention_mask'])
    
    # Parse results
    predictions = []
    for i in range(len(request.texts)):
        sentiment_probs = torch.softmax(outputs['sentiment'][i], dim=0)
        sentiment_label = torch.argmax(sentiment_probs).item()
        
        sarcasm_prob = torch.sigmoid(outputs['sarcasm'][i]).item()
        toxicity_prob = torch.sigmoid(outputs['toxicity'][i]).item()
        
        predictions.append({
            'sentiment': {
                'label': ['positive', 'neutral', 'negative'][sentiment_label],
                'score': float(sentiment_probs[sentiment_label]),
                'confidence': float(sentiment_probs[sentiment_label])
            },
            'sarcasm': {
                'is_sarcastic': sarcasm_prob > 0.6,
                'confidence': sarcasm_prob
            },
            'toxicity': {
                'is_toxic': toxicity_prob > 0.7,
                'confidence': toxicity_prob
            }
        })
    
    return PredictionResponse(predictions=predictions)
```

#### Entity Linking (spaCy)

```python
# models/entity_linker.py
import spacy
from fuzzywuzzy import fuzz

class CastEntityLinker:
    def __init__(self, cast_dictionary: dict):
        self.nlp = spacy.load('en_core_web_lg')
        self.cast_dict = cast_dictionary
    
    def extract_mentions(self, text: str):
        doc = self.nlp(text)
        mentions = []
        
        # Exact match
        for cast in self.cast_dict['cast']:
            for alias in cast['aliases']:
                if alias.lower() in text.lower():
                    mentions.append({
                        'cast_member': cast['canonical_name'],
                        'confidence': 0.95,
                        'method': 'exact'
                    })
        
        # Fuzzy match (if no exact match)
        if not mentions:
            for cast in self.cast_dict['cast']:
                score = fuzz.partial_ratio(
                    text.lower(),
                    cast['canonical_name'].lower()
                )
                if score >= 85:
                    mentions.append({
                        'cast_member': cast['canonical_name'],
                        'confidence': score / 100,
                        'method': 'fuzzy'
                    })
        
        # Coreference resolution
        if doc._.coref_chains:
            for chain in doc._.coref_chains:
                # Logic for pronoun resolution
                pass
        
        return mentions
```

---

### 4. Infrastructure & DevOps

#### Docker Configuration

**Backend Dockerfile**:
```dockerfile
# Dockerfile (backend)
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Expose port
EXPOSE 8000

# Run with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Frontend Dockerfile**:
```dockerfile
# Dockerfile (frontend)
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

**Docker Compose** (Development):
```yaml
# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: ltsr
      POSTGRES_USER: ltsr_user
      POSTGRES_PASSWORD: ltsr_pass
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  backend:
    build: ./src/backend
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis
    environment:
      DATABASE_URL: postgresql://ltsr_user:ltsr_pass@postgres:5432/ltsr
      REDIS_URL: redis://redis:6379/0
    volumes:
      - ./src/backend:/app

  celery_worker:
    build: ./src/backend
    command: celery -A workers.celery_app worker --loglevel=info
    depends_on:
      - postgres
      - redis
    environment:
      DATABASE_URL: postgresql://ltsr_user:ltsr_pass@postgres:5432/ltsr
      REDIS_URL: redis://redis:6379/0

  frontend:
    build: ./src/frontend
    ports:
      - "5173:80"
    depends_on:
      - backend

volumes:
  postgres_data:
```

#### Kubernetes Deployment

**Backend Deployment**:
```yaml
# kubernetes/backend/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ltsr-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ltsr-backend
  template:
    metadata:
      labels:
        app: ltsr-backend
    spec:
      containers:
      - name: backend
        image: ltsr/backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: ltsr-secrets
              key: database-url
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

#### CI/CD: GitHub Actions

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov
      
      - name: Run tests
        run: pytest tests/ --cov=src/
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Build Docker images
        run: |
          docker build -t ltsr/backend:${{ github.sha }} ./src/backend
          docker build -t ltsr/frontend:${{ github.sha }} ./src/frontend
      
      - name: Push to registry
        run: |
          docker push ltsr/backend:${{ github.sha }}
          docker push ltsr/frontend:${{ github.sha }}

  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to Kubernetes
        run: |
          kubectl set image deployment/ltsr-backend backend=ltsr/backend:${{ github.sha }}
          kubectl set image deployment/ltsr-frontend frontend=ltsr/frontend:${{ github.sha }}
```

---

### 5. Monitoring & Observability

#### Application Monitoring: Datadog

```python
# utils/monitoring.py
from ddtrace import tracer, patch_all
from ddtrace.contrib.fastapi import patch as patch_fastapi

# Enable auto-instrumentation
patch_all()
patch_fastapi()

# Custom metrics
from datadog import statsd

def track_sentiment_accuracy(accuracy: float):
    statsd.gauge('ltsr.model.accuracy', accuracy)

def track_api_latency(endpoint: str, latency_ms: float):
    statsd.histogram(f'ltsr.api.latency.{endpoint}', latency_ms)

def track_reddit_api_calls(count: int):
    statsd.increment('ltsr.reddit.api_calls', count)
```

#### Logging: Structured Logging

```python
# utils/logger.py
import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
        }
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        return json.dumps(log_data)

def get_logger(name: str):
    logger = logging.getLogger(name)
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger
```

#### Error Tracking: Sentry

```python
# main.py
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    integrations=[FastApiIntegration()],
    traces_sample_rate=0.1,  # 10% of requests
    environment=os.getenv("ENV", "development")
)
```

---

### 6. Security

#### Authentication: Auth0

```python
# api/dependencies.py
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            os.getenv("AUTH0_PUBLIC_KEY"),
            algorithms=["RS256"],
            audience=os.getenv("AUTH0_AUDIENCE")
        )
        return payload
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Usage in routes
@app.get("/api/threads")
async def get_threads(user = Depends(verify_token)):
    # user is now authenticated
    pass
```

#### Secrets Management: AWS Secrets Manager

```python
# config.py
import boto3
import json

def get_secret(secret_name: str):
    client = boto3.client('secretsmanager', region_name='us-east-1')
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# Load secrets at startup
REDDIT_CREDENTIALS = get_secret('ltsr/reddit-api')
DATABASE_PASSWORD = get_secret('ltsr/database')['password']
```

---

### 7. Performance Optimization

#### Database Query Optimization

```python
# Eager loading (avoid N+1 queries)
from sqlalchemy.orm import joinedload

threads = session.query(Thread).options(
    joinedload(Thread.comments),
    joinedload(Thread.aggregates)
).all()

# Pagination
def get_threads_paginated(page: int, page_size: int = 20):
    offset = (page - 1) * page_size
    return session.query(Thread).offset(offset).limit(page_size).all()

# Connection pooling
engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600
)
```

#### Caching Strategy

```python
from functools import wraps
import json

def cache_result(ttl: int = 300):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{json.dumps(args)}:{json.dumps(kwargs)}"
            
            # Check cache
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
            
            # Compute
            result = await func(*args, **kwargs)
            
            # Store in cache
            redis_client.setex(cache_key, ttl, json.dumps(result))
            
            return result
        return wrapper
    return decorator

# Usage
@cache_result(ttl=300)
async def get_cast_analytics(thread_id: str, cast_member: str):
    # Expensive computation
    return analytics
```

#### ML Batch Inference

```python
# Batch processing for efficiency
def classify_comments_batch(comments: List[str], batch_size: int = 32):
    results = []
    
    for i in range(0, len(comments), batch_size):
        batch = comments[i:i+batch_size]
        
        # Tokenize batch
        encoded = tokenizer(
            batch,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors='pt'
        )
        
        # Inference
        with torch.no_grad():
            outputs = model(encoded['input_ids'], encoded['attention_mask'])
        
        results.extend(parse_outputs(outputs))
    
    return results
```

---

### 8. Testing Stack

```python
# Dependencies
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
pytest-mock==3.12.0
httpx==0.25.2  # For testing FastAPI
factory-boy==3.3.0  # Test data factories
```

**Test Configuration**:
```python
# conftest.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

TEST_DATABASE_URL = "postgresql://test:test@localhost:5432/ltsr_test"

@pytest.fixture
def client():
    engine = create_engine(TEST_DATABASE_URL)
    TestingSessionLocal = sessionmaker(bind=engine)
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    # Override dependency
    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as c:
        yield c
    
    # Drop tables
    Base.metadata.drop_all(bind=engine)
```

---

## Development Environment Setup

### Prerequisites
- Python 3.11+
- Node.js 20+
- Docker 24+
- PostgreSQL 15+
- Redis 7+

### Quick Start

```bash
# 1. Clone repository
git clone https://github.com/company/socializer.git
cd socializer

# 2. Run setup script
./scripts/setup.sh

# 3. Configure environment
cp .env.example .env
# Edit .env with your credentials

# 4. Start services
docker-compose up -d

# 5. Run migrations
./scripts/migrate.sh

# 6. Seed data
./scripts/seed_data.sh

# 7. Start development servers
./scripts/run_dev.sh

# Backend: http://localhost:8000
# Frontend: http://localhost:5173
# API Docs: http://localhost:8000/api/docs
```

---

**Last Updated**: October 16, 2025  
**Version**: 1.0  
**Maintained By**: Engineering Team