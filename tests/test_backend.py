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
