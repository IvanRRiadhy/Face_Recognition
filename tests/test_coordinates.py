import os
import cv2
import pytest

from detectors.yunet_face_detector import YuNetFaceDetector

MODEL_PATH = "assets/models/face_detection_yunet_2023mar.onnx"
FIXTURES_DIR = "tests/fixtures"


@pytest.fixture(scope="module")
def detector():
    return YuNetFaceDetector(model_path=MODEL_PATH)


class TestCoordinateBounds:
    """
    Requirement 7: Add coordinate validation tests:
    - Bounding box must remain inside image bounds
    - Landmark coordinates must remain inside image bounds
    - Ensure coordinates are in the original image coordinate system
    """

    def test_single_face_coordinates_within_bounds(self, detector):
        img_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        img = cv2.imread(img_path)
        img_h, img_w = img.shape[:2]

        faces = detector.detect(img)
        assert len(faces) == 1
        face = faces[0]

        # Bounding box bounds check
        bx = face.boundingBox.x
        by = face.boundingBox.y
        bw = face.boundingBox.width
        bh = face.boundingBox.height

        assert 0 <= bx < img_w, f"bx={bx} out of [0, {img_w})"
        assert 0 <= by < img_h, f"by={by} out of [0, {img_h})"
        assert 0 < bw <= img_w, f"bw={bw} exceeds width"
        assert 0 < bh <= img_h, f"bh={bh} exceeds height"
        assert bx + bw <= img_w, f"bx+bw={bx+bw} exceeds img_w={img_w}"
        assert by + bh <= img_h, f"by+bh={by+bh} exceeds img_h={img_h}"

        # 5 facial landmarks bounds check
        landmarks = face.landmarks
        for name, pt in [
            ("leftEye", landmarks.leftEye),
            ("rightEye", landmarks.rightEye),
            ("nose", landmarks.nose),
            ("leftMouth", landmarks.leftMouth),
            ("rightMouth", landmarks.rightMouth),
        ]:
            assert 0 <= pt.x < img_w, f"{name}.x={pt.x} outside [0, {img_w})"
            assert 0 <= pt.y < img_h, f"{name}.y={pt.y} outside [0, {img_h})"

        # Anatomy / orientation check: leftEye should be to the left of rightEye
        assert landmarks.leftEye.x <= landmarks.rightEye.x, "leftEye.x should be <= rightEye.x"
        assert landmarks.leftMouth.x <= landmarks.rightMouth.x, "leftMouth.x should be <= rightMouth.x"

    def test_multiple_faces_coordinates_within_bounds(self, detector):
        img_path = os.path.join(FIXTURES_DIR, "multiple_faces.jpg")
        img = cv2.imread(img_path)
        img_h, img_w = img.shape[:2]

        faces = detector.detect(img)
        assert len(faces) >= 2

        for i, face in enumerate(faces):
            bx = face.boundingBox.x
            by = face.boundingBox.y
            bw = face.boundingBox.width
            bh = face.boundingBox.height

            assert 0 <= bx < img_w, f"face {i} bx={bx} out of bounds"
            assert 0 <= by < img_h, f"face {i} by={by} out of bounds"
            assert bx + bw <= img_w, f"face {i} bounding box exceeds img_w={img_w}"
            assert by + bh <= img_h, f"face {i} bounding box exceeds img_h={img_h}"

            landmarks = face.landmarks
            for name, pt in [
                ("leftEye", landmarks.leftEye),
                ("rightEye", landmarks.rightEye),
                ("nose", landmarks.nose),
                ("leftMouth", landmarks.leftMouth),
                ("rightMouth", landmarks.rightMouth),
            ]:
                assert 0 <= pt.x < img_w, f"face {i} {name}.x={pt.x} out of bounds"
                assert 0 <= pt.y < img_h, f"face {i} {name}.y={pt.y} out of bounds"
