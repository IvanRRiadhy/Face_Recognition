from typing import Optional, Tuple
import cv2
import numpy as np

from models.responses import BoundingBox, FaceLandmarks, Point2D


class ImageResizer:
    """
    Applies pixelCompression and maxWidth / maxHeight dimension constraints.
    - Preserves aspect ratio.
    - NEVER upscales the image.
    - Accurately maps face bounding boxes and landmarks to the resized coordinate space.
    """

    @staticmethod
    def calculate_target_dimensions(
        original_w: int,
        original_h: int,
        pixel_compression: int,
        max_width: Optional[int] = None,
        max_height: Optional[int] = None,
    ) -> Tuple[int, int]:
        # 1. Pixel compression: retain X% of original dimensions
        pixel_ratio = max(1, min(pixel_compression, 100)) / 100.0
        w_pixel = max(1, int(round(original_w * pixel_ratio)))
        h_pixel = max(1, int(round(original_h * pixel_ratio)))

        # 2. Maximum dimension constraint while preserving aspect ratio and avoiding upscaling
        scales = [1.0]
        if max_width is not None and max_width > 0:
            scales.append(max_width / float(w_pixel))
        if max_height is not None and max_height > 0:
            scales.append(max_height / float(h_pixel))

        scale = min(scales)
        target_w = max(1, int(round(w_pixel * scale)))
        target_h = max(1, int(round(h_pixel * scale)))

        return target_w, target_h

    @classmethod
    def resize_image(
        cls,
        image: np.ndarray,
        pixel_compression: int,
        max_width: Optional[int] = None,
        max_height: Optional[int] = None,
    ) -> Tuple[np.ndarray, float, float]:
        orig_h, orig_w = image.shape[:2]
        target_w, target_h = cls.calculate_target_dimensions(
            original_w=orig_w,
            original_h=orig_h,
            pixel_compression=pixel_compression,
            max_width=max_width,
            max_height=max_height,
        )

        if target_w == orig_w and target_h == orig_h:
            return image, 1.0, 1.0

        scale_x = target_w / float(orig_w)
        scale_y = target_h / float(orig_h)

        interpolation = cv2.INTER_AREA if scale_x < 1.0 else cv2.INTER_LINEAR
        resized_img = cv2.resize(image, (target_w, target_h), interpolation=interpolation)

        return resized_img, scale_x, scale_y

    @staticmethod
    def scale_face_coordinates(
        bbox: BoundingBox,
        landmarks: FaceLandmarks,
        scale_x: float,
        scale_y: float,
        target_w: int,
        target_h: int,
    ) -> Tuple[BoundingBox, FaceLandmarks]:
        new_bx = max(0, min(int(round(bbox.x * scale_x)), target_w - 1))
        new_by = max(0, min(int(round(bbox.y * scale_y)), target_h - 1))
        new_bw = max(1, min(int(round(bbox.width * scale_x)), target_w - new_bx))
        new_bh = max(1, min(int(round(bbox.height * scale_y)), target_h - new_by))
        scaled_bbox = BoundingBox(x=new_bx, y=new_by, width=new_bw, height=new_bh)

        def scale_pt(pt: Point2D) -> Point2D:
            return Point2D(
                x=max(0, min(int(round(pt.x * scale_x)), target_w - 1)),
                y=max(0, min(int(round(pt.y * scale_y)), target_h - 1)),
            )

        scaled_landmarks = FaceLandmarks(
            leftEye=scale_pt(landmarks.leftEye),
            rightEye=scale_pt(landmarks.rightEye),
            nose=scale_pt(landmarks.nose),
            leftMouth=scale_pt(landmarks.leftMouth),
            rightMouth=scale_pt(landmarks.rightMouth),
        )

        return scaled_bbox, scaled_landmarks
