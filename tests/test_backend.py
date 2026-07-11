from __future__ import annotations

import io
import zipfile

from fastapi.testclient import TestClient
from PIL import Image

from backend.main import app


client = TestClient(app)


def image_bytes(
    size: tuple[int, int] = (300, 250),
    color: tuple[int, int, int, int] = (40, 120, 210, 255),
    image_format: str = "PNG",
) -> bytes:
    image = Image.new("RGBA", size, color)
    buffer = io.BytesIO()
    image.save(buffer, format=image_format)
    return buffer.getvalue()


def zip_names(payload: bytes) -> set[str]:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        return set(archive.namelist())


def test_healthcheck() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_optimize_requires_upload() -> None:
    response = client.post("/optimize", data={"max_size_kb": "150"})

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/zip"
    assert "errors.txt" in zip_names(response.content)


def test_resize_image_happy_path() -> None:
    response = client.post(
        "/resize",
        data={
            "target_width": "320",
            "target_height": "100",
            "mode": "solid_background",
            "background_color": "#ffffff",
        },
        files={
            "images": (
                "creative.png",
                image_bytes((300, 250)),
                "image/png",
            )
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert 'filename="creative_320x100_solid_background.png"' in response.headers["content-disposition"]


def test_convert_image_happy_path() -> None:
    response = client.post(
        "/convert",
        data={"target_format": "jpg"},
        files={
            "images": (
                "creative.png",
                image_bytes((64, 64)),
                "image/png",
            )
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert 'filename="creative_converted.jpg"' in response.headers["content-disposition"]


def test_optimize_reduces_image_size() -> None:
    response = client.post(
        "/optimize",
        data={"max_size_kb": "40"},
        files={
            "banners": (
                "creative.png",
                image_bytes((1200, 900), image_format="PNG"),
                "image/png",
            )
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert 'filename="creative_optimized.png"' in response.headers["content-disposition"]


def test_optimize_falls_back_when_target_is_too_small() -> None:
    response = client.post(
        "/optimize",
        data={"max_size_kb": "1"},
        files={
            "banners": (
                "creative.png",
                image_bytes((64, 64), image_format="PNG"),
                "image/png",
            )
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert 'filename="creative_optimized.png"' in response.headers["content-disposition"]


def test_contact_get() -> None:
    response = client.get("/contact")
    assert response.status_code == 200


def test_contact_post_success() -> None:
    payload = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "subject": "Inquiry",
        "message": "Hello, this is a test message."
    }
    response = client.post("/contact", json=payload)
    assert response.status_code == 200
    assert response.text == "Message sent successfully."


def test_contact_post_validation_error() -> None:
    payload = {
        "name": "",
        "email": "jane@example.com",
        "subject": "Inquiry",
        "message": "Hello, this is a test message."
    }
    response = client.post("/contact", json=payload)
    assert response.status_code == 400


def test_robots_txt() -> None:
    response = client.get("/robots.txt")
    assert response.status_code == 200
    assert "Sitemap:" in response.text
    assert "Allow: /" in response.text


def test_sitemap_xml() -> None:
    response = client.get("/sitemap.xml")
    assert response.status_code == 200
    assert "application/xml" in response.headers["content-type"]
    assert "<urlset" in response.text
    assert "https://jpgoptimiser.com/jpg-to-png" in response.text


def test_blog_list_page() -> None:
    response = client.get("/blog")
    assert response.status_code == 200
    assert "Knowledge Base" in response.text
    assert "jpg-vs-png" in response.text


def test_blog_post_page() -> None:
    response = client.get("/blog/jpg-vs-png")
    assert response.status_code == 200
    assert "JPG vs PNG" in response.text
    assert "Joint Photographic" in response.text


def test_static_page_scraped() -> None:
    response = client.get("/about")
    assert response.status_code == 200
    assert "About Us" in response.text
    assert "Our Core Technology" in response.text or "Welcome to" in response.text


def test_dynamic_seo_compress_kb() -> None:
    response = client.get("/compress-image-to-100kb")
    assert response.status_code == 200
    assert "Compress Image to 100KB" in response.text
    assert "targetSizeSlider" in response.text


def test_dynamic_seo_resize_px() -> None:
    response = client.get("/resize-image-to-1080x1080")
    assert response.status_code == 200
    assert "Resize Image to 1080x1080 Pixels" in response.text
    assert "resizeWidthInput" in response.text


def test_dynamic_seo_convert_formats() -> None:
    response = client.get("/heic-to-jpg")
    assert response.status_code == 200
    assert "Convert HEIC to JPG" in response.text
    assert "convertTargetFormatSelect" in response.text


def test_video_pages_routing() -> None:
    for tool_path in ["/resize-video", "/compress-video", "/convert-video", "/watermark-video"]:
        response = client.get(tool_path)
        assert response.status_code == 200
        assert "video" in response.text.lower()


def test_video_blog_articles() -> None:
    for post_slug in ["mp4-vs-webm", "compress-video-for-web", "how-to-watermark-videos"]:
        response = client.get(f"/blog/{post_slug}")
        assert response.status_code == 200
        assert "video" in response.text.lower()

