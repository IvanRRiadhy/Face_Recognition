import base64
import os
from typing import Optional, Tuple
import cv2
import numpy as np


class ImageEncoder:
    """
    Encodes image numpy array to compressed image bytes and base64.
    Format handling:
    - JPEG (.jpg, .jpeg) and WebP (.webp) are encoded as JPEG using qualityCompression (1-100).
    - PNG (.png) uses lossless compression settings and preserves alpha transparency.
    """

    @staticmethod
    def encode(
        image: np.ndarray,
        filename: Optional[str],
        quality_compression: int = 100,
    ) -> Tuple[bytes, str, str, str]:
        ext = ".jpg"
        if filename:
            parsed_ext = os.path.splitext(filename)[1].lower()
            if parsed_ext == ".png":
                ext = ".png"
            elif parsed_ext in {".jpg", ".jpeg", ".webp"}:
                ext = ".jpg"

        quality = max(1, min(quality_compression, 100))

        if ext == ".png":
            # PNG is lossless; use IMWRITE_PNG_COMPRESSION (0 to 9, where 9 is max compression)
            # Map quality 1-100 to level 9..1 (higher quality/fast vs max compression) or default 3
            png_compression = 3
            encode_params = [cv2.IMWRITE_PNG_COMPRESSION, png_compression]
            output_format = "png"
            content_type = "image/png"
            success, buffer = cv2.imencode(".png", image, encode_params)
        else:
            encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
            output_format = "jpeg"
            content_type = "image/jpeg"
            success, buffer = cv2.imencode(".jpg", image, encode_params)

        if not success or buffer is None:
            raise RuntimeError("Failed to encode processed image.")

        img_bytes = buffer.tobytes()
        base64_str = base64.b64encode(img_bytes).decode("utf-8")

        return img_bytes, base64_str, output_format, content_type
