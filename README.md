JPG Optimiser
=================

Quickstart (development)
------------------------

- Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

- Install dependencies:

```bash
pip install -r requirements.txt
```

- Video processing requires `ffmpeg` to be installed and available on `PATH`.

- Run the dev server (auto-reload):

```bash
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

- Verify: open `http://127.0.0.1:8000/health`

Files of interest
-----------------

- `backend/main.py`: FastAPI application and endpoints.
- `passenger_wsgi.py`: WSGI wrapper for Phusion Passenger (see notes).
- `frontend/`: static frontend HTML files (`index.html`, `converter.html`).

Deployment notes
----------------

- `passenger_wsgi.py` wraps the FastAPI ASGI app for Phusion Passenger:

```python
from a2wsgi import ASGIMiddleware
from backend.main import app
application = ASGIMiddleware(app)
```

- Build static frontend files before deploying if your host serves from `dist/`:

```bash
python scripts/build_dist.py
```

- For production ASGI servers consider:

```bash
gunicorn -k uvicorn.workers.UvicornWorker "backend.main:app" -w 4
```

API endpoints (important)
-------------------------

- `GET /health` — healthcheck
- `POST /process` — add logo to banners
- `POST /optimize` — optimize images
- `POST /resize` — resize/adapt creatives
- `POST /convert` — convert image/video formats
- `GET /` and `GET /converter` — serve frontend index pages (if present in `frontend/` or `dist/`)

Testing
-------

- Run tests with `pytest` (requirements include `pytest` and `httpx`).
