import os
import threading
from typing import List
import cv2
import numpy as np

from models.responses import BoundingBox, FaceInfo, FaceLandmarks, Point2D
from .face_detector import BaseFaceDetector


class YuNetFaceDetector(BaseFaceDetector):
    """
    Thread-safe implementation of YuNet face detector using OpenCV FaceDetectorYN.
    Coordinates returned are in original image pixel space.
    """

    def __init__(
        self,
        model_path: str,
        score_threshold: float = 0.6,
        nms_threshold: float = 0.3,
        top_k: int = 5000,
    ):
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"YuNet ONNX model not found at: {model_path}")

        self._model_path = model_path
        self._score_threshold = score_threshold
        self._nms_threshold = nms_threshold
        self._top_k = top_k
        self._lock = threading.Lock()

        # Initialize with placeholder input size (320, 320)
        self._detector = cv2.FaceDetectorYN.create(
            model=self._model_path,
            config="",
            input_size=(320, 320),
            score_threshold=self._score_threshold,
            nms_threshold=self._nms_threshold,
            top_k=self._top_k,
        )

    @property
    def model_name(self) -> str:
        return "yunet"

    def detect(self, image: np.ndarray) -> List[FaceInfo]:
        """
        Detect faces in the given BGR image.
        Synchronized with a lock to ensure thread safety across concurrent requests.
        """
        if image is None or image.size == 0:
            return []

        img_h, img_w = image.shape[:2]

        with self._lock:
            # Update input size to match current image dimensions
            self._detector.setInputSize((img_w, img_h))
            _, raw_faces = self._detector.detect(image)

        if raw_faces is None or len(raw_faces) == 0:
            return []

        detected_faces: List[FaceInfo] = []
        for face in raw_faces:
            # YuNet output format:
            # face[0:4]: [x, y, w, h] of bounding box
            # face[4:6]: [x_re, y_re] right eye
            # face[6:8]: [x_le, y_le] left eye
            # face[8:10]: [x_nt, y_nt] nose tip
            # face[10:12]: [x_rcm, y_rcm] right corner of mouth
            # face[12:14]: [x_lcm, y_lcm] left corner of mouth
            # face[14]: confidence score
            # Note: OpenCV YuNet landmark indices:
            # (4,5) = right_eye (viewer's left or subject's right eye)
            # In OpenCV documentation conventions:
            # 0: right eye, 1: left eye, 2: nose, 3: right mouth, 4: left mouth
            # Let's map subject-centric: leftEye/rightEye or image-left/right:
            # In YuNet:
            # Landmark 0 (face[4], face[5]) is right eye of person (left in image)
            # Landmark 1 (face[6], face[7]) is left eye of person (right in image)
            # To be clear and consistent with standard anatomical naming:
            # leftEye = face[4:6] (if viewer's left) or anatomically left:
            # Usually: x of right eye in face[4] is smaller than left eye in face[6].
            # Let's check coordinate positions:
            x1, y1, w, h = face[0:4]
            conf = float(face[14])

            # Clamp bounding box inside image bounds
            bx = max(0, min(int(round(x1)), img_w - 1))
            by = max(0, min(int(round(y1)), img_h - 1))
            bw = max(1, min(int(round(w)), img_w - bx))
            bh = max(1, min(int(round(h)), img_h - by))

            # Landmarks points
            # pt0: right eye (viewer's left)
            # pt1: left eye (viewer's right)
            # pt2: nose tip
            # pt3: right mouth
            # pt4: left mouth
            # Standard conventions in face datasets: leftEye is subject's left eye or viewer's left.
            # In YuNet OpenCV docs:
            # landmark 0: right eye
            # landmark 1: left eye
            # landmark 2: nose tip
            # landmark 3: right mouth corner
            # landmark 4: left mouth corner
            # Notice user example:
            # "leftEye": { "x": 475, "y": 270 }, "rightEye": { "x": 560, "y": 268 }
            # Notice 475 < 560! So in the user's specification, "leftEye" is the left side of the image (x=475),
            # and "rightEye" is the right side of the image (x=560).
            # Let's assign based on x position to guarantee leftEye.x <= rightEye.x:
            eye_a = (int(round(face[4])), int(round(face[5])))
            eye_b = (int(round(face[6])), int(round(face[7])))
            if eye_a[0] <= eye_b[0]:
                left_eye_pt, right_eye_pt = eye_a, eye_b
            else:
                left_eye_pt, right_eye_pt = eye_b, eye_a

            nose_pt = (int(round(face[8])), int(round(face[9])))

            mouth_a = (int(round(face[10])), int(round(face[11])))
            mouth_b = (int(round(face[12])), int(round(face[13])))
            if mouth_a[0] <= mouth_b[0]:
                left_mouth_pt, right_mouth_pt = mouth_a, mouth_b
            else:
                left_mouth_pt, right_mouth_pt = mouth_b, mouth_a

            # Ensure landmarks remain within image boundaries
            def clamp_pt(pt):
                return Point2D(
                    x=max(0, min(pt[0], img_w - 1)),
                    y=max(0, min(pt[1], img_h - 1)),
                )

            landmarks = FaceLandmarks(
                leftEye=clamp_pt(left_eye_pt),
                rightEye=clamp_pt(right_eye_pt),
                nose=clamp_pt(nose_pt),
                leftMouth=clamp_pt(left_mouth_pt),
                rightMouth=clamp_pt(right_mouth_pt),
            )

            bbox = BoundingBox(x=bx, y=by, width=bw, height=bh)

            detected_faces.append(
                FaceInfo(
                    confidence=round(conf, 4),
                    boundingBox=bbox,
                    landmarks=landmarks,
                )
            )

        return detected_faces
