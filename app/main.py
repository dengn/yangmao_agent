from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.db import init_db
from app.routes import benefits, cards, chat, offers, transactions


ROOT = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(ROOT / "templates"))

app = FastAPI(title="薅羊毛 Agent")


@app.on_event("startup")
def _startup():
    init_db()


app.include_router(cards.router)
app.include_router(benefits.router)
app.include_router(offers.router)
app.include_router(transactions.router)
app.include_router(chat.router)

static_dir = ROOT / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/cards", response_class=HTMLResponse)
def cards_page(request: Request):
    return templates.TemplateResponse(request, "cards.html")


@app.get("/offers", response_class=HTMLResponse)
def offers_page(request: Request):
    return templates.TemplateResponse(request, "offers.html")


@app.get("/chat", response_class=HTMLResponse)
def chat_page(request: Request):
    return templates.TemplateResponse(request, "chat.html")
