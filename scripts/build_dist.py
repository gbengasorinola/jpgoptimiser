from __future__ import annotations

from pathlib import Path
import shutil


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_INDEX = PROJECT_ROOT / "frontend" / "index.html"
SOURCE_CONVERTER = PROJECT_ROOT / "frontend" / "converter.html"
SOURCE_ABOUT = PROJECT_ROOT / "frontend" / "about.html"
SOURCE_PRIVACY = PROJECT_ROOT / "frontend" / "privacy.html"
SOURCE_TERMS = PROJECT_ROOT / "frontend" / "terms.html"

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


def main() -> None:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    OPTIMISER_DIR.mkdir(parents=True, exist_ok=True)
    CONVERTER_DIR.mkdir(parents=True, exist_ok=True)
    ABOUT_DIR.mkdir(parents=True, exist_ok=True)
    PRIVACY_DIR.mkdir(parents=True, exist_ok=True)
    TERMS_DIR.mkdir(parents=True, exist_ok=True)
    
    shutil.copy2(SOURCE_INDEX, DIST_INDEX)
    shutil.copy2(SOURCE_INDEX, OPTIMISER_INDEX)
    shutil.copy2(SOURCE_CONVERTER, CONVERTER_INDEX)
    shutil.copy2(SOURCE_ABOUT, ABOUT_INDEX)
    shutil.copy2(SOURCE_PRIVACY, PRIVACY_INDEX)
    shutil.copy2(SOURCE_TERMS, TERMS_INDEX)
    
    print(f"Built {DIST_INDEX}")
    print(f"Built {OPTIMISER_INDEX}")
    print(f"Built {CONVERTER_INDEX}")
    print(f"Built {ABOUT_INDEX}")
    print(f"Built {PRIVACY_INDEX}")
    print(f"Built {TERMS_INDEX}")


if __name__ == "__main__":
    main()
