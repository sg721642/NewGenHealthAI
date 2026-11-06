"""
NewGenHealthAI — tools/image_preprocess.py
Image preprocessing and secure upload validation.
Protects against decompression bombs, unbounded uploads, malformed formats,
and strips EXIF / privacy metadata.
"""

import io
from typing import Optional, Set
from fastapi import UploadFile
from PIL import Image, ImageOps, ImageFile

from app.core.config import (
    ALLOWED_IMAGE_FORMATS,
    ALLOWED_IMAGE_MIMES,
    MAX_IMAGE_DIMENSION,
    MAX_IMAGE_PIXELS,
    MAX_IMAGE_UPLOAD_BYTES,
)
from app.core.logging_config import logger

# Prevent Pillow from loading truncated images without failing
ImageFile.LOAD_TRUNCATED_IMAGES = False
# Set global Pillow decompression bomb limit
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


class ImageValidationError(Exception):
    """Raised when an uploaded image fails security, format, or size validation."""

    def __init__(self, message: str, status_code: int = 400, status: str = "invalid_image"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.status = status


def _validate_image_signature(header: bytes) -> str:
    """
    Validate trusted file header magic bytes.
    Accepts only JPEG, PNG, and WebP signatures.
    """
    if len(header) < 12:
        raise ImageValidationError("File is too small to be a valid image.", status_code=400)
    if header.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "WEBP"
    raise ImageValidationError(
        "Unsupported or malformed image format. Only JPEG, PNG, and WebP are accepted.",
        status_code=400,
    )


async def validate_and_read_image_upload(
    file: UploadFile,
    max_bytes: int = MAX_IMAGE_UPLOAD_BYTES,
) -> bytes:
    """
    Read uploaded file in bounded chunks (64KB).
    Rejects empty files and files exceeding max_bytes before decoding into memory.
    """
    if not file:
        raise ImageValidationError("No file uploaded.", status_code=400)

    CHUNK_SIZE = 64 * 1024  # 64 KB chunks
    total_bytes = 0
    buffer = bytearray()

    try:
        while True:
            chunk = await file.read(CHUNK_SIZE)
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > max_bytes:
                logger.warning(
                    "Image upload exceeded max limit (%d > %d bytes)",
                    total_bytes, max_bytes
                )
                raise ImageValidationError(
                    f"Uploaded image exceeds maximum permitted size of {max_bytes // (1024 * 1024)}MB.",
                    status_code=413,
                )
            buffer.extend(chunk)
    finally:
        await file.close()

    if total_bytes == 0:
        raise ImageValidationError("Empty file provided.", status_code=400)

    # Verify header magic bytes
    _validate_image_signature(bytes(buffer[:16]))

    return bytes(buffer)


def safe_decode_and_sanitize_image(
    image_bytes: bytes,
    max_pixels: int = MAX_IMAGE_PIXELS,
    max_dimension: int = MAX_IMAGE_DIMENSION,
) -> Image.Image:
    """
    Safely decode image bytes, verify structure and dimensions, normalize EXIF orientation,
    and strip all EXIF/privacy metadata by re-rasterizing into a clean RGB image.
    """
    _validate_image_signature(image_bytes[:16])

    # Configure Pillow pixel ceiling for decompression bomb protection
    Image.MAX_IMAGE_PIXELS = max_pixels

    try:
        raw_img = Image.open(io.BytesIO(image_bytes))
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as e:
        logger.warning("Decompression bomb detected in uploaded image")
        raise ImageValidationError(
            "Image dimensions exceed maximum permitted resolution (decompression bomb protection).",
            status_code=400,
        ) from e
    except Exception as e:
        logger.warning("Image decoding failed: %s", type(e).__name__)
        raise ImageValidationError(
            "The uploaded file could not be decoded as a valid image.",
            status_code=400,
        ) from e

    # Verify format
    if raw_img.format not in ALLOWED_IMAGE_FORMATS:
        fmt = raw_img.format
        raw_img.close()
        raise ImageValidationError(
            f"Image format '{fmt}' is not supported. Only JPEG, PNG, and WebP are allowed.",
            status_code=400,
        )

    # Check dimensions
    width, height = raw_img.size
    if width <= 0 or height <= 0:
        raw_img.close()
        raise ImageValidationError("Invalid image dimensions.", status_code=400)
    if width > max_dimension or height > max_dimension:
        raw_img.close()
        raise ImageValidationError(
            f"Image dimension ({width}x{height}) exceeds maximum permitted limit ({max_dimension}px).",
            status_code=400,
        )
    if (width * height) > max_pixels:
        raw_img.close()
        raise ImageValidationError(
            "Total image pixel count exceeds maximum permitted limit.",
            status_code=400,
        )

    # Force loading of pixel data to catch corrupted or truncated streams
    try:
        raw_img.load()
    except Exception as e:
        raw_img.close()
        logger.warning("Corrupted or truncated image stream: %s", type(e).__name__)
        raise ImageValidationError(
            "The uploaded image file is corrupted or truncated.",
            status_code=400,
        ) from e

    # Apply safe EXIF orientation normalization
    try:
        transposed = ImageOps.exif_transpose(raw_img)
    except Exception:
        transposed = raw_img

    # Strip metadata and convert to clean RGB
    try:
        clean_img = Image.new("RGB", transposed.size)
        if transposed.mode != "RGB":
            rgb_transposed = transposed.convert("RGB")
            clean_img.paste(rgb_transposed)
            if rgb_transposed != transposed:
                rgb_transposed.close()
        else:
            clean_img.paste(transposed)
    finally:
        if transposed != raw_img:
            transposed.close()
        raw_img.close()

    return clean_img


# ── Legacy Preprocessing Pipeline (Backwards Compatibility) ───────────────────
try:
    import torchvision.transforms as transforms

    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225],
        ),
    ])

    def preprocess(img):
        img = transform(img)
        return img.unsqueeze(0)

except ImportError:
    transform = None

    def preprocess(img):
        raise RuntimeError("torchvision is required for preprocess")
