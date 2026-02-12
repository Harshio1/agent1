# CodePilot Frontend

TypeScript + Next.js 14 (App Router) frontend for the CodePilot autonomous coding agent.

## Architecture

- **Framework**: Next.js 14 App Router (`app/` directory), optimized for deployment on Vercel.
- **UI**: Tailwind CSS, dark theme by default with a client-side theme toggle in `components/Navbar.tsx`.
- **State & UX**:
  - `app/page.tsx` is a small client component that orchestrates:
    - Input via `components/ChatInput.tsx`
    - Result sections via `components/ResultSection.tsx`
    - Rich, typed subviews:
      - `IntentCard` for intent classification
      - `PlanningSection` for the engineering plan
      - `TestResults` for test outcomes
      - `DebugResult` for debugging information
      - `ExecutionTimeline` for the execution log
      - `RequestMeta` for displaying and copying the request ID
    - Loading skeletons via `components/LoadingSkeleton.tsx`
    - Toast notifications via `components/ToastProvider.tsx`
- **API Layer**:
  - All backend communication is centralized in `lib/api.ts`.
  - `runCodePilot` handles:
    - `POST /solve` calls to the CodePilot backend
    - Timeouts via `AbortController`
    - Network failure handling and user-friendly `CodePilotError`s
    - Normalization of backend responses into a typed `CodePilotResponse` (`types/index.ts`)
  - A `runCodePilotStream` stub is included to support future streaming responses without changing the UI.
- **Error Handling**:
  - Global error boundary in `app/error.tsx` for runtime UI failures.
  - Toast-based surfaced backend errors using `ToastProvider` + `useToast`.

## Environment

- `NEXT_PUBLIC_API_BASE` (optional): Base URL for the CodePilot backend.
  - Defaults to `http://127.0.0.1:8000` for local development.

## Development

```bash
cd frontend
npm install
npm run dev
```

Then open `http://localhost:3000`.

Ensure the CodePilot backend is running and reachable at `NEXT_PUBLIC_API_BASE`.

## Deploying to Vercel

This project is ready for Vercel:

- App Router + `app/` directory.
- `next.config.mjs` with `output: "standalone"` for optimized production bundles.

Basic steps:

1. Push this repository to GitHub/GitLab/Bitbucket.
2. Create a new Vercel project and select the `frontend` folder as the root (if using a monorepo).
3. Set the environment variable:
   - `NEXT_PUBLIC_API_BASE` → your production CodePilot backend URL.
4. Use the default Next.js build settings:
   - Build command: `npm run build`
   - Output: `.next`

After deployment, the frontend will call your backend through `NEXT_PUBLIC_API_BASE` while preserving the same UI and API contracts used in development.

