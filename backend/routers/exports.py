"""Export-Endpunkt: fertigen Lebenslauf als PDF oder Word herunterladen."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from backend import schemas
from backend.services import export_service

router = APIRouter(tags=["Exports"])

_MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.post("/api/export")
def export_cv(req: schemas.ExportRequest):
    safe_name = export_service.sanitize_filename(req.filename)
    photo_bytes = export_service.decode_photo(req.photo)

    if req.format == "docx":
        data = export_service.to_docx(req.content, req.design, req.language, photo=photo_bytes)
    elif req.format == "pdf":
        data = export_service.to_pdf(req.content, req.design, req.language, photo=photo_bytes)
    else:
        raise HTTPException(422, "Format muss 'pdf' oder 'docx' sein.")

    filename = f"{safe_name}_{req.design}.{req.format}"
    return Response(
        content=data,
        media_type=_MEDIA_TYPES[req.format],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
