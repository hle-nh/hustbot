# HUSTBot Frontend

This folder contains the React/Vite frontend for HUSTBot. It provides the chat interface, conversation sidebar, source citation cards, typing states, and API integration with the FastAPI backend.

## Responsibilities

- Render the main chatbot interface.
- Send user questions to the backend `/chat` API.
- Display assistant answers and source references.
- Manage conversation state on the client side.
- Provide a local Vite development server for demo and testing.

## Project Structure

```text
frontend/
├── public/              # Static icons and favicon
├── src/
│   ├── api/             # Backend API client
│   ├── assets/          # UI images and logos
│   ├── components/      # Chat UI components
│   ├── store/           # Client-side state
│   ├── App.tsx
│   └── main.tsx
├── package.json
└── vite.config.ts
```

## Setup

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server runs at:

```text
http://localhost:5173
```

The frontend expects the backend API to be available at:

```text
http://localhost:8000
```

## Useful Commands

```bash
npm run dev      # Start local development server
npm run build    # Type-check and build production assets
npm run lint     # Run ESLint
npm run preview  # Preview the production build locally
```
