# ScholarFlow Backend

**AI-native Research Operating System** powered by LangGraph Multi-Agent Workflows

## 🎯 Architecture Overview

This backend implements a **cyclic, stateful multi-agent system** using LangGraph to power ScholarFlow's Research and Studio modes.

### Key Features

- **Discovery Loop**: Iterative paper search with automatic query refinement
- **Review Loop**: AI-powered draft revision with quality control
- **Multimodal Analysis**: Gemini Vision for analyzing charts, images, and figures
- **RAG with FAISS**: Context-aware responses using vector similarity search
- **Server-Sent Events**: Real-time streaming updates to frontend
- **Project Isolation**: Each project has its own vector index and chat history

---

## 🏗️ Tech Stack

- **Framework**: FastAPI (async)
- **Orchestration**: LangGraph (cyclic workflows)
- **AI Models**: Google Gemini 1.5 Pro + Vision
- **Vector DB**: FAISS (local, no external dependencies)
- **Database**: SQLAlchemy (SQLite dev / PostgreSQL prod)
- **Embeddings**: sentence-transformers (all-MiniLM-L6-v2)

---

## 📊 LangGraph Workflow Architecture

### The Agentic Workforce

```
┌─────────────┐
│   Router    │  ← Entry: Classify intent
└──────┬──────┘
       │
   ┌───┴───┬────────┬────────┐
   │       │        │        │
   ▼       ▼        ▼        ▼
Search  Planner  LabAnalyst Writer
SubGraph SubGraph  (Vision)  (RAG)
   │       │        │        │
   └───────┴────────┴────────┘
              │
              ▼
          [Reviewer]
              │
           ┌──┴──┐
           │     │
       Revise  Approve
     (loop back)  (END)
```

### Discovery Loop (Search Refinement)

```
Search → Ranker → [Check Relevance]
            ↑            │
            │        Score < 0.6?
            │            │
       [Refine Query] ←─┘
                     (max 3 iterations)
```

### Review Loop (Draft Revision)

```
Writer → Reviewer → [Check Quality]
  ↑                      │
  │                  Needs revision?
  └──────────────────────┘
        (max 2 revisions)
```

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd backend
pip install poetry
poetry install
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY
```

### 3. Initialize Database

```bash
poetry run python -m app.models.database
```

### 4. Run Server

```bash
poetry run uvicorn app.main:app --reload
```

Server will start at `http://localhost:8000`

- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

---

## 📁 Project Structure

```
backend/
├── app/
│   ├── core/
│   │   ├── config.py           # Settings & environment
│   │   └── gemini_client.py    # Gemini API singleton
│   ├── models/
│   │   ├── database.py         # SQLAlchemy models
│   │   └── schemas.py          # Pydantic schemas
│   ├── services/
│   │   ├── lab_analyst.py      # Gemini Vision service
│   │   └── vector_store.py     # FAISS operations
│   ├── agents/
│   │   ├── state.py            # LangGraph state definition
│   │   ├── nodes.py            # Individual agent implementations
│   │   └── graph.py            # ⭐ CORE: Cyclic workflow definition
│   ├── api/
│   │   ├── projects.py         # Project CRUD
│   │   ├── lab.py              # Lab asset upload/analysis
│   │   └── chat.py             # SSE streaming endpoints
│   └── main.py                 # FastAPI application
├── data/
│   ├── indexes/                # FAISS vector indexes (per project)
│   └── uploads/                # User-uploaded files
├── pyproject.toml
└── .env
```

---

## 🔑 Key Endpoints

### Project Management

- `POST /projects` - Create new project
- `GET /projects` - List all projects
- `GET /projects/{id}` - Get project details
- `DELETE /projects/{id}` - Delete project

### Lab (Multimodal Assets)

- `POST /lab/projects/{id}/upload` - Upload image/CSV (triggers Vision analysis)
- `GET /lab/projects/{id}` - List project assets
- `POST /lab/assets/{id}/reanalyze` - Re-analyze with custom prompt

### Chat & Workflow (SSE Streaming)

- `POST /chat/stream` - Run full LangGraph workflow with real-time updates
- `POST /chat/draft-section` - Stream section drafting

---

## 💡 Usage Examples

### Upload and Analyze an Image

```python
import httpx

files = {"file": open("chart.png", "rb")}
data = {"name": "Results Chart", "asset_type": "image"}

response = httpx.post(
    "http://localhost:8000/lab/projects/{project_id}/upload",
    files=files,
    data=data
)

print(response.json()["ai_description"])
# Output: "Figure shows a line graph with accuracy on Y-axis..."
```

### Stream Workflow Execution

```javascript
const eventSource = new EventSource('http://localhost:8000/chat/stream', {
  method: 'POST',
  body: JSON.stringify({
    project_id: "...",
    message: "Find papers on transformers",
    selected_paper_ids: [],
    lab_asset_ids: []
  })
});

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  if (data.type === 'log') {
    console.log(`[${data.data.source}] ${data.data.message}`);
  } else if (data.type === 'text') {
    console.log('Draft:', data.data);
  }
};
```

---

## 🧪 Testing LangGraph Workflow

### Manual Test

```bash
poetry run python -c "
from app.agents.graph import research_graph
from app.agents.state import create_initial_state

state = create_initial_state(
    query='Find papers on efficient transformers',
    project_id='test-123'
)

for s in research_graph.stream(state):
    print(s.get('logs', []))
"
```

---

## 🔧 Configuration

Edit `.env` or `app/core/config.py`:

| Setting | Description | Default |
|---------|-------------|---------|
| `max_search_iterations` | Discovery Loop limit | 3 |
| `max_revision_iterations` | Review Loop limit | 2 |
| `relevance_threshold` | Paper quality cutoff | 0.6 |

---

## 📝 Database Schema

### Core Entities

- **Project**: Isolation context (one vector index per project)
- **LibraryItem**: PDF metadata + vector reference
- **LabAsset**: Image/CSV with AI description
- **Draft**: Structured content blocks
- **ChatSession**: Message history

---

## 🎨 Extending the Workflow

### Add a Custom Agent Node

1. Define node in `app/agents/nodes.py`:

```python
async def my_custom_node(state: ResearchState) -> Dict:
    # Your logic here
    return {
        "custom_field": "value",
        "logs": [{"source": "CustomAgent", "message": "Done!"}]
    }
```

2. Register in `app/agents/graph.py`:

```python
graph.add_node("my_node", my_custom_node)
graph.add_edge("some_node", "my_node")
```

---

## 🐛 Troubleshooting

### "Module not found" errors
```bash
poetry install
```

### FAISS dimension mismatch
```bash
# Delete existing indexes
rm -rf data/indexes/*
```

### Database locked (SQLite)
Switch to PostgreSQL for production in `.env`:
```
DATABASE_URL=postgresql://user:pass@localhost/scholarflow
```

---

## 📚 References

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Google Gemini API](https://ai.google.dev/docs)
- [FastAPI](https://fastapi.tiangolo.com/)
- [FAISS](https://github.com/facebookresearch/faiss)

---

## 🤝 Contributing

This backend is designed to be **production-ready** with:
- ✅ Proper error handling
- ✅ Async/await throughout
- ✅ Type hints (Pydantic/TypedDict)
- ✅ Database transactions
- ✅ Configurable via environment

**Next Steps for Production**:
1. Add authentication (JWT)
2. Implement rate limiting
3. Add Redis for caching
4. Deploy vector store to Qdrant/Weaviate for scale
