import os
from typing import Optional, Tuple
import cv2
import numpy as np

from models.responses import ImageDimensions, ValidationReason

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg"}
ALLOWED_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "application/octet-stream",  # often sent by generic clients, verify by magic bytes / cv2 decode
}


class ImageValidator:
    """
    Validates uploaded file size, file format, and safely decodes the image bytes.
    """

    def __init__(self, max_upload_size_mb: int = 10):
        self.max_upload_size_bytes = max_upload_size_mb * 1024 * 1024

    def validate_file_size(self, file_size: int) -> Tuple[bool, Optional[ValidationReason]]:
        if file_size > self.max_upload_size_bytes:
            return False, ValidationReason.FILE_TOO_LARGE
        return True, None

    def validate_filename(self, filename: Optional[str]) -> Tuple[bool, Optional[ValidationReason]]:
        if not filename:
            return False, ValidationReason.UNSUPPORTED_FORMAT

        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return False, ValidationReason.UNSUPPORTED_FORMAT

        return True, None

    def decode_image(
        self, image_bytes: bytes
    ) -> Tuple[bool, Optional[ValidationReason], Optional[np.ndarray], Optional[ImageDimensions]]:
        if not image_bytes or len(image_bytes) == 0:
            return False, ValidationReason.INVALID_IMAGE, None, None

        # Safe decode from in-memory bytes
        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None or img.size == 0:
                return False, ValidationReason.INVALID_IMAGE, None, None

            height, width = img.shape[:2]
            return True, None, img, ImageDimensions(width=width, height=height)
        except Exception:
            return False, ValidationReason.INVALID_IMAGE, None, None
