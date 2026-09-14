# GitHub and Vercel deployment

## 1. GitHub repository

The deployment repository is [kennygeemartin/MedAI_LLM](https://github.com/kennygeemartin/MedAI_LLM). Keep `.env`, databases, tokens, model weights, and patient data out of GitHub. `.gitignore` is supplied.

With Git and GitHub CLI installed and authenticated:

```powershell
git init -b main
git add .
git commit -m "Build MedAI healthcare education application"
git remote add origin https://github.com/kennygeemartin/MedAI_LLM.git
git push -u origin main
```

These commands are for an initial upload to an empty repository. Once published, clone the repository for subsequent work. GitHub Actions runs application tests and JavaScript syntax validation.

## 2. Persistent PostgreSQL

Provision PostgreSQL with your chosen provider, such as a provider available through Vercel Marketplace. Use the provider's required SSL settings and a pooled connection string if appropriate. Save the connection string as `DATABASE_URL` in your local ignored `.env` temporarily to initialize production.

Set a random `JWT_SECRET` and `APP_ENV=production` in the same file, then run:

```powershell
.\.venv\Scripts\python.exe -m backend.manage init-db
.\.venv\Scripts\python.exe -m backend.manage create-admin
.\.venv\Scripts\python.exe -m backend.seed
```

These commands target the database selected by `DATABASE_URL`. `init-db` creates missing tables; it is not an upgrade migration tool. Use a separate development `.env` when returning to local work. Do not put production database initialization into every Vercel cold start.

## 3. Vercel

1. Import the GitHub repository into the intended Vercel team.
2. Keep the repository root as the root directory and choose **FastAPI**. The root `main.py` exports `app`; `vercel.json` selects the framework.
3. Add `DATABASE_URL`, `JWT_SECRET`, and `APP_ENV=production` to production environment variables. Use separate settings for previews.
4. Leave inference variables unset for the first evidence-library deployment, or set both variables once the GPU service is ready.
5. Deploy, then open `/api/health` and confirm `status: ok`.
6. Sign in as the administrator, review the imported drafts, and publish suitable content. Register a test patient and run the smoke checks below.

Alternatively, with Vercel CLI installed and authenticated, run `vercel` to link/deploy a preview and `vercel --prod` for production. Never pass secret values in command-line arguments or commit them.

Vercel's [FastAPI guide](https://vercel.com/docs/frameworks/backend/fastapi) documents the supported entry point and static-file handling. Heavy model dependencies and weights are intentionally excluded from its function bundle. A Vercel deployment is not a GPU model host.

## 4. Private MedGemma service

The user operating the Hugging Face account must review and accept the [MedGemma access terms](https://huggingface.co/google/medgemma-4b-it). Set `HF_TOKEN` in the GPU host's secret store. Select a CUDA host with enough memory for the model, its context, and runtime overhead; confirm performance with the workload before committing to a hosting plan.

Build from the repository root:

```sh
docker build -f inference/Dockerfile -t medai-inference .
docker run --gpus all --env-file /secure/path/inference.env -p 127.0.0.1:8001:8001 medai-inference
```

The private environment file needs `HF_TOKEN`, a random `INFERENCE_API_KEY` of at least 32 characters, and optionally `MODEL_ID=google/medgemma-4b-it`. Use an HTTPS reverse proxy or the host's managed HTTPS ingress. Authenticate requests with the shared key and restrict access where the provider supports it. Do not expose the service's unencrypted port publicly. Use a persistent model cache for faster restarts.

Set Vercel `INFERENCE_URL` to the HTTPS base URL (without `/generate`) and `INFERENCE_API_KEY` to the matching shared key, then redeploy. The health endpoint reports configuration presence, **not** successful GPU inference. Verify an actual answer has `mode: medgemma`. The web app falls back to reviewed excerpts on timeouts, rejected output, or service failure.

The GPU container and actual model download/inference must be tested on the target host. They are not exercised by the CPU-only API suite. The service serializes generation with a lock and returns 503 when busy; run one worker per model instance. Its relevance threshold is a research default, not a validated clinical threshold.

## Smoke checks

- `/api/health` succeeds and the site loads its CSS/JS.
- Register, sign out, sign in, and reload conversation history.
- Draft articles do not appear in the library; published articles do.
- Ask a matching question and check its source links and mode label.
- Ask a question with no matching evidence and confirm it does not fabricate an answer.
- A severe-breathing-difficulty message triggers urgent-help guidance without waiting for AI.
- A second patient cannot access the first patient's conversations.
- Feedback updates the report; conversation deletion removes messages and feedback.
- Only administrators can access management endpoints.

## Deployment status

Implementation session, 15 September 2026:

- Local application started and `/api/health` verified.
- API tests and desktop/mobile browser workflows passed.
- GitHub repository `kennygeemartin/MedAI_LLM` is connected and write access was verified.
- Vercel integration was found but is not installed/connected yet.
- No production PostgreSQL URL, GPU endpoint, or Hugging Face model credential was available.
- Source publication targets the linked GitHub repository. No Vercel deployment or live MedGemma inference has been verified.

Next: connect Vercel to `kennygeemartin/MedAI_LLM`; configure PostgreSQL and initialize it. The web app can then be deployed in evidence-library mode, followed by GPU inference once provisioned. Record live URLs here after verification.
