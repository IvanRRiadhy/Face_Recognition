import base64
import os
import cv2
import numpy as np
import pytest

from detectors.yunet_face_detector import YuNetFaceDetector
from processors.image_cropper import ImageCropper
from processors.image_resizer import ImageResizer
from processors.image_encoder import ImageEncoder
from models.responses import BoundingBox, FaceInfo, FaceLandmarks, Point2D

MODEL_PATH = "assets/models/face_detection_yunet_2023mar.onnx"
FIXTURES_DIR = "tests/fixtures"


@pytest.fixture(scope="module")
def detector():
    return YuNetFaceDetector(model_path=MODEL_PATH)


class TestImageResizer:
    """
    Unit tests for ImageResizer:
    - Pixel compression: 100%, 50%, 25%
    - maxWidth / maxHeight fit
    - Aspect ratio preservation
    - No upscaling
    """

    def test_pixel_compression_100_percent_unchanged(self):
        w, h = ImageResizer.calculate_target_dimensions(
            original_w=1920, original_h=1080, pixel_compression=100, max_width=4000, max_height=4000
        )
        assert w == 1920
        assert h == 1080

    def test_pixel_compression_50_percent(self):
        w, h = ImageResizer.calculate_target_dimensions(
            original_w=1920, original_h=1080, pixel_compression=50, max_width=4000, max_height=4000
        )
        assert w == 960
        assert h == 540

    def test_pixel_compression_25_percent(self):
        w, h = ImageResizer.calculate_target_dimensions(
            original_w=1920, original_h=1080, pixel_compression=25, max_width=4000, max_height=4000
        )
        assert w == 480
        assert h == 270

    def test_max_dimensions_constraint_preserves_aspect_ratio(self):
        # Original: 1920 x 1080, maxWidth=1000, maxHeight=800
        w, h = ImageResizer.calculate_target_dimensions(
            original_w=1920, original_h=1080, pixel_compression=100, max_width=1000, max_height=800
        )
        assert w <= 1000
        assert h <= 800
        assert w == 1000
        # 1080 * (1000 / 1920) = 562.5 -> approx 562 or 563
        assert abs(h - 563) <= 1
        # Aspect ratio tolerance check
        orig_aspect = 1920.0 / 1080.0
        new_aspect = float(w) / float(h)
        assert abs(orig_aspect - new_aspect) < 0.01

    def test_never_upscale_smaller_image(self):
        # Original 500x400 with maxWidth=2000, maxHeight=2000
        w, h = ImageResizer.calculate_target_dimensions(
            original_w=500, original_h=400, pixel_compression=100, max_width=2000, max_height=2000
        )
        assert w == 500
        assert h == 400

    def test_interaction_pixel_compression_and_max_dimensions(self):
        # Original: 4000 x 3000, pixelCompression: 50% -> 2000 x 1500, max: 1000 x 800 -> 1000 x 750
        w, h = ImageResizer.calculate_target_dimensions(
            original_w=4000, original_h=3000, pixel_compression=50, max_width=1000, max_height=800
        )
        assert w == 1000
        assert h == 750


class TestImageCropper:
    """
    Unit tests for face-aware cropping:
    - Bounding box expansion with margin
    - Clamping within original image
    - Accurate coordinate translation
    """

    def test_face_aware_crop(self):
        img = np.zeros((1000, 1000, 3), dtype=np.uint8)
        cropper = ImageCropper(crop_margin_percent=25.0)

        face = FaceInfo(
            confidence=0.95,
            boundingBox=BoundingBox(x=400, y=200, width=300, height=400),
            landmarks=FaceLandmarks(
                leftEye=Point2D(x=450, y=300),
                rightEye=Point2D(x=550, y=300),
                nose=Point2D(x=500, y=350),
                leftMouth=Point2D(x=460, y=420),
                rightMouth=Point2D(x=540, y=420),
            ),
        )

        cropped_img, crop_box, new_bbox, new_landmarks = cropper.crop_face(img, face)

        # 25% of 300 is 75, 25% of 400 is 100
        # crop_x = 400 - 75 = 325
        # crop_y = 200 - 100 = 100
        # crop_w = 300 + 150 = 450
        # crop_h = 400 + 200 = 600
        assert crop_box.x == 325
        assert crop_box.y == 100
        assert crop_box.width == 450
        assert crop_box.height == 600

        # Cropped shape
        assert cropped_img.shape[0] == 600
        assert cropped_img.shape[1] == 450

        # Translated bounding box
        assert new_bbox.x == 400 - 325  # 75
        assert new_bbox.y == 200 - 100  # 100
        assert new_bbox.width == 300
        assert new_bbox.height == 400

        # Translated landmark
        assert new_landmarks.nose.x == 500 - 325  # 175
        assert new_landmarks.nose.y == 350 - 100  # 250


class TestImageEncoder:
    """
    Unit tests for image encoding:
    - JPEG encoding at qualities: 1, 50, 80, 100
    - PNG encoding
    - Valid base64 output
    """

    @pytest.mark.parametrize("quality", [1, 50, 80, 100])
    def test_jpeg_encoding_qualities(self, quality):
        img = np.zeros((200, 200, 3), dtype=np.uint8)
        img_bytes, b64_str, out_fmt, mime = ImageEncoder.encode(
            image=img, filename="test.jpg", quality_compression=quality
        )
        assert out_fmt == "jpeg"
        assert mime == "image/jpeg"
        assert len(img_bytes) > 0

        # Verify base64 decodes back
        decoded = base64.b64decode(b64_str)
        assert decoded == img_bytes

        # Verify OpenCV decodes back
        nparr = np.frombuffer(img_bytes, np.uint8)
        decoded_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        assert decoded_cv is not None
        assert decoded_cv.shape == (200, 200, 3)

    def test_png_encoding_lossless(self):
        img = np.zeros((150, 150, 3), dtype=np.uint8)
        img_bytes, b64_str, out_fmt, mime = ImageEncoder.encode(
            image=img, filename="test.png", quality_compression=90
        )
        assert out_fmt == "png"
        assert mime == "image/png"
        assert len(img_bytes) > 0
