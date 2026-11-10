from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

if __package__:
    from .routers import homework, reservation
else:
    from routers import homework, reservation

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Unified FastAPI Application")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.include_router(homework.router)
app.include_router(reservation.router)


@app.get("/", response_class=HTMLResponse)
async def landing_page() -> str:
    return """
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Unified FastAPI Application</title>
        <script src="https://cdn.tailwindcss.com"></script>
      </head>
      <body class="min-h-screen bg-slate-100 text-slate-900">
        <main class="mx-auto max-w-3xl px-6 py-16">
          <h1 class="text-3xl font-bold">Unified FastAPI Application</h1>
          <p class="mt-2 text-slate-600">Choose an application to get started.</p>
          <nav class="mt-8 grid gap-4 sm:grid-cols-3">
            <a class="rounded-xl bg-white p-5 font-semibold shadow-sm ring-1 ring-slate-200 hover:ring-indigo-400"
               href="/homework-ui">CORS homework</a>
            <a class="rounded-xl bg-white p-5 font-semibold shadow-sm ring-1 ring-slate-200 hover:ring-indigo-400"
               href="/reservation/ui">Reservation dashboard</a>
            <a class="rounded-xl bg-white p-5 font-semibold shadow-sm ring-1 ring-slate-200 hover:ring-indigo-400"
               href="/docs">API documentation</a>
          </nav>
        </main>
      </body>
    </html>
    """
