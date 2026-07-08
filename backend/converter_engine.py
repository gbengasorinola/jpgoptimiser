from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path
from PIL import Image

try:
    from .utils import extension_for_format, normalize_format, sanitize_stem
except ImportError:
    from utils import extension_for_format, normalize_format, sanitize_stem


def convert_image_bytes(
    image_bytes: bytes,
    filename: str,
    target_format: str,
) -> tuple[bytes, str]:
    """Convert image bytes to a target format (JPEG, PNG, WEBP, BMP, TIFF, GIF) using Pillow."""
    
    fmt = normalize_format(target_format)
    ext = extension_for_format(fmt)
    
    # Load image from bytes
    image = Image.open(io.BytesIO(image_bytes))
    
    # Handle alpha channel issues for JPEG
    if fmt == "JPEG":
        if image.mode in {"RGBA", "LA", "P"}:
            # Create white background canvas to place transparent image on
            bg = Image.new("RGB", image.size, (255, 255, 255))
            if image.mode == "P":
                image = image.convert("RGBA")
            bg.paste(image, mask=image.split()[3] if len(image.split()) == 4 else None)
            image = bg
        else:
            image = image.convert("RGB")
            
    # Serialize image to target format
    output = io.BytesIO()
    save_kwargs = {}
    if fmt == "JPEG":
        save_kwargs["quality"] = 95
        save_kwargs["optimize"] = True
    elif fmt == "PNG":
        save_kwargs["optimize"] = True
        
    image.save(output, format=fmt, **save_kwargs)
    
    source_stem = sanitize_stem(filename)
    output_name = f"{source_stem}_converted.{ext}"
    
    return output.getvalue(), output_name


def convert_video_bytes(
    video_bytes: bytes,
    filename: str,
    target_format: str,
) -> tuple[bytes, str]:
    """Convert video bytes to a target format (MP4, WEBM, GIF) using MoviePy."""
    try:
        from moviepy import VideoFileClip
    except ImportError:  # pragma: no cover - MoviePy 1.x compatibility
        from moviepy.editor import VideoFileClip
    
    fmt = target_format.strip().lower()
    if fmt not in {"mp4", "webm", "gif"}:
        raise ValueError(f"Unsupported target video format: {fmt}")
        
    source_stem = sanitize_stem(filename)
    source_ext = Path(filename).suffix.lower() if filename else ".mp4"
    output_name = f"{source_stem}_converted.{fmt}"
    
    temp_in_path = None
    temp_out_path = None
    clip = None
    
    try:
        # Save input bytes to temporary file
        with tempfile.NamedTemporaryFile(suffix=source_ext, delete=False) as temp_in:
            temp_in.write(video_bytes)
            temp_in_path = temp_in.name
            
        clip = VideoFileClip(temp_in_path)
        
        # Save converted clip to temporary file
        with tempfile.NamedTemporaryFile(suffix=f".{fmt}", delete=False) as temp_out:
            temp_out_path = temp_out.name
            
        # Codecs selection
        if fmt == "gif":
            # For conversion from video to GIF, choose a moderate fps to save bandwidth
            clip.write_gif(
                temp_out_path,
                fps=min(12, clip.fps or 10),
                logger=None,
            )
        elif fmt == "webm":
            clip.write_videofile(
                temp_out_path,
                codec="libvpx",
                audio_codec="libvorbis" if clip.audio is not None else None,
                logger=None,
            )
        else: # mp4
            clip.write_videofile(
                temp_out_path,
                codec="libx264",
                audio_codec="aac" if clip.audio is not None else None,
                logger=None,
            )
            
        with open(temp_out_path, "rb") as f:
            output_bytes = f.read()
            
        return output_bytes, output_name
        
    finally:
        # Clean up moviepy clip
        if clip:
            try:
                clip.close()
            except Exception:
                pass
        # Clean up temp files
        for path in (temp_in_path, temp_out_path):
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except Exception:
                    pass
