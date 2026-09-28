from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
import io
import os
import urllib.parse
import zipfile
from typing import Any, Iterable

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import json
import re

try:
    from .seo_config import (
        resolve_seo_data,
        get_blog_post,
        get_related_links,
        BLOG_ARTICLES,
    )
except ImportError:
    from seo_config import (
        resolve_seo_data,
        get_blog_post,
        get_related_links,
        BLOG_ARTICLES,
    )

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
    from .limits import (
        MAX_REQUEST_BYTES,
        MAX_TOTAL_UPLOAD_BYTES,
        MAX_SINGLE_IMAGE_BYTES,
        MAX_IMAGES_PER_REQUEST,
        MAX_IMAGE_MEGAPIXELS,
        MAX_IMAGE_DIMENSION,
        MAX_COMBINED_MEGAPIXELS,
        MAX_LOGO_BYTES,
        MAX_LOGO_MEGAPIXELS,
        MAX_RESIZE_TARGETS,
        MAX_TARGET_MEGAPIXELS,
        MAX_GENERATED_JOBS,
        MAX_RESPONSE_BYTES,
        MAX_WORKERS,
        MAX_VIDEO_FILES,
        BudgetExceededError,
        ValidationError,
        TargetUnachievableError,
        error_response,
        read_bounded_request,
        validate_image_source,
        inspect_safe_zip,
        validate_video_source,
        validate_response_size,
    )
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
    from limits import (
        MAX_REQUEST_BYTES,
        MAX_TOTAL_UPLOAD_BYTES,
        MAX_SINGLE_IMAGE_BYTES,
        MAX_IMAGES_PER_REQUEST,
        MAX_IMAGE_MEGAPIXELS,
        MAX_IMAGE_DIMENSION,
        MAX_COMBINED_MEGAPIXELS,
        MAX_LOGO_BYTES,
        MAX_LOGO_MEGAPIXELS,
        MAX_RESIZE_TARGETS,
        MAX_TARGET_MEGAPIXELS,
        MAX_GENERATED_JOBS,
        MAX_RESPONSE_BYTES,
        MAX_WORKERS,
        MAX_VIDEO_FILES,
        BudgetExceededError,
        ValidationError,
        TargetUnachievableError,
        error_response,
        read_bounded_request,
        validate_image_source,
        inspect_safe_zip,
        validate_video_source,
        validate_response_size,
    )


app = FastAPI(title="JPG Optimiser", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(BudgetExceededError)
async def budget_exceeded_handler(request: Request, exc: BudgetExceededError) -> Response:
    return error_response(exc)


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError) -> Response:
    return error_response(exc)


templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

FRONTEND_INDEX = Path(__file__).resolve().parents[1] / "frontend" / "index.html"
DIST_INDEX = Path(__file__).resolve().parents[1] / "dist" / "index.html"
FRONTEND_DIR = (Path(__file__).resolve().parents[1] / "frontend").resolve()
ALLOWED_STATIC_EXTENSIONS = {
    ".html", ".htm", ".css", ".js", ".png", ".jpg", ".jpeg",
    ".webp", ".gif", ".svg", ".ico", ".txt", ".xml", ".webmanifest"
}
FORBIDDEN_EXTENSIONS = {
    ".py", ".pyc", ".git", ".config", ".env", ".json", ".yml",
    ".yaml", ".ini", ".toml", ".sh", ".bash", ".md"
}


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
    filename: str = "globeoptimiser_processed_errors.zip",
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


async def _extract_media_items(
    uploads: list[Any],
    *,
    is_video_allowed: bool = True,
    max_count: int = MAX_IMAGES_PER_REQUEST,
    max_total_bytes: int = MAX_TOTAL_UPLOAD_BYTES,
) -> list[tuple[str, bytes]]:
    if not uploads:
        return []

    extracted: list[tuple[str, bytes]] = []
    total_upload_bytes = 0

    for upload in uploads:
        filename = upload.filename or "file"
        data = await upload.read()
        total_upload_bytes += len(data)
        if total_upload_bytes > max_total_bytes:
            raise BudgetExceededError(
                f"Total uploaded files ({total_upload_bytes / (1024 * 1024):.1f} MiB) exceed the budget limit of {max_total_bytes / (1024 * 1024):.1f} MiB.",
                code="total_upload_too_large",
            )

        if not data:
            continue

        if filename.lower().endswith(".zip"):
            zip_items = inspect_safe_zip(data, filename)
            extracted.extend(zip_items)
        else:
            extracted.append((filename, data))

    if len(extracted) > max_count:
        raise BudgetExceededError(
            f"Too many media items ({len(extracted)}). Maximum allowed per request is {max_count}.",
            code="too_many_files",
        )

    combined_pixels = 0
    video_count = 0

    for fname, item_bytes in extracted:
        is_video = is_video_file(fname)
        if is_video:
            if not is_video_allowed:
                raise ValidationError(f"Video file '{fname}' is not supported for this operation.")
            video_count += 1
            if video_count > MAX_VIDEO_FILES:
                raise BudgetExceededError(
                    f"Only {MAX_VIDEO_FILES} video clip allowed per request.",
                    code="too_many_videos",
                )
            validate_video_source(item_bytes, fname)
        else:
            w, h, _ = validate_image_source(item_bytes, fname, is_logo=False)
            combined_pixels += (w * h)
            if combined_pixels > MAX_COMBINED_MEGAPIXELS:
                raise BudgetExceededError(
                    f"Combined source images ({combined_pixels / 1_000_000:.1f} MP) exceed the {MAX_COMBINED_MEGAPIXELS / 1_000_000:.1f} MP limit.",
                    code="combined_megapixels_exceeded",
                )

    return extracted


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
        unachievable = [e for e in errors if "target_size_unachievable" in e]
        if unachievable:
            return error_response(
                unachievable[0],
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="target_size_unachievable",
            )

        budget_err = [
            e for e in errors
            if any(k in e.lower() for k in ("exceeds", "budget", "too large", "limit"))
        ]
        if budget_err:
            return error_response(
                budget_err[0],
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                code="budget_exceeded",
            )

        return error_response(
            errors[0] if errors else empty_message,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="invalid_input",
        )

    if custom_name:
        stem = sanitize_stem(custom_name)
        if len(processed_files) == 1 and not errors:
            output_name, output_bytes = processed_files[0]
            validate_response_size(output_bytes, output_name)
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
            validate_response_size(output_bytes, output_name)
            headers = {"Content-Disposition": f'attachment; filename="{output_name}"'}
            return Response(
                content=output_bytes,
                media_type=media_type_for_filename(output_name),
                headers=headers,
            )

    zip_bytes = build_zip_bytes(processed_files, errors or None)
    validate_response_size(zip_bytes, zip_filename)
    headers = {"Content-Disposition": f'attachment; filename="{zip_filename}"'}
    return Response(content=zip_bytes, media_type="application/zip", headers=headers)


@app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
@app.api_route("/optimiser", methods=["GET", "HEAD"], include_in_schema=False)
@app.api_route("/optimiser/", methods=["GET", "HEAD"], include_in_schema=False)
async def frontend_root(request: Request) -> Response:
    return await catch_all(request, "")


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.api_route("/favicon.ico", methods=["GET", "HEAD"], include_in_schema=False)
@app.api_route("/favicon.png", methods=["GET", "HEAD"], include_in_schema=False)
async def favicon() -> Response:
    for candidate in [
        FRONTEND_DIR / "images" / "favicon.png",
        FRONTEND_DIR / "favicon.png",
        Path(__file__).resolve().parents[1] / "images" / "favicon.png",
    ]:
        if candidate.exists() and candidate.is_file():
            return FileResponse(candidate, media_type="image/png")
    return Response(status_code=404)


@app.post("/process")
async def process(request: Request) -> Response:
    await read_bounded_request(request)
    form = await request.form()
    custom_name = _first_text(form, ("custom_name", "output_name"))

    placement_mode_raw = _first_text(form, ("placement_mode", "placement"))
    if not placement_mode_raw:
        raise ValidationError("Missing required field: placement_mode.")

    placement_mode = _normalize_mode(placement_mode_raw)
    if placement_mode not in ALLOWED_PLACEMENT_MODES:
        raise ValidationError(
            "Invalid placement_mode. Expected one of: smart, top-left, top-right."
        )

    banner_uploads = _collect_uploads(
        form,
        ("banner_images", "banners", "banner_files", "banner"),
    )
    if not banner_uploads:
        raise ValidationError("No banner images were uploaded.")

    logo_uploads = _collect_uploads(form, ("logo_image", "logo", "logo_file"))
    if not logo_uploads:
        raise ValidationError("No logo image was uploaded.")

    logo_upload = logo_uploads[0]
    logo_bytes = await logo_upload.read()
    if not logo_bytes:
        raise ValidationError("The uploaded logo image is empty.")

    validate_image_source(logo_bytes, logo_upload.filename or "logo", is_logo=True)

    try:
        logo_image, _ = load_image_bytes(logo_bytes)
    except ValueError:
        raise ValidationError("The uploaded logo image is corrupted or unsupported.")

    remaining_budget = max(0, MAX_TOTAL_UPLOAD_BYTES - len(logo_bytes))
    banner_items = await _extract_media_items(
        banner_uploads,
        is_video_allowed=True,
        max_count=MAX_IMAGES_PER_REQUEST,
        max_total_bytes=remaining_budget,
    )
    if not banner_items:
        raise ValidationError("No valid banner images or videos found in the upload.")

    processed_files = []
    errors = []

    tasks = [
        BannerTask(
            filename=source_name,
            banner_bytes=banner_bytes,
            logo_image=logo_image,
            placement_mode=placement_mode,
            custom_name=custom_name,
        )
        for source_name, banner_bytes in banner_items
    ]

    for result in process_banner_batch(tasks):
        if result.output_name and result.output_bytes:
            processed_files.append((result.output_name, result.output_bytes))
        if result.error:
            errors.append(result.error)

    return _download_response(
        processed_files,
        errors,
        empty_message="No banners could be processed.",
        zip_filename="globeoptimiser_processed_banners.zip",
        error_filename="globeoptimiser_processed_errors.zip",
        custom_name=custom_name,
        append_custom_name=True,
    )


@app.post("/optimize")
async def optimize(request: Request) -> Response:
    await read_bounded_request(request)
    form = await request.form()
    custom_name = _first_text(form, ("custom_name", "output_name"))

    max_size_kb_str = _first_text(form, ("max_size_kb", "target_size_kb", "max_output_bytes"))
    max_output_bytes = None
    if max_size_kb_str:
        try:
            kb_val = float(max_size_kb_str)
            if kb_val <= 0:
                raise ValidationError("Target size must be a positive number greater than 0.")
            max_output_bytes = int(kb_val * 1024)
        except ValueError:
            raise ValidationError("Target size must be a valid number.")

    enforce_dimensions_str = _first_text(form, ("enforce_dimensions", "enforce_banner_dimensions"))
    enforce_dimensions = True
    if enforce_dimensions_str is not None:
        enforce_dimensions = enforce_dimensions_str.lower() in ("true", "1", "yes", "on")

    banner_uploads = _collect_uploads(
        form,
        ("banner_images", "banners", "banner_files", "banner"),
    )
    if not banner_uploads:
        raise ValidationError("No banner images were uploaded.")

    banner_items = await _extract_media_items(
        banner_uploads,
        is_video_allowed=True,
        max_count=MAX_IMAGES_PER_REQUEST,
        max_total_bytes=MAX_TOTAL_UPLOAD_BYTES,
    )
    if not banner_items:
        raise ValidationError("No valid banner images or videos found in the upload.")

    processed_files = []
    errors = []

    tasks = [
        OptimizationTask(
            filename=source_name,
            banner_bytes=banner_bytes,
            max_output_bytes=max_output_bytes,
            enforce_dimensions=enforce_dimensions,
        )
        for source_name, banner_bytes in banner_items
    ]

    for result in process_optimization_batch(tasks):
        if result.output_name and result.output_bytes:
            processed_files.append((result.output_name, result.output_bytes))
        if result.error:
            errors.append(result.error)

    return _download_response(
        processed_files,
        errors,
        empty_message="No banners could be optimized.",
        zip_filename="globeoptimiser_optimized_banners.zip",
        error_filename="globeoptimiser_optimized_errors.zip",
        custom_name=custom_name,
    )


@app.post("/resize")
async def resize(request: Request) -> Response:
    await read_bounded_request(request)
    form = await request.form()
    custom_name = _first_text(form, ("custom_name", "output_name"))

    mode = normalize_resize_mode(_first_text(form, ("mode", "resize_mode")))
    if mode not in ALLOWED_RESIZE_MODES:
        raise ValidationError(
            "Invalid mode. Expected one of: fit_expand, blur_expand, solid_background, dominant_color_background."
        )

    try:
        targets = parse_target_dimensions(
            _all_text(form, ("targets", "dimensions", "target")),
            _first_text(form, ("target_width", "width")),
            _first_text(form, ("target_height", "height")),
        )
    except ValueError as exc:
        raise ValidationError(str(exc))

    if not targets:
        raise ValidationError("At least one resize target dimension must be specified.")

    if len(targets) > MAX_RESIZE_TARGETS:
        raise BudgetExceededError(
            f"Too many resize targets ({len(targets)}). Maximum allowed is {MAX_RESIZE_TARGETS}.",
            code="too_many_targets",
        )

    for target in targets:
        if target.width > MAX_IMAGE_DIMENSION or target.height > MAX_IMAGE_DIMENSION:
            raise ValidationError(
                f"Target dimension {target.width}x{target.height} exceeds maximum allowed dimension of {MAX_IMAGE_DIMENSION} px."
            )
        if (target.width * target.height) > MAX_TARGET_MEGAPIXELS:
            raise ValidationError(
                f"Target dimension {target.width}x{target.height} ({(target.width * target.height) / 1_000_000:.1f} MP) exceeds maximum allowed target limit of {MAX_TARGET_MEGAPIXELS / 1_000_000:.1f} MP."
            )

    try:
        blur_radius = float(_first_text(form, ("blur_radius", "blur")) or "24")
    except ValueError:
        raise ValidationError("blur_radius must be a number.")

    uploads = _collect_uploads(form, ("images", "image", "files", "creative", "creatives"))
    if not uploads:
        raise ValidationError("No creative images were uploaded.")

    items = await _extract_media_items(
        uploads,
        is_video_allowed=True,
        max_count=MAX_IMAGES_PER_REQUEST,
        max_total_bytes=MAX_TOTAL_UPLOAD_BYTES,
    )
    if not items:
        raise ValidationError("No valid creative images or videos found in the upload.")

    total_jobs = len(items) * len(targets)
    if total_jobs > MAX_GENERATED_JOBS:
        raise BudgetExceededError(
            f"Requested operation would generate {total_jobs} image jobs. Maximum allowed per request is {MAX_GENERATED_JOBS}.",
            code="too_many_jobs",
        )

    background_color = _first_text(form, ("background_color", "background", "color"))
    processed_files = []
    errors = []

    tasks = [
        ResizeTask(
            filename=source_name,
            image_bytes=image_bytes,
            target=target,
            mode=mode,
            background_color=background_color,
            blur_radius=blur_radius,
        )
        for source_name, image_bytes in items
        for target in targets
    ]

    for result in process_resize_batch(tasks):
        if result.output_name and result.output_bytes:
            processed_files.append((result.output_name, result.output_bytes))
        if result.error:
            errors.append(result.error)

    return _download_response(
        processed_files,
        errors,
        empty_message="No creatives could be adapted.",
        zip_filename="globeoptimiser_resized_images.zip",
        error_filename="globeoptimiser_resized_errors.zip",
        custom_name=custom_name,
    )


@app.get("/converter", include_in_schema=False)
@app.get("/converter/", include_in_schema=False)
async def converter_legacy_redirect() -> Response:
    return RedirectResponse(url="/convert-image", status_code=301)


def _get_static_html_body(page_name: str) -> str:
    """Extract page body html from legacy static files for migration."""
    p = Path(__file__).resolve().parents[1] / "frontend" / f"{page_name}.html"
    if p.exists():
        try:
            text = p.read_text(encoding="utf-8")
            match = re.search(r'<article[^>]*>(.*?)</article>', text, re.DOTALL)
            if match:
                body = match.group(1)
                # strip nested h1 since base/static templates render them
                body = re.sub(r'<h1[^>]*>.*?</h1>', '', body, flags=re.IGNORECASE)
                return body
        except Exception:
            pass
    return f"<p>Details and information about {page_name} on globeoptimiser.com.</p>"


@app.get("/about", include_in_schema=False)
@app.get("/about/", include_in_schema=False)
async def about_page(request: Request) -> Response:
    seo_data = resolve_seo_data("about")
    html_content = _get_static_html_body("about")
    return templates.TemplateResponse(
        request,
        "static_page.html",
        {
            "title_header": "About Us",
            "seo_data": seo_data,
            "page_name": "about",
            "html_content": html_content,
        },
    )


@app.get("/privacy", include_in_schema=False)
@app.get("/privacy/", include_in_schema=False)
async def privacy_page(request: Request) -> Response:
    seo_data = resolve_seo_data("privacy")
    html_content = _get_static_html_body("privacy")
    return templates.TemplateResponse(
        request,
        "static_page.html",
        {
            "title_header": "Privacy Policy",
            "seo_data": seo_data,
            "page_name": "privacy",
            "html_content": html_content,
        },
    )


@app.get("/terms", include_in_schema=False)
@app.get("/terms/", include_in_schema=False)
async def terms_page(request: Request) -> Response:
    seo_data = resolve_seo_data("terms")
    html_content = _get_static_html_body("terms")
    return templates.TemplateResponse(
        request,
        "static_page.html",
        {
            "title_header": "Terms of Use",
            "seo_data": seo_data,
            "page_name": "terms",
            "html_content": html_content,
        },
    )


@app.get("/contact", include_in_schema=False)
@app.get("/contact/", include_in_schema=False)
async def contact_page(request: Request) -> Response:
    seo_data = resolve_seo_data("contact")
    return templates.TemplateResponse(
        request,
        "static_page.html",
        {
            "title_header": "Contact Us",
            "subtitle": "Have questions or feedback? Drop us a line below and we'll get back to you shortly.",
            "seo_data": seo_data,
            "page_name": "contact",
        },
    )


@app.get("/robots.txt", include_in_schema=False)
async def robots_txt() -> Response:
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        "\n"
        "Sitemap: https://globeoptimiser.com/sitemap.xml\n"
    )
    return Response(content=content, media_type="text/plain")


@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml() -> Response:
    from .seo_config import get_all_paths
    domain = "https://globeoptimiser.com"
    urls = [f"{domain}/"] + [f"{domain}/{p}" for p in get_all_paths()]
    
    xml_items = []
    for url in urls:
        xml_items.append(
            f"  <url>\n"
            f"    <loc>{url}</loc>\n"
            f"    <changefreq>weekly</changefreq>\n"
            f"    <priority>0.8</priority>\n"
            f"  </url>"
        )
        
    xml_content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(xml_items) +
        '\n</urlset>'
    )
    return Response(content=xml_content, media_type="application/xml")


@app.get("/blog", include_in_schema=False)
@app.get("/blog/", include_in_schema=False)
async def blog_list(request: Request) -> Response:
    seo_data = {
        "title": "Blog — Image Optimization Insights | globeoptimiser.com",
        "meta_description": "Read expert articles on web performance, next-gen formats (WebP vs AVIF), and social image quality optimization.",
        "canonical": "/blog",
        "active_tab": "blog",
    }
    return templates.TemplateResponse(
        request,
        "blog_list.html",
        {"articles": BLOG_ARTICLES, "seo_data": seo_data},
    )


@app.get("/blog/{slug}", include_in_schema=False)
async def blog_post(request: Request, slug: str) -> Response:
    post = get_blog_post(slug)
    if not post:
        return Response(content="Article not found.", status_code=404, media_type="text/plain")
        
    post = post.copy()
    content_html = post["content"]
    paragraphs = [p.strip() for p in content_html.split("</p>") if p.strip()]
    mid = len(paragraphs) // 2
    if mid > 0:
        ad_code = (
            '\n<div class="ad-slot ad-in-content" style="margin: 28px auto;" aria-label="Advertisement">\n'
            '  <span class="ad-label">Advertisement</span>\n'
            '  <!-- /23043164651/globeoptimiser_banner4 -->\n'
            '  <div id="div-gpt-ad-1790268002577-0" style="min-width: 200px; min-height: 50px;">\n'
            '    <script>\n'
            '      googletag.cmd.push(function() { googletag.display("div-gpt-ad-1790268002577-0"); });\n'
            '    </script>\n'
            '  </div>\n'
            '</div>\n'
        )
        paragraphs.insert(mid, ad_code)
        content_parts = []
        for i, p in enumerate(paragraphs):
            if p.strip() == ad_code.strip():
                content_parts.append(p)
            else:
                content_parts.append(p + "</p>")
        post["content"] = "".join(content_parts)

    seo_data = {
        "title": f"{post['title']} | globeoptimiser.com Blog",
        "meta_description": post["summary"],
        "canonical": f"/blog/{slug}",
        "active_tab": "blog",
    }
    
    schema = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": post["title"],
        "description": post["summary"],
        "datePublished": "2026-07-10",
        "author": {
            "@type": "Organization",
            "name": "globeoptimiser.com",
        },
    }
    
    return templates.TemplateResponse(
        request,
        "blog_post.html",
        {
            "post": post,
            "seo_data": seo_data,
            "schema_json": json.dumps(schema),
        },
    )


@app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
async def catch_all(request: Request, path: str) -> Response:
    unquoted_path = urllib.parse.unquote(path)
    if (
        ".." in path
        or ".." in unquoted_path
        or "\0" in path
        or "\0" in unquoted_path
        or "\\" in path
        or "\\" in unquoted_path
    ):
        return Response(content="Page not found.", status_code=404, media_type="text/plain")

    clean_path = unquoted_path.lstrip("/")
    parts = Path(clean_path).parts
    if any(part.startswith(".") for part in parts):
        return Response(content="Page not found.", status_code=404, media_type="text/plain")

    # Safely bypass post API routes that fast-api usually resolves first
    if clean_path in {"health", "process", "optimize", "resize", "convert", "contact"}:
        return Response(status_code=404)

    if clean_path:
        try:
            candidate = (FRONTEND_DIR / clean_path).resolve()
            if candidate.is_relative_to(FRONTEND_DIR) and candidate.is_file():
                ext = candidate.suffix.lower()
                if ext in FORBIDDEN_EXTENSIONS or ext not in ALLOWED_STATIC_EXTENSIONS:
                    return Response(content="Page not found.", status_code=404, media_type="text/plain")
                return FileResponse(candidate)
        except Exception:
            return Response(content="Page not found.", status_code=404, media_type="text/plain")

    seo_data = resolve_seo_data(clean_path)
    if not seo_data:
        return Response(content="Page not found.", status_code=404, media_type="text/plain")

    # Build schema structures
    breadcrumbs = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "name": "Home",
                "item": "https://globeoptimiser.com/",
            }
        ],
    }
    if clean_path:
        breadcrumbs["itemListElement"].append(
            {
                "@type": "ListItem",
                "position": 2,
                "name": clean_path.replace("-", " ").title(),
                "item": f"https://globeoptimiser.com/{clean_path}",
            }
        )

    software_app = {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": seo_data["title"],
        "operatingSystem": "All",
        "applicationCategory": "ImageApplication",
        "offers": {
            "@type": "Offer",
            "price": "0.00",
            "priceCurrency": "USD",
        },
    }

    faq_schema = None
    if seo_data.get("faqs"):
        faq_schema = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [],
        }
        for faq in seo_data["faqs"]:
            faq_schema["mainEntity"].append(
                {
                    "@type": "Question",
                    "name": faq["q"],
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": faq["a"],
                    },
                }
            )

    schema_list = [breadcrumbs, software_app]
    if faq_schema:
        schema_list.append(faq_schema)

    related_links = get_related_links(clean_path)

    return templates.TemplateResponse(
        request,
        "tool.html",
        {
            "seo_data": seo_data,
            "related_links": related_links,
            "schema_json": json.dumps(schema_list),
        },
    )


@app.post("/contact")
async def contact_submit(request: Request) -> Response:
    try:
        body = await request.json()
        name = body.get("name")
        email = body.get("email")
        subject = body.get("subject")
        message = body.get("message")

        if not name or not email or not subject or not message:
            return Response(content="All fields are required.", status_code=400)

        print(f"Contact form submitted by {name} ({email}): Subject: {subject}\nMessage: {message}")
        return Response(content="Message sent successfully.", status_code=200)
    except Exception as e:
        print(f"Error handling contact submission: {e}")
        return Response(content="An internal error occurred.", status_code=500)


@app.post("/convert")
async def convert(request: Request) -> Response:
    await read_bounded_request(request)
    form = await request.form()
    custom_name = _first_text(form, ("custom_name", "output_name"))

    target_format = _first_text(form, ("target_format", "format"))
    if not target_format:
        raise ValidationError("Missing required field: target_format.")

    target_format = target_format.strip().lower()

    uploads = _collect_uploads(
        form,
        ("images", "banners", "banner_images", "files", "banner_files", "banner"),
    )
    if not uploads:
        raise ValidationError("No files were uploaded for conversion.")

    items = await _extract_media_items(
        uploads,
        is_video_allowed=True,
        max_count=MAX_IMAGES_PER_REQUEST,
        max_total_bytes=MAX_TOTAL_UPLOAD_BYTES,
    )
    if not items:
        raise ValidationError("No valid files found for conversion.")

    processed_files = []
    errors = []

    for filename, file_bytes in items:
        try:
            is_video = is_video_file(filename)
            if is_video:
                if target_format not in {"mp4", "webm", "gif"}:
                    raise ValidationError(f"Cannot convert video to non-video format: {target_format}")
                out_bytes, out_name = convert_video_bytes(file_bytes, filename, target_format)
            else:
                if target_format not in {"jpg", "jpeg", "png", "webp", "bmp", "tiff", "gif"}:
                    raise ValidationError(f"Cannot convert image to non-image format: {target_format}")
                out_bytes, out_name = convert_image_bytes(file_bytes, filename, target_format)

            processed_files.append((out_name, out_bytes))
        except (BudgetExceededError, ValidationError):
            raise
        except Exception as exc:
            errors.append(f"{filename}: {exc}")

    return _download_response(
        processed_files,
        errors,
        empty_message="No files could be converted.",
        zip_filename="globeoptimiser_converted_files.zip",
        error_filename="globeoptimiser_converter_errors.zip",
        custom_name=custom_name,
    )

