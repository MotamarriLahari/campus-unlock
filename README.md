# Campus Unlock – full-stack version
FastAPI + SQLite backend serving the frontend.
Run locally:  pip install -r requirements.txt && uvicorn server:app --port 8000   → http://localhost:8000
Deploy: push this folder to GitHub → Render "New Web Service" (render.yaml included).
Note: Render's free disk resets on redeploy; use Render Postgres/Supabase for permanent storage.
Server-side protections: contact validation, duplicate-contact blocking, 5 sign-ups/hour/IP, referral codes issued
by the server and only accepted if they exist (no self-made codes). ALLOW_DEMO=0 disables the simulate button.
