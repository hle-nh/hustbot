# HUSTBot

HUSTBot is a Vietnamese academic advising chatbot for Hanoi University of Science and Technology. The project uses a retrieval-augmented generation pipeline over official academic documents, with a FastAPI backend and a React/Vite frontend.

## Project Structure

```text
backend/    FastAPI API, RAG pipeline, ingestion, evaluation scripts
frontend/   React/Vite chatbot interface
data/       Official source documents and prepared datasets
```

## Run Locally

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Create `backend/.env` from `backend/.env.example` and set the required API keys before starting the server.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend runs on `http://localhost:5173` by default and calls the backend at `http://localhost:8000`.

## Demo Helpers

On Windows, the demo can be started with:

```bat
start_demo.cmd
```

This launches both backend and frontend using the local environment.
