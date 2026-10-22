from typing import Tuple
import numpy as np

from models.responses import BoundingBox, CropBox, FaceInfo, FaceLandmarks, Point2D


class ImageCropper:
    """
    Performs face-aware cropping around a detected face bounding box with a configurable margin.
    Clamps within image boundaries and maps coordinates to the cropped coordinate system.
    """

    def __init__(self, crop_margin_percent: float = 25.0):
        self.crop_margin_percent = crop_margin_percent

    def crop_face(
        self, image: np.ndarray, face: FaceInfo
    ) -> Tuple[np.ndarray, CropBox, BoundingBox, FaceLandmarks]:
        img_h, img_w = image.shape[:2]
        bx = face.boundingBox.x
        by = face.boundingBox.y
        bw = face.boundingBox.width
        bh = face.boundingBox.height

        dx = int(round(bw * (self.crop_margin_percent / 100.0)))
        dy = int(round(bh * (self.crop_margin_percent / 100.0)))

        crop_x = max(0, bx - dx)
        crop_y = max(0, by - dy)
        crop_x2 = min(img_w, bx + bw + dx)
        crop_y2 = min(img_h, by + bh + dy)

        crop_w = max(1, crop_x2 - crop_x)
        crop_h = max(1, crop_y2 - crop_y)

        cropped_img = image[crop_y : crop_y + crop_h, crop_x : crop_x + crop_w].copy()

        crop_box = CropBox(x=crop_x, y=crop_y, width=crop_w, height=crop_h)

        # Map face coordinates to crop relative coordinates
        new_bx = max(0, min(bx - crop_x, crop_w - 1))
        new_by = max(0, min(by - crop_y, crop_h - 1))
        new_bw = max(1, min(bw, crop_w - new_bx))
        new_bh = max(1, min(bh, crop_h - new_by))
        new_bbox = BoundingBox(x=new_bx, y=new_by, width=new_bw, height=new_bh)

        def map_pt(pt: Point2D) -> Point2D:
            return Point2D(
                x=max(0, min(pt.x - crop_x, crop_w - 1)),
                y=max(0, min(pt.y - crop_y, crop_h - 1)),
            )

        new_landmarks = FaceLandmarks(
            leftEye=map_pt(face.landmarks.leftEye),
            rightEye=map_pt(face.landmarks.rightEye),
            nose=map_pt(face.landmarks.nose),
            leftMouth=map_pt(face.landmarks.leftMouth),
            rightMouth=map_pt(face.landmarks.rightMouth),
        )

        return cropped_img, crop_box, new_bbox, new_landmarks
