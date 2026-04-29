## Frontend Deploy Surface

This folder exists as a clean frontend boundary for future separation.

Current Vercel deployment is locked to static root files via `vercel.json`:
- `index.html`
- `style.css`
- `script.js`
- image assets

This prevents accidental invocation of backend Python code (`app/`) on Vercel.

For a full split later:
1. Move static files into this `frontend/` folder.
2. Update `vercel.json` routes/builds to point to `frontend/*`.
3. Keep bot backend deployed separately on Render.
