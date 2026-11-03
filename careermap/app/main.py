"""CareerMap FastAPI Ana Uygulaması (V1 & V2)."""
import logging
import json
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from .routes import search_router, export_router
from .routes.v2 import (
    auth_router,
    employers_router,
    candidate_router,
    public_cv_router,
    applications_router,
    admin_router,
    research_router
)
from .routes.v2.candidate_api import view_secure_cv
from .professions.registry import ProfessionRegistry
from .database.db import init_db, get_cache_info, query_employers

# Logging yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("careermap")

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR = STATIC_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="CareerMap V2.6 Platformu (iPhone PWA & Ulusal İstihdam)",
    description="Akıllı İş Başvuru ve İletişim Yönetim Sistemi (iPhone PWA & Web)",
    version="2.6.0"
)

# CORS yapılandırması (Vercel, Next.js, React Native Expo ve iPhone PWA istemcileri için)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Statik dosyalar ve şablonlar
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# V1 Router'lar (Geriye Dönük Uyumluluk)
app.include_router(search_router)
app.include_router(export_router)

# V2 REST API Router'ları
app.include_router(auth_router)
app.include_router(employers_router)
app.include_router(candidate_router)
app.include_router(public_cv_router)
app.include_router(applications_router)
app.include_router(admin_router)
app.include_router(research_router)

@app.on_event("startup")
def on_startup():
    init_db()
    logger.info("CareerMap V2.0 başlatıldı. Veritabanı tabloları, aday profilleri ve REST API hazır.")

@app.get("/manifest.json")
def get_manifest():
    """PWA Web Uygulama Bildirimi (PWA Manifest)."""
    manifest_file = STATIC_DIR / "manifest.json"
    if manifest_file.exists():
        with open(manifest_file, "r", encoding="utf-8") as f:
            return JSONResponse(content=json.load(f), media_type="application/manifest+json")
    return JSONResponse(content={"short_name": "CareerMap", "name": "CareerMap V2.6"})

@app.get("/service-worker.js")
def get_service_worker():
    """PWA Service Worker Dosyası."""
    sw_file = STATIC_DIR / "service-worker.js"
    if sw_file.exists():
        return FileResponse(sw_file, media_type="application/javascript")
    return JSONResponse(status_code=404, content={"detail": "Service worker not found"})

@app.get("/offline.html")
def get_offline_page():
    """PWA Çevrimdışı Sayfası."""
    offline_file = STATIC_DIR / "offline.html"
    if offline_file.exists():
        return FileResponse(offline_file, media_type="text/html")
    return HTMLResponse("<h1>Çevrimdışı</h1>", status_code=503)

@app.get("/apple-touch-icon.png")
@app.get("/apple-touch-icon-180x180.png")
def get_apple_touch_icon():
    """Apple iOS Ana Ekran Simgesi."""
    icon_file = STATIC_DIR / "icons" / "apple-touch-icon-180x180.png"
    if not icon_file.exists():
        icon_file = STATIC_DIR / "apple-touch-icon.png"
    if icon_file.exists():
        return FileResponse(icon_file, media_type="image/png")
    return JSONResponse(status_code=404, content={"detail": "Icon not found"})

@app.get("/favicon.ico")
def get_favicon():
    """Favicon."""
    fav_file = STATIC_DIR / "icons" / "favicon.png"
    if fav_file.exists():
        return FileResponse(fav_file, media_type="image/png")
    return JSONResponse(status_code=404, content={"detail": "Favicon not found"})

@app.get("/cv/view/{token}", response_class=HTMLResponse)
def public_cv_view_shortcut(token: str):
    """30 günlük güvenli aday CV sayfası kısayolu."""
    return view_secure_cv(token)

@app.get("/app", response_class=HTMLResponse)
@app.get("/v2", response_class=HTMLResponse)
def v2_web_app(request: Request):
    """CareerMap V2.0 Modern Web Uygulaması (Tüm 7 Ekran + PWA)."""
    return templates.TemplateResponse(request=request, name="v2_app.html", context={
        "app_title": "CareerMap V2.0 — Akıllı İş Başvuru ve İletişim Platformu"
    })

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    """Anasayfa: V2 Modern Platformuna yönlendirme seçeneği ile birlikte."""
    professions = ProfessionRegistry.list_all()
    dentist_prof = ProfessionRegistry.get("dentist")
    districts = dentist_prof.supported_cities.get("Eskişehir", [])
    cache = get_cache_info("dentist", "Eskişehir")

    return templates.TemplateResponse(request=request, name="v2_app.html", context={
        "professions": professions,
        "active_profession": "dentist",
        "city": "Eskişehir",
        "districts": districts,
        "employer_types": dentist_prof.employer_types,
        "cache": cache
    })

@app.get("/results", response_class=HTMLResponse)
def results_page(request: Request):
    """V1 Klasik Sonuçlar Tablosu."""
    professions = ProfessionRegistry.list_all()
    dentist_prof = ProfessionRegistry.get("dentist")
    districts = dentist_prof.supported_cities.get("Eskişehir", [])
    cache = get_cache_info("dentist", "Eskişehir")

    return templates.TemplateResponse(request=request, name="results.html", context={
        "professions": professions,
        "active_profession": "dentist",
        "city": "Eskişehir",
        "districts": districts,
        "employer_types": dentist_prof.employer_types,
        "cache": cache
    })
