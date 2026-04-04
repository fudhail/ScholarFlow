# ScholarFlow - AI-Powered Academic Research System

**ScholarFlow** is a unified operating system for academic research that bridges the gap between literature discovery, deep reading, and manuscript co-authoring using Google Gemini, Ollama, and advanced RAG agents.

## 🌟 Features

- **Hybrid Intelligence**: seamlessly switches between local LLMs (Ollama/Llama 3) for privacy/speed and Cloud AI (Gemini Pro) for complex reasoning.
- **Deep Research Agent**: Autonomous multi-step research workflow (Plan → Search → Read → Synthesize).
- **Interactive Reading**: PDF viewer with integrated AI context awareness and active note-taking.
- **Academic Studio**: Split-screen LaTeX-like editor with real-time AI drafting and citation integration.
- **Avatar Interface**: Anam.ai integration for a conversational research partner.

## 🏗 System Architecture

ScholarFlow is built on a modern stack designed for performance and extensibility:

### Backend (Python/FastAPI)
- **Framework**: FastAPI with async support
- **AI Orchestration**: LangGraph for stateful multi-agent workflows
- **Vector Store**: FAISS for local, efficient similarity search
- **Search**: Direct integration with ArXiv (via robust `urllib` client) and Google Scholar
- **Database**: SQLite with SQLAlchemy & Alembic migrations

### Frontend (React/Vite)
- **Core**: React 19 + TypeScript
- **State**: Zustand for global store management
- **Styling**: Tailwind CSS with custom academic theme
- **Visualization**: React Flow for agent thought process visualization
- **Editor**: Monaco Editor for LaTeX/Markdown authoring

## 🚀 Getting Started

### Option A: Hybrid Setup (Recommended for Windows + macOS)

Use Docker Compose for shared onboarding and keep native commands for fast local iteration.

#### Docker (shared, reproducible)

```bash
# From repo root
docker compose up --build
```

Services:

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`

Stop containers:

```bash
docker compose down
```

#### Native (quick local iteration)

Backend:

```bash
cd backend
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend (new terminal at repo root):

```bash
npm install
npm run dev
```

Tip: `npm run dev:docker`, `npm run docker:down`, and `npm run docker:logs` are included as convenience wrappers.

### Prerequisites

- **Python 3.11+**
- **Node.js 20+**
- **Ollama** (optional, recommended for hybrid mode)
- **Google AI Studio Key** (for Gemini models)

### 1. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env with your API keys (see Configuration below)

# Initialize Database
alembic upgrade head

# Run Server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Frontend Setup

```bash
# In the root directory
npm install

# Start Development Server
npm run dev
```

Visit `http://localhost:5173` to open ScholarFlow.

## ⚙️ Configuration

Create a `.env` file in the `backend/` directory:

```ini
# Core
DATABASE_URL=sqlite:///./scholarflow.db
UPLOAD_PATH=./data/uploads
FAISS_INDEX_PATH=./data/indexes

# AI Providers
GOOGLE_API_KEY=your_gemini_api_key_here
ANAM_API_KEY=your_anam_key_optional

# Model Configuration
LLM_PROVIDER=hybrid  # gemini, ollama, or hybrid
TEXT_MODEL_NAME=scholarmate
FAST_MODEL_NAME=scholarmate
VISION_MODEL_NAME=gemini-1.5-flash

# Ollama Settings (if using hybrid/ollama)
OLLAMA_BASE_URL=http://localhost:11434
```

## 🧠 Model Setup (Ollama)

For the best experience in Hybrid mode, pull these models:

```bash
ollama pull llama3
ollama pull nomic-embed-text
```

## 🛠 Project Structure

```
scholarflow/
├── backend/
│   ├── app/
│   │   ├── agents/     # LangGraph agent definitions (Nodes, Graph)
│   │   ├── api/        # FastAPI endpoints
│   │   ├── core/       # Config & Security
│   │   ├── models/     # Database Schemas & Pydantic models
│   │   └── services/   # External integrations (ArXiv, Vector Store)
│   └── data/           # Local storage (DB, Uploads, Indices)
│
├── src/                # Frontend Source
│   ├── components/     # React Components
│   ├── stores/         # State Management (Zustand)
│   └── types/          # TypeScript Definitions
```

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
