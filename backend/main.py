from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
import io
import os
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

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

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
async def frontend_root(request: Request) -> Response:
    return await catch_all(request, "")


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
    return f"<p>Details and information about {page_name} on jpgoptimiser.com.</p>"


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
        "Sitemap: https://jpgoptimiser.com/sitemap.xml\n"
    )
    return Response(content=content, media_type="text/plain")


@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml() -> Response:
    from .seo_config import get_all_paths
    domain = "https://jpgoptimiser.com"
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
        "title": "Blog — Image Optimization Insights | jpgoptimiser.com",
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
            '  <div class="ad-placeholder">In-Article Responsive Ad (728x90 / 300x250)</div>\n'
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
        "title": f"{post['title']} | jpgoptimiser.com Blog",
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
            "name": "jpgoptimiser.com",
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


@app.get("/{path:path}", include_in_schema=False)
async def catch_all(request: Request, path: str) -> Response:
    # Safely bypass post API routes that fast-api usually resolves first
    if path in {"health", "process", "optimize", "resize", "convert", "contact"}:
        return Response(status_code=404)
        
    seo_data = resolve_seo_data(path)
    if not seo_data:
        # Check if file exists in frontend as static asset
        frontend_file = Path(__file__).resolve().parents[1] / "frontend" / path
        if frontend_file.exists() and frontend_file.is_file():
            return FileResponse(frontend_file)
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
                "item": "https://jpgoptimiser.com/",
            }
        ],
    }
    if path:
        breadcrumbs["itemListElement"].append(
            {
                "@type": "ListItem",
                "position": 2,
                "name": path.replace("-", " ").title(),
                "item": f"https://jpgoptimiser.com/{path}",
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

    related_links = get_related_links(path)

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

