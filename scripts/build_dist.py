from __future__ import annotations

from pathlib import Path
import shutil


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_INDEX = PROJECT_ROOT / "frontend" / "index.html"
SOURCE_CONVERTER = PROJECT_ROOT / "frontend" / "converter.html"
SOURCE_ABOUT = PROJECT_ROOT / "frontend" / "about.html"
SOURCE_PRIVACY = PROJECT_ROOT / "frontend" / "privacy.html"
SOURCE_TERMS = PROJECT_ROOT / "frontend" / "terms.html"
SOURCE_CONTACT = PROJECT_ROOT / "frontend" / "contact.html"
SOURCE_COMPRESS_VIDEO = PROJECT_ROOT / "frontend" / "compress-video.html"
SOURCE_RESIZE_VIDEO = PROJECT_ROOT / "frontend" / "resize-video.html"
SOURCE_CONVERT_VIDEO = PROJECT_ROOT / "frontend" / "convert-video.html"
SOURCE_WATERMARK_VIDEO = PROJECT_ROOT / "frontend" / "watermark-video.html"

DIST_DIR = PROJECT_ROOT / "dist"
DIST_INDEX = DIST_DIR / "index.html"
OPTIMISER_DIR = DIST_DIR / "optimiser"
OPTIMISER_INDEX = OPTIMISER_DIR / "index.html"
CONVERTER_DIR = DIST_DIR / "converter"
CONVERTER_INDEX = CONVERTER_DIR / "index.html"
ABOUT_DIR = DIST_DIR / "about"
ABOUT_INDEX = ABOUT_DIR / "index.html"
PRIVACY_DIR = DIST_DIR / "privacy"
PRIVACY_INDEX = PRIVACY_DIR / "index.html"
TERMS_DIR = DIST_DIR / "terms"
TERMS_INDEX = TERMS_DIR / "index.html"
CONTACT_DIR = DIST_DIR / "contact"
CONTACT_INDEX = CONTACT_DIR / "index.html"

COMPRESS_VIDEO_DIR = DIST_DIR / "compress-video"
COMPRESS_VIDEO_INDEX = COMPRESS_VIDEO_DIR / "index.html"
RESIZE_VIDEO_DIR = DIST_DIR / "resize-video"
RESIZE_VIDEO_INDEX = RESIZE_VIDEO_DIR / "index.html"
CONVERT_VIDEO_DIR = DIST_DIR / "convert-video"
CONVERT_VIDEO_INDEX = CONVERT_VIDEO_DIR / "index.html"
WATERMARK_VIDEO_DIR = DIST_DIR / "watermark-video"
WATERMARK_VIDEO_INDEX = WATERMARK_VIDEO_DIR / "index.html"


def main() -> None:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    OPTIMISER_DIR.mkdir(parents=True, exist_ok=True)
    CONVERTER_DIR.mkdir(parents=True, exist_ok=True)
    ABOUT_DIR.mkdir(parents=True, exist_ok=True)
    PRIVACY_DIR.mkdir(parents=True, exist_ok=True)
    TERMS_DIR.mkdir(parents=True, exist_ok=True)
    CONTACT_DIR.mkdir(parents=True, exist_ok=True)
    COMPRESS_VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    RESIZE_VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    CONVERT_VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    WATERMARK_VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    
    shutil.copy2(SOURCE_INDEX, DIST_INDEX)
    shutil.copy2(SOURCE_INDEX, OPTIMISER_INDEX)
    shutil.copy2(SOURCE_CONVERTER, CONVERTER_INDEX)
    shutil.copy2(SOURCE_ABOUT, ABOUT_INDEX)
    shutil.copy2(SOURCE_PRIVACY, PRIVACY_INDEX)
    shutil.copy2(SOURCE_TERMS, TERMS_INDEX)
    shutil.copy2(SOURCE_CONTACT, CONTACT_INDEX)
    
    if SOURCE_COMPRESS_VIDEO.exists():
        shutil.copy2(SOURCE_COMPRESS_VIDEO, COMPRESS_VIDEO_INDEX)
    if SOURCE_RESIZE_VIDEO.exists():
        shutil.copy2(SOURCE_RESIZE_VIDEO, RESIZE_VIDEO_INDEX)
    if SOURCE_CONVERT_VIDEO.exists():
        shutil.copy2(SOURCE_CONVERT_VIDEO, CONVERT_VIDEO_INDEX)
    if SOURCE_WATERMARK_VIDEO.exists():
        shutil.copy2(SOURCE_WATERMARK_VIDEO, WATERMARK_VIDEO_INDEX)

    # Copy images & favicon
    source_images = PROJECT_ROOT / "frontend" / "images"
    if not source_images.exists():
        source_images = PROJECT_ROOT / "images"
    dist_images = DIST_DIR / "images"
    dist_images.mkdir(parents=True, exist_ok=True)
    for img_file in source_images.glob("*"):
        if img_file.is_file():
            shutil.copy2(img_file, dist_images / img_file.name)
    fav = source_images / "favicon.png"
    if fav.exists():
        shutil.copy2(fav, DIST_DIR / "favicon.png")
        shutil.copy2(fav, DIST_DIR / "favicon.ico")

    print(f"Built {DIST_INDEX}")
    print(f"Built {OPTIMISER_INDEX}")
    print(f"Built {CONVERTER_INDEX}")
    print(f"Built {ABOUT_INDEX}")
    print(f"Built {PRIVACY_INDEX}")
    print(f"Built {TERMS_INDEX}")
    print(f"Built {CONTACT_INDEX}")
    print(f"Built {COMPRESS_VIDEO_INDEX}")
    print(f"Built {RESIZE_VIDEO_INDEX}")
    print(f"Built {CONVERT_VIDEO_INDEX}")
    print(f"Built {WATERMARK_VIDEO_INDEX}")
    print(f"Copied images and favicon to {dist_images}")


if __name__ == "__main__":
    main()
