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
    mode = "RGB" if image_format.upper() in ("JPG", "JPEG") else "RGBA"
    image = Image.new(mode, size, color[:3] if mode == "RGB" else color)
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
    assert response.headers["content-type"] == "application/json"
    assert response.json()["code"] == "invalid_input"


def test_process_watermark_happy_path() -> None:
    response = client.post(
        "/process",
        data={"placement_mode": "smart"},
        files={
            "banners": ("banner.png", image_bytes((300, 250)), "image/png"),
            "logo": ("logo.png", image_bytes((50, 50)), "image/png"),
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert 'filename="banner_processed.png"' in response.headers["content-disposition"]



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


def test_optimize_impossible_target_returns_422() -> None:
    import os
    noise_data = os.urandom(200 * 200 * 3)
    img = Image.frombytes("RGB", (200, 200), noise_data)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    noisy_jpeg = buf.getvalue()

    response = client.post(
        "/optimize",
        data={"max_size_kb": "1"},
        files={"banners": ("noisy.jpg", noisy_jpeg, "image/jpeg")},
    )
    assert response.status_code == 422
    assert response.headers["content-type"] == "application/json"
    assert response.json()["code"] == "target_size_unachievable"


def test_optimize_achievable_target_under_limit() -> None:
    img = Image.new("RGB", (400, 400), (80, 140, 220))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    raw_bytes = buf.getvalue()

    response = client.post(
        "/optimize",
        data={"max_size_kb": "25"},
        files={"banners": ("plain.jpg", raw_bytes, "image/jpeg")},
    )
    assert response.status_code == 200
    assert len(response.content) <= 25 * 1024


def test_optimize_alpha_png_under_limit() -> None:
    img = Image.new("RGBA", (200, 200), (50, 100, 150, 180))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw_png = buf.getvalue()

    response = client.post(
        "/optimize",
        data={"max_size_kb": "20"},
        files={"banners": ("alpha.png", raw_png, "image/png")},
    )
    assert response.status_code == 200
    assert len(response.content) <= 20 * 1024


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
    assert "https://globeoptimiser.com/jpg-to-png" in response.text


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


def test_batch_zip_downloads() -> None:
    # Test batch conversion zip
    response = client.post(
        "/convert",
        data={"target_format": "png"},
        files=[
            ("images", ("img1.jpg", image_bytes((64, 64), image_format="JPEG"), "image/jpeg")),
            ("images", ("img2.jpg", image_bytes((64, 64), image_format="JPEG"), "image/jpeg")),
        ],
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert 'filename="globeoptimiser_converted_files.zip"' in response.headers["content-disposition"]
    filenames = zip_names(response.content)
    assert "img1_converted.png" in filenames
    assert "img2_converted.png" in filenames

    # Test batch resizing zip
    response = client.post(
        "/resize",
        data={"target_width": "100", "target_height": "100", "mode": "solid_background"},
        files=[
            ("images", ("a.png", image_bytes((200, 200)), "image/png")),
            ("images", ("b.png", image_bytes((200, 200)), "image/png")),
        ],
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert 'filename="globeoptimiser_resized_images.zip"' in response.headers["content-disposition"]


def test_video_conversion_and_resizing() -> None:
    import tempfile
    from moviepy import ColorClip
    from backend.converter_engine import convert_video_bytes
    from backend.resizer import process_single_video_resize, ResizeTask, ResizeTarget

    clip = ColorClip(size=(64, 64), color=(200, 50, 50), duration=0.5)
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        clip.write_videofile(f.name, fps=10, codec="libx264", logger=None)
        f.seek(0)
        video_bytes = open(f.name, "rb").read()

    # Verify video conversion
    out_bytes, out_name = convert_video_bytes(video_bytes, "sample.mp4", "webm")
    assert out_name == "sample_converted.webm"
    assert len(out_bytes) > 0

    # Verify video resizing
    task = ResizeTask(
        filename="sample.mp4",
        image_bytes=video_bytes,
        target=ResizeTarget(120, 120),
        mode="solid_background",
        background_color="#ffffff",
    )
    res = process_single_video_resize(task)
    assert res.error is None
    assert res.output_name == "sample_120x120_solid_background.mp4"
    assert len(res.output_bytes or b"") > 0


def test_file_disclosure_traversal_blocked() -> None:
    traversal_paths = [
        "/%2e%2e/backend/main.py",
        "/..%2fbackend/main.py",
        "/../backend/main.py",
        "/%2e%2e/.git/config",
        "/..%2f.git/config",
        "/.git/config",
        "/.htaccess",
        "/backend/main.py",
    ]
    for path in traversal_paths:
        resp = client.get(path)
        assert resp.status_code == 404, f"Path {path} returned {resp.status_code}, expected 404"
        assert "def " not in resp.text
        assert "[core]" not in resp.text


def test_public_static_asset_served() -> None:
    resp = client.get("/about.html")
    assert resp.status_code == 200


def test_branding_assets_and_favicons() -> None:
    for path in [
        "/favicon.ico",
        "/favicon.png",
        "/images/favicon.png",
        "/images/wordmark-ii.png",
        "/images/icon.png",
    ]:
        resp_get = client.get(path)
        assert resp_get.status_code == 200, f"GET {path} failed"
        assert resp_get.headers["content-type"] == "image/png"
        assert len(resp_get.content) > 0

        resp_head = client.head(path)
        assert resp_head.status_code == 200, f"HEAD {path} failed"

    root_resp = client.get("/")
    assert root_resp.status_code == 200
    assert "/images/favicon.png" in root_resp.text
    assert "/images/wordmark-ii.png" in root_resp.text
    assert "/images/icon.png" in root_resp.text


def test_request_body_exceeds_budget_returns_413() -> None:
    oversized_data = b"0" * (4 * 1024 * 1024)
    response = client.post(
        "/optimize",
        data={"max_size_kb": "50"},
        files={"banners": ("large.png", oversized_data, "image/png")},
    )
    assert response.status_code == 413
    assert response.json()["code"] in ("request_too_large", "file_too_large")


def test_too_many_images_returns_413() -> None:
    files = [
        ("banners", (f"img_{i}.png", image_bytes((100, 100)), "image/png"))
        for i in range(4)
    ]
    response = client.post("/optimize", data={"max_size_kb": "50"}, files=files)
    assert response.status_code == 413
    assert response.json()["code"] == "too_many_files"


def test_nested_zip_rejected() -> None:
    inner_buf = io.BytesIO()
    with zipfile.ZipFile(inner_buf, "w") as inner_zf:
        inner_zf.writestr("inner.png", image_bytes((50, 50)))

    outer_buf = io.BytesIO()
    with zipfile.ZipFile(outer_buf, "w") as outer_zf:
        outer_zf.writestr("nested.zip", inner_buf.getvalue())

    response = client.post(
        "/optimize",
        data={"max_size_kb": "50"},
        files={"banners": ("archive.zip", outer_buf.getvalue(), "application/zip")},
    )
    assert response.status_code == 422
    assert "Nested ZIP archives are forbidden" in response.json()["detail"]


def test_zip_bomb_expansion_rejected() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("huge1.png", b"0" * (4 * 1024 * 1024))
        zf.writestr("huge2.png", b"0" * (4 * 1024 * 1024))

    response = client.post(
        "/optimize",
        data={"max_size_kb": "50"},
        files={"banners": ("bomb.zip", buf.getvalue(), "application/zip")},
    )
    assert response.status_code in (413, 422)


def test_video_oversized_returns_413() -> None:
    fake_video = b"\x00" * int(1.5 * 1024 * 1024)
    response = client.post(
        "/convert",
        data={"target_format": "webm"},
        files={"images": ("sample.mp4", fake_video, "video/mp4")},
    )
    assert response.status_code == 413
    assert response.json()["code"] in ("video_too_large", "total_upload_too_large")


def test_response_budget_exceeded_returns_413(monkeypatch) -> None:
    from backend.resizer import ResizeResult
    def fake_resize_batch(tasks):
        return [ResizeResult(source_name="test.png", output_name="huge.png", output_bytes=b"X" * (4 * 1024 * 1024))]

    monkeypatch.setattr("backend.main.process_resize_batch", fake_resize_batch)
    response = client.post(
        "/resize",
        data={"target_width": "100", "target_height": "100", "mode": "fit_expand"},
        files={"images": ("test.png", image_bytes((50, 50)), "image/png")},
    )
    assert response.status_code == 413
    assert response.json()["code"] == "response_too_large"



