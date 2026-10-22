import os
import cv2
import pytest

from detectors.yunet_face_detector import YuNetFaceDetector

MODEL_PATH = "assets/models/face_detection_yunet_2023mar.onnx"
FIXTURES_DIR = "tests/fixtures"


@pytest.fixture(scope="module")
def detector():
    assert os.path.exists(MODEL_PATH), f"Model not found at {MODEL_PATH}"
    return YuNetFaceDetector(model_path=MODEL_PATH)


class TestFaceDetection:
    """
    Automated tests for YuNet face detector using local fixtures:
    - Single face
    - Multiple faces
    - No face
    """

    def test_single_face_detection(self, detector):
        img_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        img = cv2.imread(img_path)
        assert img is not None

        faces = detector.detect(img)
        assert len(faces) == 1
        assert faces[0].confidence >= 0.8
        assert faces[0].boundingBox.width > 0
        assert faces[0].boundingBox.height > 0

    def test_multiple_faces_detection(self, detector):
        img_path = os.path.join(FIXTURES_DIR, "multiple_faces.jpg")
        img = cv2.imread(img_path)
        assert img is not None

        faces = detector.detect(img)
        assert len(faces) >= 2
        for face in faces:
            assert face.confidence >= 0.6
            assert face.boundingBox.width > 0
            assert face.boundingBox.height > 0

    def test_no_face_detection(self, detector):
        img_path = os.path.join(FIXTURES_DIR, "no_face.jpg")
        img = cv2.imread(img_path)
        assert img is not None

        faces = detector.detect(img)
        assert len(faces) == 0
