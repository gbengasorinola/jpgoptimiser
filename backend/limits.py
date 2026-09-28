from __future__ import annotations

from pathlib import Path
import io
import math
import os
import zipfile
from dataclasses import dataclass
from typing import Any, Iterable, Sequence
from PIL import Image
from fastapi import HTTPException, Request, Response, status
from fastapi.responses import JSONResponse


# --- Vercel Hobby Processing Budget Constants ---
MAX_REQUEST_BYTES = 3 * 1024 * 1024          # 3 MiB multipart request total
MAX_TOTAL_UPLOAD_BYTES = int(2.5 * 1024 * 1024) # 2.5 MiB total uploaded files
MAX_SINGLE_IMAGE_BYTES = 2 * 1024 * 1024     # 2 MiB individual image
MAX_IMAGES_PER_REQUEST = 3                   # At most 3 images per request
MAX_IMAGE_MEGAPIXELS = 8_000_000             # 8 Megapixels per image
MAX_IMAGE_DIMENSION = 4096                   # Max width or height: 4096 px
MAX_COMBINED_MEGAPIXELS = 12_000_000         # 12 Megapixels combined source
MAX_LOGO_BYTES = 256 * 1024                  # 256 KiB logo
MAX_LOGO_MEGAPIXELS = 2_000_000              # 2 Megapixels logo
MAX_RESIZE_TARGETS = 3                       # At most 3 resize targets
MAX_TARGET_MEGAPIXELS = 4_000_000            # 4 Megapixels per resize target
MAX_GENERATED_JOBS = 6                       # At most 6 generated image jobs
MAX_RESPONSE_BYTES = 3 * 1024 * 1024         # 3 MiB complete response (including ZIP)
MAX_WORKERS = 2                              # At most 2 parallel workers on Hobby

# ZIP Archive Limits
MAX_ZIP_ENTRIES = 3                          # At most 3 eligible images from zip
MAX_ZIP_COMPRESSED_BYTES = int(2.5 * 1024 * 1024) # 2.5 MiB compressed input
MAX_ZIP_EXPANDED_BYTES = 6 * 1024 * 1024     # 6 MiB total expanded data
MAX_ZIP_RATIO = 10.0                         # Max safe expansion ratio

# Video Hobby Policy Limits
MAX_VIDEO_FILES = 1                          # 1 clip per request
MAX_VIDEO_INPUT_BYTES = 1 * 1024 * 1024      # 1 MiB video input
MAX_VIDEO_DURATION_SEC = 3.0                 # At most 3 seconds
MAX_VIDEO_WIDTH = 640                        # 640 px
MAX_VIDEO_HEIGHT = 360                       # 360 px
MAX_VIDEO_FPS = 24                           # 24 fps
MAX_VIDEO_PIXELS = 640 * 360                 # 230,400 pixels per frame

# Compression target validation
MIN_TARGET_SIZE_KB = 5
MAX_TARGET_SIZE_KB = 2500

# Protect Pillow against decompression bombs
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_MEGAPIXELS


class BudgetExceededError(Exception):
    def __init__(self, detail: str, code: str = "request_too_large"):
        super().__init__(detail)
        self.detail = detail
        self.code = code
        self.status_code = status.HTTP_413_CONTENT_TOO_LARGE


class ValidationError(Exception):
    def __init__(self, detail: str, code: str = "invalid_input"):
        super().__init__(detail)
        self.detail = detail
        self.code = code
        self.status_code = status.HTTP_422_UNPROCESSABLE_CONTENT


class TargetUnachievableError(ValidationError):
    def __init__(self, detail: str):
        super().__init__(detail, code="target_size_unachievable")


def error_response(exc: BudgetExceededError | ValidationError | str, status_code: int = 422, code: str = "error") -> JSONResponse:
    if isinstance(exc, (BudgetExceededError, ValidationError)):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "code": exc.code},
        )
    return JSONResponse(
        status_code=status_code,
        content={"detail": str(exc), "code": code},
    )


async def read_bounded_request(request: Request, max_bytes: int = MAX_REQUEST_BYTES) -> None:
    """Validate request size before and during streaming body reading."""
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            cl = int(content_length)
            if cl > max_bytes:
                raise BudgetExceededError(
                    f"Request payload ({cl / 1024 / 1024:.1f} MiB) exceeds the Hobby budget limit of 3 MiB.",
                    code="request_too_large"
                )
        except ValueError:
            raise ValidationError("Invalid Content-Length header.")

    # Read body in chunks to prevent unbounded streaming
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > max_bytes:
            raise BudgetExceededError(
                f"Request payload exceeds the Hobby budget limit of 3 MiB.",
                code="request_too_large"
            )
    
    # Cache consumed body so Starlette's request.form() can parse it from memory
    request._body = bytes(body)


def inspect_image_metadata(image_bytes: bytes, filename: str = "image") -> tuple[int, int, str]:
    """Inspect image dimensions without fully loading pixel data into memory."""
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            w, h = img.size
            fmt = img.format or "PNG"
            return w, h, fmt
    except Exception as exc:
        raise ValidationError(f"File '{filename}' is not a valid or supported image: {exc}")


def validate_image_source(image_bytes: bytes, filename: str, is_logo: bool = False) -> tuple[int, int, str]:
    """Validate byte length, dimensions, and megapixels for an image source."""
    if not image_bytes:
        raise ValidationError(f"File '{filename}' is empty.")

    max_bytes = MAX_LOGO_BYTES if is_logo else MAX_SINGLE_IMAGE_BYTES
    max_mp = MAX_LOGO_MEGAPIXELS if is_logo else MAX_IMAGE_MEGAPIXELS
    label = "Logo image" if is_logo else f"Image '{filename}'"

    if len(image_bytes) > max_bytes:
        raise BudgetExceededError(
            f"{label} ({len(image_bytes) / 1024:.1f} KiB) exceeds maximum allowed size of {max_bytes // 1024} KiB.",
            code="file_too_large"
        )

    w, h, fmt = inspect_image_metadata(image_bytes, filename)

    if not is_logo:
        if w > MAX_IMAGE_DIMENSION or h > MAX_IMAGE_DIMENSION:
            raise ValidationError(
                f"{label} has dimensions {w}x{h}, which exceeds maximum allowed dimension of {MAX_IMAGE_DIMENSION} px."
            )

    pixels = w * h
    if pixels > max_mp:
        raise ValidationError(
            f"{label} has {pixels / 1_000_000:.1f} megapixels, which exceeds the allowed limit of {max_mp / 1_000_000:.1f} MP."
        )

    return w, h, fmt


def inspect_safe_zip(zip_bytes: bytes, filename: str) -> list[tuple[str, bytes]]:
    """Safely extract eligible images from a ZIP archive enforcing bomb and nested checks."""
    if len(zip_bytes) > MAX_ZIP_COMPRESSED_BYTES:
        raise BudgetExceededError(
            f"Uploaded ZIP '{filename}' ({len(zip_bytes) / 1024 / 1024:.1f} MiB) exceeds compressed limit of 2.5 MiB.",
            code="zip_too_large"
        )

    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except Exception as exc:
        raise ValidationError(f"ZIP archive '{filename}' is corrupted or invalid: {exc}")

    with zf:
        total_uncompressed = 0
        eligible_entries: list[zipfile.ZipInfo] = []

        for zinfo in zf.infolist():
            # Check for encryption
            if zinfo.flag_bits & 0x1:
                raise ValidationError(f"Encrypted ZIP archives are not supported: '{zinfo.filename}' is password-protected.")

            # Skip directories and mac metadata
            if zinfo.is_dir() or zinfo.filename.startswith("__MACOSX/") or os.path.basename(zinfo.filename).startswith("."):
                continue

            base_name = os.path.basename(zinfo.filename)
            ext = base_name.lower().rpartition(".")[-1]

            # Reject nested zip archives
            if ext == "zip":
                raise ValidationError(f"Nested ZIP archives are forbidden: found '{zinfo.filename}'.")

            if ext in {"png", "jpg", "jpeg", "webp", "bmp", "tiff", "gif", "mp4", "webm"}:
                eligible_entries.append(zinfo)
                total_uncompressed += zinfo.file_size

        if not eligible_entries:
            raise ValidationError(f"ZIP archive '{filename}' contains no supported image or video files.")

        if len(eligible_entries) > MAX_ZIP_ENTRIES:
            raise BudgetExceededError(
                f"ZIP archive contains {len(eligible_entries)} media files. Maximum allowed per request is {MAX_ZIP_ENTRIES}.",
                code="too_many_files"
            )

        if total_uncompressed > MAX_ZIP_EXPANDED_BYTES:
            raise BudgetExceededError(
                f"ZIP uncompressed content ({total_uncompressed / 1024 / 1024:.1f} MiB) exceeds the 6 MiB expansion limit.",
                code="zip_bomb_detected"
            )

        # Check compression ratio
        compressed_size = max(1, len(zip_bytes))
        ratio = total_uncompressed / compressed_size
        if ratio > MAX_ZIP_RATIO and total_uncompressed > 1024 * 1024:
            raise ValidationError(f"Suspicious ZIP expansion ratio ({ratio:.1f}:1) detected.")

        extracted_files: list[tuple[str, bytes]] = []
        for zinfo in eligible_entries:
            data = zf.read(zinfo.filename)
            if len(data) > MAX_SINGLE_IMAGE_BYTES:
                raise BudgetExceededError(
                    f"Extracted file '{zinfo.filename}' ({len(data) / 1024 / 1024:.1f} MiB) exceeds individual limit of 2 MiB.",
                    code="file_too_large"
                )
            extracted_files.append((os.path.basename(zinfo.filename), data))

        return extracted_files


def validate_video_source(video_bytes: bytes, filename: str) -> None:
    """Validate video clip strictly against Vercel Hobby limits."""
    if len(video_bytes) > MAX_VIDEO_INPUT_BYTES:
        raise BudgetExceededError(
            f"Video '{filename}' ({len(video_bytes) / 1024 / 1024:.1f} MiB) exceeds the Hobby limit of 1 MiB.",
            code="video_too_large"
        )

    import tempfile
    ext = Path(filename).suffix.lower() if filename else ".mp4"
    temp_path = None
    clip = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
            f.write(video_bytes)
            temp_path = f.name

        try:
            from moviepy import VideoFileClip
        except ImportError:
            from moviepy.editor import VideoFileClip

        clip = VideoFileClip(temp_path)
        
        duration = clip.duration or 0.0
        if duration > MAX_VIDEO_DURATION_SEC:
            raise ValidationError(
                f"Video duration ({duration:.1f}s) exceeds the maximum allowed Hobby limit of {int(MAX_VIDEO_DURATION_SEC)} seconds."
            )

        w, h = clip.w, clip.h
        if w > MAX_VIDEO_WIDTH or h > MAX_VIDEO_HEIGHT:
            if (w * h) > MAX_VIDEO_PIXELS:
                raise ValidationError(
                    f"Video dimensions ({w}x{h}) exceed maximum allowed 640x360 resolution for Hobby processing."
                )

        fps = clip.fps or 24
        if fps > MAX_VIDEO_FPS + 1:  # Allow standard slight deviations
            raise ValidationError(
                f"Video frame rate ({fps:.1f} fps) exceeds the maximum allowed 24 fps limit on Hobby."
            )

    except (BudgetExceededError, ValidationError):
        raise
    except Exception as exc:
        raise ValidationError(f"Could not read video metadata for '{filename}': {exc}")
    finally:
        if clip:
            try:
                clip.close()
            except Exception:
                pass
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception:
                pass


def validate_response_size(response_bytes: bytes, filename: str = "output") -> None:
    """Ensure response payload does not exceed 3 MiB budget."""
    if len(response_bytes) > MAX_RESPONSE_BYTES:
        raise BudgetExceededError(
            f"Generated output ({len(response_bytes) / 1024 / 1024:.2f} MiB) exceeds maximum response budget of 3 MiB.",
            code="response_too_large"
        )
