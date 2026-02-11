"""HTML page routes."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from ..config import load_config

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    config = load_config()
    if config.system.first_run:
        return request.app.state.templates.TemplateResponse(
            "setup_wizard.html", {"request": request, "config": config}
        )
    return request.app.state.templates.TemplateResponse(
        "index.html", {"request": request, "config": config}
    )


@router.get("/cameras", response_class=HTMLResponse)
async def cameras_page(request: Request):
    config = load_config()
    return request.app.state.templates.TemplateResponse(
        "cameras.html", {"request": request, "config": config}
    )


@router.get("/recordings", response_class=HTMLResponse)
async def recordings_page(request: Request):
    config = load_config()
    return request.app.state.templates.TemplateResponse(
        "recordings.html", {"request": request, "config": config}
    )


@router.get("/cloud", response_class=HTMLResponse)
async def cloud_page(request: Request):
    config = load_config()
    return request.app.state.templates.TemplateResponse(
        "cloud.html", {"request": request, "config": config}
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    config = load_config()
    return request.app.state.templates.TemplateResponse(
        "settings.html", {"request": request, "config": config}
    )


@router.get("/wizard", response_class=HTMLResponse)
async def wizard_page(request: Request):
    config = load_config()
    return request.app.state.templates.TemplateResponse(
        "setup_wizard.html", {"request": request, "config": config}
    )
