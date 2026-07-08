from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
import io
import os
import zipfile
from typing import Any, Iterable

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

try:  # pragma: no cover - import shim for direct execution
    from .banner_optimizer import OptimizationTask, process_optimization_batch
    from .image_processor import (
        ALLOWED_PLACEMENT_MODES,
        BannerTask,
        load_image_bytes,
        process_banner_batch,
    )
    from .resizer import (
        ALLOWED_RESIZE_MODES,
        ResizeTask,
        normalize_resize_mode,
        parse_target_dimensions,
        process_resize_batch,
    )
    from .utils import build_zip_bytes, media_type_for_filename, sanitize_stem, is_video_file
    from .converter_engine import convert_image_bytes, convert_video_bytes
except ImportError:  # pragma: no cover
    from banner_optimizer import OptimizationTask, process_optimization_batch
    from image_processor import (
        ALLOWED_PLACEMENT_MODES,
        BannerTask,
        load_image_bytes,
        process_banner_batch,
    )
    from resizer import (
        ALLOWED_RESIZE_MODES,
        ResizeTask,
        normalize_resize_mode,
        parse_target_dimensions,
        process_resize_batch,
    )
    from utils import build_zip_bytes, media_type_for_filename, sanitize_stem, is_video_file
    from converter_engine import convert_image_bytes, convert_video_bytes


app = FastAPI(title="JPG Optimiser", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_INDEX = Path(__file__).resolve().parents[1] / "frontend" / "index.html"
DIST_INDEX = Path(__file__).resolve().parents[1] / "dist" / "index.html"


def _chunked(items: list[Any], size: int) -> Iterator[list[Any]]:
    for index in range(0, len(items), size):
        yield items[index:index + size]


def _is_upload(value: Any) -> bool:
    return hasattr(value, "read") and hasattr(value, "filename")


def _collect_uploads(form: Any, keys: Iterable[str]) -> list[Any]:
    uploads: list[Any] = []
    for key in keys:
        if hasattr(form, "getlist"):
            values = form.getlist(key)
        else:
            value = form.get(key)
            values = [] if value is None else [value]
        uploads.extend([value for value in values if _is_upload(value)])
    return uploads


def _first_text(form: Any, keys: Iterable[str]) -> str | None:
    for key in keys:
        if hasattr(form, "getlist"):
            values = form.getlist(key)
            for value in values:
                if isinstance(value, str) and value.strip():
                    return value.strip()
        else:
            value = form.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _error_zip_response(
    messages: Iterable[str],
    http_status: int,
    *,
    filename: str = "jpgoptimiser_processed_errors.zip",
) -> Response:
    zip_bytes = build_zip_bytes([], messages)
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers=headers,
        status_code=http_status,
    )


def _frontend_index_path() -> Path | None:
    if DIST_INDEX.exists():
        return DIST_INDEX
    if FRONTEND_INDEX.exists():
        return FRONTEND_INDEX
    return None


def _normalize_mode(mode: str) -> str:
    return mode.strip().lower().replace("_", "-")


def _all_text(form: Any, keys: Iterable[str]) -> list[str]:
    values: list[str] = []
    for key in keys:
        if hasattr(form, "getlist"):
            values.extend(
                value.strip()
                for value in form.getlist(key)
                if isinstance(value, str) and value.strip()
            )
        else:
            value = form.get(key)
            if isinstance(value, str) and value.strip():
                values.append(value.strip())
    return values


def _download_response(
    processed_files: list[tuple[str, bytes]],
    errors: list[str],
    *,
    empty_message: str,
    zip_filename: str,
    error_filename: str,
    custom_name: str | None = None,
    append_custom_name: bool = False,
) -> Response:
    if not processed_files:
        return _error_zip_response(
            errors or [empty_message],
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            filename=error_filename,
        )

    if custom_name:
        stem = sanitize_stem(custom_name)
        if len(processed_files) == 1 and not errors:
            output_name, output_bytes = processed_files[0]
            if not append_custom_name:
                ext = Path(output_name).suffix
                output_name = f"{stem}{ext}"
            headers = {"Content-Disposition": f'attachment; filename="{output_name}"'}
            return Response(
                content=output_bytes,
                media_type=media_type_for_filename(output_name),
                headers=headers,
            )
        else:
            zip_filename = f"{stem}.zip"
    else:
        if len(processed_files) == 1 and not errors:
            output_name, output_bytes = processed_files[0]
            headers = {"Content-Disposition": f'attachment; filename="{output_name}"'}
            return Response(
                content=output_bytes,
                media_type=media_type_for_filename(output_name),
                headers=headers,
            )

    zip_bytes = build_zip_bytes(processed_files, errors or None)
    headers = {"Content-Disposition": f'attachment; filename="{zip_filename}"'}
    return Response(content=zip_bytes, media_type="application/zip", headers=headers)


@app.get("/", include_in_schema=False)
@app.get("/optimiser", include_in_schema=False)
@app.get("/optimiser/", include_in_schema=False)
async def frontend() -> Response:
    frontend_index = _frontend_index_path()
    if frontend_index is not None:
        return FileResponse(frontend_index)
    return Response(
        content="JPG Optimiser frontend not found. Open jpgoptimiser/frontend/index.html directly.",
        media_type="text/plain",
    )


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/process")
async def process(request: Request) -> Response:
    form = await request.form()
    custom_name = _first_text(form, ("custom_name", "output_name"))

    placement_mode_raw = _first_text(form, ("placement_mode", "placement"))
    if not placement_mode_raw:
        return _error_zip_response(
            ["Missing required field: placement_mode."],
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            filename="jpgoptimiser_processed_errors.zip",
        )

    placement_mode = _normalize_mode(placement_mode_raw)
    if placement_mode not in ALLOWED_PLACEMENT_MODES:
        return _error_zip_response(
            [
                "Invalid placement_mode.",
                "Expected one of: smart, top-left, top-right.",
            ],
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            filename="jpgoptimiser_processed_errors.zip",
        )

    banner_uploads = _collect_uploads(
        form,
        ("banner_images", "banners", "banner_files", "banner"),
    )
    if not banner_uploads:
        return _error_zip_response(
            ["No banner images were uploaded."],
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            filename="jpgoptimiser_processed_errors.zip",
        )

    logo_uploads = _collect_uploads(form, ("logo_image", "logo", "logo_file"))
    if not logo_uploads:
        return _error_zip_response(
            ["No logo image was uploaded."],
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            filename="jpgoptimiser_processed_errors.zip",
        )

    logo_upload = logo_uploads[0]
    logo_bytes = await logo_upload.read()
    if not logo_bytes:
        return _error_zip_response(
            ["The uploaded logo image is empty."],
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            filename="jpgoptimiser_processed_errors.zip",
        )

    try:
        logo_image, _ = load_image_bytes(logo_bytes)
    except ValueError:
        return _error_zip_response(
            ["The uploaded logo image is corrupted or unsupported."],
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            filename="jpgoptimiser_processed_errors.zip",
        )

    processed_files = []
    errors = []
    chunk_size = max(1, min(16, (os.cpu_count() or 1) * 2))

    banner_files: list[tuple[str, bytes]] = []
    for upload in banner_uploads:
        banner_bytes = await upload.read()
        source_name = upload.filename or "unknown"
        if not banner_bytes:
            errors.append(f"{source_name}: uploaded file is empty")
            continue
            
        if source_name.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(banner_bytes)) as zf:
                    for zinfo in zf.infolist():
                        if zinfo.is_dir() or zinfo.filename.startswith("__MACOSX/") or zinfo.filename.split("/")[-1].startswith("."):
                            continue
                        ext = zinfo.filename.lower().rpartition(".")[-1]
                        if ext not in {"png", "jpg", "jpeg", "webp", "bmp", "tiff", "gif", "mp4", "webm", "mov", "avi", "mkv", "m4v"}:
                            continue
                        
                        file_data = zf.read(zinfo.filename)
                        if file_data:
                            banner_files.append((os.path.basename(zinfo.filename), file_data))
            except zipfile.BadZipFile:
                errors.append(f"{source_name}: invalid zip archive")
        else:
            banner_files.append((source_name, banner_bytes))

    if not banner_files:
        return _error_zip_response(
            ["No valid banner images or videos found in the upload."] + errors,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            filename="jpgoptimiser_processed_errors.zip",
        )

    for chunk_index, upload_chunk in enumerate(_chunked(banner_files, chunk_size)):
        tasks = []
        for offset, (source_name, banner_bytes) in enumerate(upload_chunk):
            if not banner_bytes:
                continue


            tasks.append(
                BannerTask(
                    filename=source_name,
                    banner_bytes=banner_bytes,
                    logo_image=logo_image,
                    placement_mode=placement_mode,
                    custom_name=custom_name,
                )
            )

        for result in process_banner_batch(tasks):
            if result.output_name and result.output_bytes:
                processed_files.append((result.output_name, result.output_bytes))
            if result.error:
                errors.append(result.error)

    return _download_response(
        processed_files,
        errors,
        empty_message="No banners could be processed.",
        zip_filename="jpgoptimiser_processed_banners.zip",
        error_filename="jpgoptimiser_processed_errors.zip",
        custom_name=custom_name,
        append_custom_name=True,
    )


@app.post("/optimize")
async def optimize(request: Request) -> Response:
    form = await request.form()
    custom_name = _first_text(form, ("custom_name", "output_name"))

    max_size_kb_str = _first_text(form, ("max_size_kb", "target_size_kb", "max_output_bytes"))
    max_output_bytes = None
    if max_size_kb_str:
        try:
            max_output_bytes = int(float(max_size_kb_str) * 1024)
        except ValueError:
            pass

    enforce_dimensions_str = _first_text(form, ("enforce_dimensions", "enforce_banner_dimensions"))
    enforce_dimensions = True
    if enforce_dimensions_str is not None:
        enforce_dimensions = enforce_dimensions_str.lower() in ("true", "1", "yes", "on")

    banner_uploads = _collect_uploads(
        form,
        ("banner_images", "banners", "banner_files", "banner"),
    )
    if not banner_uploads:
        return _error_zip_response(
            ["No banner images were uploaded."],
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            filename="jpgoptimiser_optimized_errors.zip",
        )

    processed_files = []
    errors = []
    chunk_size = max(1, min(16, (os.cpu_count() or 1) * 2))

    for chunk_index, upload_chunk in enumerate(_chunked(banner_uploads, chunk_size)):
        tasks = []
        for offset, upload in enumerate(upload_chunk):
            banner_bytes = await upload.read()
            source_index = (chunk_index * chunk_size) + offset + 1
            source_name = upload.filename or f"banner_{source_index}"
            if not banner_bytes:
                errors.append(f"{source_name}: uploaded file is empty")
                continue

            tasks.append(
                OptimizationTask(
                    filename=source_name,
                    banner_bytes=banner_bytes,
                    max_output_bytes=max_output_bytes,
                    enforce_dimensions=enforce_dimensions,
                )
            )

        for result in process_optimization_batch(tasks):
            if result.output_name and result.output_bytes:
                processed_files.append((result.output_name, result.output_bytes))
            if result.error:
                errors.append(result.error)

    return _download_response(
        processed_files,
        errors,
        empty_message="No banners could be optimized.",
        zip_filename="jpgoptimiser_optimized_banners.zip",
        error_filename="jpgoptimiser_optimized_errors.zip",
        custom_name=custom_name,
    )


@app.post("/resize")
async def resize(request: Request) -> Response:
    form = await request.form()
    custom_name = _first_text(form, ("custom_name", "output_name"))

    mode = normalize_resize_mode(_first_text(form, ("mode", "resize_mode")))
    if mode not in ALLOWED_RESIZE_MODES:
        return _error_zip_response(
            [
                "Invalid mode.",
                "Expected one of: fit_expand, blur_expand, solid_background, dominant_color_background.",
            ],
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            filename="jpgoptimiser_resized_errors.zip",
        )

    try:
        targets = parse_target_dimensions(
            _all_text(form, ("targets", "dimensions", "target")),
            _first_text(form, ("target_width", "width")),
            _first_text(form, ("target_height", "height")),
        )
    except ValueError as exc:
        return _error_zip_response(
            [str(exc)],
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            filename="jpgoptimiser_resized_errors.zip",
        )

    try:
        blur_radius = float(_first_text(form, ("blur_radius", "blur")) or "24")
    except ValueError:
        return _error_zip_response(
            ["blur_radius must be a number."],
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            filename="jpgoptimiser_resized_errors.zip",
        )

    uploads = _collect_uploads(form, ("images", "image", "files", "creative", "creatives"))
    if not uploads:
        return _error_zip_response(
            ["No creative images were uploaded."],
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            filename="jpgoptimiser_resized_errors.zip",
        )

    background_color = _first_text(form, ("background_color", "background", "color"))
    processed_files = []
    errors = []
    chunk_size = max(1, min(16, (os.cpu_count() or 1) * 2))

    for chunk_index, upload_chunk in enumerate(_chunked(uploads, chunk_size)):
        tasks = []
        for offset, upload in enumerate(upload_chunk):
            image_bytes = await upload.read()
            source_index = (chunk_index * chunk_size) + offset + 1
            source_name = upload.filename or f"creative_{source_index}"
            if not image_bytes:
                errors.append(f"{source_name}: uploaded file is empty")
                continue

            for target in targets:
                tasks.append(
                    ResizeTask(
                        filename=source_name,
                        image_bytes=image_bytes,
                        target=target,
                        mode=mode,
                        background_color=background_color,
                        blur_radius=blur_radius,
                    )
                )

        for result in process_resize_batch(tasks):
            if result.output_name and result.output_bytes:
                processed_files.append((result.output_name, result.output_bytes))
            if result.error:
                errors.append(result.error)

    return _download_response(
        processed_files,
        errors,
        empty_message="No creatives could be adapted.",
        zip_filename="jpgoptimiser_resized_images.zip",
        error_filename="jpgoptimiser_resized_errors.zip",
        custom_name=custom_name,
    )


@app.get("/converter", include_in_schema=False)
@app.get("/converter/", include_in_schema=False)
async def converter_frontend() -> Response:
    CONVERTER_INDEX = Path(__file__).resolve().parents[1] / "frontend" / "converter.html"
    CONVERTER_DIST_INDEX = Path(__file__).resolve().parents[1] / "dist" / "converter" / "index.html"

    if CONVERTER_DIST_INDEX.exists():
        return FileResponse(CONVERTER_DIST_INDEX)
    if CONVERTER_INDEX.exists():
        return FileResponse(CONVERTER_INDEX)
    return Response(
        content="JPG Optimiser Converter frontend not found. Open jpgoptimiser/frontend/converter.html directly.",
        media_type="text/plain",
    )


@app.post("/convert")
async def convert(request: Request) -> Response:
    form = await request.form()
    custom_name = _first_text(form, ("custom_name", "output_name"))

    target_format = _first_text(form, ("target_format", "format"))
    if not target_format:
        return _error_zip_response(
            ["Missing required field: target_format."],
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            filename="jpgoptimiser_converter_errors.zip",
        )

    target_format = target_format.strip().lower()

    uploads = _collect_uploads(
        form,
        ("images", "banners", "banner_images", "files", "banner_files", "banner"),
    )
    if not uploads:
        return _error_zip_response(
            ["No files were uploaded for conversion."],
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            filename="jpgoptimiser_converter_errors.zip",
        )

    processed_files = []
    errors = []

    for upload in uploads:
        filename = upload.filename or "file"
        file_bytes = await upload.read()
        if not file_bytes:
            errors.append(f"{filename}: uploaded file is empty")
            continue

        try:
            is_video = is_video_file(filename)
            if is_video:
                if target_format not in {"mp4", "webm", "gif"}:
                    raise ValueError(f"Cannot convert video to non-video format: {target_format}")
                out_bytes, out_name = convert_video_bytes(file_bytes, filename, target_format)
            else:
                if target_format not in {"jpg", "jpeg", "png", "webp", "bmp", "tiff", "gif"}:
                    raise ValueError(f"Cannot convert image to non-image format: {target_format}")
                out_bytes, out_name = convert_image_bytes(file_bytes, filename, target_format)

            processed_files.append((out_name, out_bytes))

        except Exception as exc:
            errors.append(f"{filename}: {exc}")

    return _download_response(
        processed_files,
        errors,
        empty_message="No files could be converted.",
        zip_filename="jpgoptimiser_converted_files.zip",
        error_filename="jpgoptimiser_converter_errors.zip",
        custom_name=custom_name,
    )

