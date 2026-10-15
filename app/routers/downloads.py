from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import AppError
from app.link_pages import render_link_error, render_link_landing
from app.rate_limit import client_ip, enforce_download_rate_limit, rate_limit_downloads
from app.schemas import CodeDownloadIn, LinkShareOut
from app.services.files import get_file_by_code, get_link_share_info, get_public_file

router = APIRouter(tags=["public"])


@router.get("/d/{token}/info", response_model=LinkShareOut, dependencies=[Depends(rate_limit_downloads)])
def link_share_info(token: str, db: Session = Depends(get_db)) -> LinkShareOut:
    record, sender_email = get_link_share_info(db, token)
    return LinkShareOut(
        filename=record.original_name,
        size=record.size,
        content_type=record.content_type,
        sender_email=sender_email,
        expires_at=record.expires_at,
        download_url=f"/d/{token}/download",
    )


@router.get("/d/{token}/download", dependencies=[Depends(rate_limit_downloads)])
def download_file(token: str, db: Session = Depends(get_db)) -> FileResponse:
    record, path = get_public_file(db, token)
    return FileResponse(path, media_type=record.content_type, filename=record.original_name)


@router.get("/d/{token}", response_class=HTMLResponse)
def link_landing(token: str, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    # Errors here must render as HTML, so the limit is checked inline instead of via a dependency.
    try:
        enforce_download_rate_limit(client_ip(request))
        record, sender_email = get_link_share_info(db, token)
    except AppError as exc:
        title = "Link expired" if exc.status_code == 410 else "Link unavailable"
        return HTMLResponse(
            render_link_error(title=title, message=exc.message),
            status_code=exc.status_code,
            headers=exc.headers,
        )
    return HTMLResponse(
        render_link_landing(
            sender_email=sender_email,
            filename=record.original_name,
            size=record.size,
            expires_at=record.expires_at,
            download_path=f"/d/{token}/download",
        )
    )


@router.post("/d/code", dependencies=[Depends(rate_limit_downloads)])
def download_by_code(body: CodeDownloadIn, db: Session = Depends(get_db)) -> FileResponse:
    record, path = get_file_by_code(db, body.code, body.password)
    return FileResponse(path, media_type=record.content_type, filename=record.original_name)
