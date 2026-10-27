import os
import pytest
from fastapi.testclient import TestClient

from api.main import app

FIXTURES_DIR = "tests/fixtures"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


class TestAPIEndpoints:
    """
    End-to-end tests for all API endpoints:
    - GET /
    - GET /health
    - POST /validate with detectFace=true / false
    - Dimension checks (valid, IMAGE_TOO_LARGE)
    - Unsupported format, corrupted image, file size limits
    - Missing fields (422)
    """

    def test_root_endpoint(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Image Validation / Face Detection Engine"
        assert "/docs" in data["docs"]
        assert "/health" in data["health"]

    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "image-validator"
        assert data["faceDetector"] == "yunet"
        assert data["modelLoaded"] is True

    def test_validate_single_face_pass(self, client):
        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        with open(file_path, "rb") as f:
            response = client.post(
                "/validate",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
                data={"maxWidth": "1500", "maxHeight": "1500", "detectFace": "true"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["reason"] == "VALID"
        assert data["image"]["width"] == 512
        assert data["image"]["height"] == 512
        assert len(data["faces"]) == 1
        face = data["faces"][0]
        assert face["confidence"] >= 0.8
        assert "boundingBox" in face
        assert "landmarks" in face
        assert "leftEye" in face["landmarks"]
        assert "rightEye" in face["landmarks"]
        assert "nose" in face["landmarks"]
        assert "leftMouth" in face["landmarks"]
        assert "rightMouth" in face["landmarks"]

    def test_validate_detect_face_false_does_not_run_detector(self, client):
        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        with open(file_path, "rb") as f:
            response = client.post(
                "/validate",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
                data={"maxWidth": "1500", "maxHeight": "1500", "detectFace": "false"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["reason"] == "VALID"
        assert data["faces"] == []

    def test_validate_no_face_found(self, client):
        file_path = os.path.join(FIXTURES_DIR, "no_face.jpg")
        with open(file_path, "rb") as f:
            response = client.post(
                "/validate",
                files={"imageFile": ("no_face.jpg", f, "image/jpeg")},
                data={"maxWidth": "1500", "maxHeight": "1500", "detectFace": "true"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["reason"] == "NO_FACE"
        assert data["faces"] == []

    def test_validate_multiple_faces_returns_all(self, client):
        file_path = os.path.join(FIXTURES_DIR, "multiple_faces.jpg")
        with open(file_path, "rb") as f:
            response = client.post(
                "/validate",
                files={"imageFile": ("multiple_faces.jpg", f, "image/jpeg")},
                data={"maxWidth": "2000", "maxHeight": "2000", "detectFace": "true"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["reason"] == "VALID"
        assert len(data["faces"]) >= 2

    def test_validate_image_too_large(self, client):
        # single_face.jpg is 512x512, setting maxWidth=500 fails
        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        with open(file_path, "rb") as f:
            response = client.post(
                "/validate",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
                data={"maxWidth": "500", "maxHeight": "1500", "detectFace": "true"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["reason"] == "IMAGE_TOO_LARGE"
        assert data["image"]["width"] == 512
        assert data["image"]["height"] == 512
        assert data["faces"] == []

    def test_validate_unsupported_file_extension(self, client):
        response = client.post(
            "/validate",
            files={"imageFile": ("document.pdf", b"%PDF-1.4...", "application/pdf")},
            data={"maxWidth": "1500", "maxHeight": "1500", "detectFace": "true"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["reason"] == "WRONG_FORMAT"

    def test_validate_corrupted_image(self, client):
        response = client.post(
            "/validate",
            files={"imageFile": ("bad.jpg", b"not-a-valid-jpeg-bytes", "image/jpeg")},
            data={"maxWidth": "1500", "maxHeight": "1500", "detectFace": "true"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["reason"] == "NO_IMAGE"

    def test_validate_empty_or_missing_image_returns_no_image(self, client):
        # Empty bytes
        response = client.post(
            "/validate",
            files={"imageFile": ("empty.jpg", b"", "image/jpeg")},
            data={"maxWidth": "1500", "maxHeight": "1500", "detectFace": "true"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["reason"] == "NO_IMAGE"

        # Missing imageFile field entirely
        response_missing = client.post(
            "/validate",
            data={"maxWidth": "1500", "maxHeight": "1500", "detectFace": "true"},
        )
        assert response_missing.status_code == 200
        data_missing = response_missing.json()
        assert data_missing["valid"] is False
        assert data_missing["reason"] == "NO_IMAGE"

    def test_validate_file_too_large(self, client):
        # Exceed MAX_UPLOAD_SIZE_MB (default 10MB)
        # Create a payload of 10.5 MB named test.jpg
        large_bytes = b"0" * (11 * 1024 * 1024)
        response = client.post(
            "/validate",
            files={"imageFile": ("huge.jpg", large_bytes, "image/jpeg")},
            data={"maxWidth": "1500", "maxHeight": "1500", "detectFace": "true"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["reason"] == "FILE_TOO_LARGE"

    def test_validate_missing_required_parameter_returns_422(self, client):
        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        with open(file_path, "rb") as f:
            # Missing detectFace
            response = client.post(
                "/validate",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
                data={"maxWidth": "1500", "maxHeight": "1500"},
            )
        assert response.status_code == 422


class TestCompressAPI:
    """
    Tests for POST /compress endpoint:
    1. Normal compression
    2. Pixel compression (50%)
    3. Maximum dimension constraint resizing
    4. Face detection
    5. Face-aware cropping
    6. detectFace=false
    7. cropImage=true without detectFace=true
    8. No face + cropImage=true
    9. Multiple faces + cropImage=true -> MULTI_FACE
    10. Invalid image
    11. Unsupported format
    12. File too large
    13. Invalid qualityCompression range (0, 101 -> 422)
    14. Invalid pixelCompression range (0, 101 -> 422)
    """

    def test_compress_normal_flow(self, client):
        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        with open(file_path, "rb") as f:
            response = client.post(
                "/compress",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
                data={
                    "maxWidth": "1000",
                    "maxHeight": "1000",
                    "detectFace": "true",
                    "qualityCompression": "85",
                    "pixelCompression": "100",
                    "cropImage": "false",
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["reason"] == "VALID"
        assert data["image"]["width"] == 512
        assert data["image"]["height"] == 512
        assert data["image"]["outputFormat"] == "jpeg"
        assert data["contentType"] == "image/jpeg"
        assert data["imageData"] is not None
        assert len(data["faces"]) == 1
        face = data["faces"][0]
        assert "originalBoundingBox" in face
        assert "boundingBox" in face
        assert "originalLandmarks" in face
        assert "landmarks" in face

    def test_compress_pixel_compression(self, client):
        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        with open(file_path, "rb") as f:
            response = client.post(
                "/compress",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
                data={
                    "maxWidth": "1000",
                    "maxHeight": "1000",
                    "detectFace": "false",
                    "qualityCompression": "80",
                    "pixelCompression": "50",
                    "cropImage": "false",
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["image"]["width"] == 256
        assert data["image"]["height"] == 256

    def test_compress_resizes_when_exceeding_max_dimensions(self, client):
        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        with open(file_path, "rb") as f:
            response = client.post(
                "/compress",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
                data={
                    "maxWidth": "300",
                    "maxHeight": "300",
                    "detectFace": "false",
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["image"]["width"] == 300
        assert data["image"]["height"] == 300

    def test_compress_face_aware_crop(self, client):
        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        with open(file_path, "rb") as f:
            response = client.post(
                "/compress",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
                data={
                    "maxWidth": "1000",
                    "maxHeight": "1000",
                    "detectFace": "true",
                    "cropImage": "true",
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["crop"]["applied"] is True
        assert data["crop"]["originalCropBox"] is not None
        assert data["image"]["width"] < 512
        assert data["image"]["height"] < 512
        # Check coordinate translation
        face = data["faces"][0]
        assert face["boundingBox"]["x"] <= face["originalBoundingBox"]["x"]

    def test_compress_crop_requires_face_detection(self, client):
        import base64
        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        with open(file_path, "rb") as f:
            raw_bytes = f.read()
        with open(file_path, "rb") as f:
            response = client.post(
                "/compress",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
                data={
                    "maxWidth": "1000",
                    "maxHeight": "1000",
                    "detectFace": "false",
                    "cropImage": "true",
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["reason"] == "CROP_REQUIRES_FACE_DETECTION"
        assert data["imageData"] == base64.b64encode(raw_bytes).decode("utf-8")

    def test_compress_no_face_with_crop(self, client):
        import base64
        file_path = os.path.join(FIXTURES_DIR, "no_face.jpg")
        with open(file_path, "rb") as f:
            raw_bytes = f.read()
        with open(file_path, "rb") as f:
            response = client.post(
                "/compress",
                files={"imageFile": ("no_face.jpg", f, "image/jpeg")},
                data={
                    "maxWidth": "1000",
                    "maxHeight": "1000",
                    "detectFace": "true",
                    "cropImage": "true",
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["reason"] == "NO_FACE"
        assert data["imageData"] == base64.b64encode(raw_bytes).decode("utf-8")

    def test_compress_multiple_faces_with_crop_returns_MULTI_FACE(self, client):
        import base64
        file_path = os.path.join(FIXTURES_DIR, "multiple_faces.jpg")
        with open(file_path, "rb") as f:
            raw_bytes = f.read()
        with open(file_path, "rb") as f:
            response = client.post(
                "/compress",
                files={"imageFile": ("multiple_faces.jpg", f, "image/jpeg")},
                data={
                    "maxWidth": "2000",
                    "maxHeight": "2000",
                    "detectFace": "true",
                    "cropImage": "true",
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["reason"] in ("MULTIPLE_FACES", "MULTI_FACE")
        assert data["imageData"] == base64.b64encode(raw_bytes).decode("utf-8")

    def test_compress_no_image_and_wrong_format(self, client):
        import base64
        # 1. Corrupted image -> NO_IMAGE, still returns raw bytes as base64
        corrupted_bytes = b"corrupted-image-content"
        res_corrupt = client.post(
            "/compress",
            files={"imageFile": ("corrupt.jpg", corrupted_bytes, "image/jpeg")},
        )
        assert res_corrupt.status_code == 200
        data_corrupt = res_corrupt.json()
        assert data_corrupt["valid"] is False
        assert data_corrupt["reason"] == "NO_IMAGE"
        assert data_corrupt["imageData"] == base64.b64encode(corrupted_bytes).decode("utf-8")

        # 2. Empty image -> NO_IMAGE, imageData is None
        res_empty = client.post(
            "/compress",
            files={"imageFile": ("empty.jpg", b"", "image/jpeg")},
        )
        assert res_empty.status_code == 200
        data_empty = res_empty.json()
        assert data_empty["valid"] is False
        assert data_empty["reason"] == "NO_IMAGE"
        assert data_empty["imageData"] is None

        # 3. Missing imageFile field -> NO_IMAGE, imageData is None
        res_missing = client.post(
            "/compress",
            data={"prefix": "ipsotek"},
        )
        assert res_missing.status_code == 200
        data_missing = res_missing.json()
        assert data_missing["valid"] is False
        assert data_missing["reason"] == "NO_IMAGE"
        assert data_missing["imageData"] is None

        # 4. Wrong format -> WRONG_FORMAT, still returns raw bytes as base64
        wrong_fmt_bytes = b"GIF89a..."
        res_fmt = client.post(
            "/compress",
            files={"imageFile": ("anim.gif", wrong_fmt_bytes, "image/gif")},
        )
        assert res_fmt.status_code == 200
        data_fmt = res_fmt.json()
        assert data_fmt["valid"] is False
        assert data_fmt["reason"] == "WRONG_FORMAT"
        assert data_fmt["imageData"] == base64.b64encode(wrong_fmt_bytes).decode("utf-8")

    def test_compress_invalid_quality_compression_returns_422(self, client):
        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        with open(file_path, "rb") as f:
            response = client.post(
                "/compress",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
                data={
                    "maxWidth": "1000",
                    "maxHeight": "1000",
                    "detectFace": "true",
                    "qualityCompression": "105",  # Exceeds 100
                },
            )
        assert response.status_code == 422

    def test_compress_invalid_pixel_compression_returns_422(self, client):
        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        with open(file_path, "rb") as f:
            response = client.post(
                "/compress",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
                data={
                    "maxWidth": "1000",
                    "maxHeight": "1000",
                    "detectFace": "true",
                    "pixelCompression": "105",  # Exceeds 100
                },
            )
        assert response.status_code == 422

    def test_compress_cdn_upload_success(self, client, monkeypatch):
        from application.cdn_uploader import CdnUploader
        monkeypatch.setattr(
            CdnUploader,
            "upload_image",
            lambda self, image_bytes, filename=None, content_type=None, path_folder="face", timeout=15.0: "/face/mock_result.jpg"
        )

        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        with open(file_path, "rb") as f:
            response = client.post(
                "/compress",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
                data={
                    "maxWidth": "1000",
                    "maxHeight": "1000",
                    "detectFace": "true",
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["file_url"] == "/face/mock_result.jpg"

    def test_compress_cdn_upload_failure(self, client, monkeypatch):
        from application.cdn_uploader import CdnUploader
        monkeypatch.setattr(
            CdnUploader,
            "upload_image",
            lambda self, image_bytes, filename=None, content_type=None, path_folder="face", timeout=15.0: "cdn_upload failed"
        )

        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        with open(file_path, "rb") as f:
            response = client.post(
                "/compress",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
                data={
                    "maxWidth": "1000",
                    "maxHeight": "1000",
                    "detectFace": "true",
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["file_url"] == "cdn_upload failed"

    def test_compress_with_prefix_form_param(self, client, monkeypatch):
        from application.cdn_uploader import CdnUploader
        captured_kwargs = {}

        def mock_upload(self, *args, **kwargs):
            captured_kwargs.update(kwargs)
            return "/face/prefix_uploaded.jpg"

        monkeypatch.setattr(CdnUploader, "upload_image", mock_upload)

        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        with open(file_path, "rb") as f:
            response = client.post(
                "/compress",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
                data={
                    "maxWidth": "1000",
                    "maxHeight": "1000",
                    "detectFace": "true",
                    "prefix": "my_prefix",
                },
            )
        assert response.status_code == 200
        assert captured_kwargs.get("prefix") == "my_prefix"
        data = response.json()
        assert data["valid"] is True
        assert data["file_url"] == "/face/prefix_uploaded.jpg"

    def test_compress_with_quoted_prefix_form_param(self, client, monkeypatch):
        from application.cdn_uploader import CdnUploader
        captured_kwargs = {}

        def mock_upload(self, *args, **kwargs):
            captured_kwargs.update(kwargs)
            return "/face/quoted_prefix_uploaded.jpg"

        monkeypatch.setattr(CdnUploader, "upload_image", mock_upload)

        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        with open(file_path, "rb") as f:
            response = client.post(
                "/compress",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
                data={
                    "maxWidth": "1000",
                    "maxHeight": "1000",
                    "detectFace": "true",
                    "prefix": '"string"',
                },
            )
        assert response.status_code == 200
        assert captured_kwargs.get("prefix") == '"string"'
        data = response.json()
        assert data["valid"] is True
        assert data["file_url"] == "/face/quoted_prefix_uploaded.jpg"

    def test_compress_with_empty_prefix_form_param(self, client, monkeypatch):
        from application.cdn_uploader import CdnUploader
        captured_kwargs = {}

        def mock_upload(self, *args, **kwargs):
            captured_kwargs.update(kwargs)
            return "/face/empty_prefix.jpg"

        monkeypatch.setattr(CdnUploader, "upload_image", mock_upload)

        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        with open(file_path, "rb") as f:
            response = client.post(
                "/compress",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
                data={
                    "maxWidth": "1000",
                    "maxHeight": "1000",
                    "detectFace": "true",
                    "prefix": "",
                },
            )
        assert response.status_code == 200
        assert captured_kwargs.get("prefix") == ""
        data = response.json()
        assert data["valid"] is True

    def test_compress_with_form_prefix_fallback(self, client, monkeypatch):
        from application.cdn_uploader import CdnUploader
        captured_kwargs = {}

        def mock_upload(self, *args, **kwargs):
            captured_kwargs.update(kwargs)
            return "/face/form_prefix.jpg"

        monkeypatch.setattr(CdnUploader, "upload_image", mock_upload)

        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        with open(file_path, "rb") as f:
            response = client.post(
                "/compress",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
                data={
                    "maxWidth": "1000",
                    "maxHeight": "1000",
                    "detectFace": "true",
                    "prefix": "form_specified_prefix",
                },
            )
        assert response.status_code == 200
        assert captured_kwargs.get("prefix") == "form_specified_prefix"
        data = response.json()
        assert data["valid"] is True

    def test_compress_with_preset_from_form_prefix(self, client, monkeypatch):
        from application.cdn_uploader import CdnUploader
        monkeypatch.setattr(
            CdnUploader,
            "upload_image",
            lambda self, *args, **kwargs: "/face/preset_abc.jpg"
        )

        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        with open(file_path, "rb") as f:
            # abc preset has maxWidth=400, maxHeight=960, detectFace=true
            # We provide only prefix in form data!
            response = client.post(
                "/compress",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
                data={"prefix": "abc"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["image"]["width"] == 400
        assert data["image"]["height"] == 400
        assert data["compression"]["qualityCompression"] == 85
        assert len(data["faces"]) == 1

    def test_compress_with_preset_override_by_form_field(self, client, monkeypatch):
        from application.cdn_uploader import CdnUploader
        monkeypatch.setattr(
            CdnUploader,
            "upload_image",
            lambda self, *args, **kwargs: "/face/preset_xyz.jpg"
        )

        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        with open(file_path, "rb") as f:
            # xyz preset sets qualityCompression=75, maxWidth=920, maxHeight=1280
            # User overrides qualityCompression to 90
            response = client.post(
                "/compress",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
                data={"prefix": "xyz", "qualityCompression": "90"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["compression"]["qualityCompression"] == 90
        # Image is 512x512, which fits in 920x1280
        assert data["image"]["width"] == 512
        assert data["image"]["height"] == 512

    def test_compress_without_preset_and_no_body_params_succeeds_as_is(self, client, monkeypatch):
        from application.cdn_uploader import CdnUploader
        captured_kwargs = {}

        def mock_upload(self, *args, **kwargs):
            captured_kwargs.update(kwargs)
            return "/smartimage/no_params.jpg"

        monkeypatch.setattr(CdnUploader, "upload_image", mock_upload)

        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        with open(file_path, "rb") as f:
            # Non-existent prefix and no form fields at all (only imageFile)
            response = client.post(
                "/compress",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        # Original single_face.jpg is 512x512
        assert data["image"]["width"] == 512
        assert data["image"]["height"] == 512
        # Default quality is 100
        assert data["compression"]["qualityCompression"] == 100
        assert data["compression"]["pixelCompression"] == 100
        assert data["compression"]["cropImage"] is False
        # detectFace defaulted to False -> faces list is empty
        assert data["faces"] == []
        assert captured_kwargs["path_folder"] == "smartimage"

    def test_compress_confidence_threshold_filtering(self, client, monkeypatch):
        from application.cdn_uploader import CdnUploader
        monkeypatch.setattr(
            CdnUploader,
            "upload_image",
            lambda self, *args, **kwargs: "/face/confidence_test.jpg"
        )

        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        # single_face.jpg detection confidence is ~0.909
        # Case 1: Threshold set to 0.95 (above 0.909) -> face is filtered out -> len(faces) == 0
        with open(file_path, "rb") as f:
            response = client.post(
                "/compress",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
                data={
                    "maxWidth": "1000",
                    "maxHeight": "1000",
                    "detectFace": "true",
                    "confidence": "0.95",
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert len(data["faces"]) == 0

        # Case 2: Threshold set to 0.85 (below 0.909) -> face is kept -> len(faces) == 1
        with open(file_path, "rb") as f:
            response = client.post(
                "/compress",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
                data={
                    "maxWidth": "1000",
                    "maxHeight": "1000",
                    "detectFace": "true",
                    "confidence": "0.85",
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert len(data["faces"]) == 1
        assert data["faces"][0]["confidence"] >= 0.85

    def test_compress_confidence_from_preset(self, client, monkeypatch):
        from application.cdn_uploader import CdnUploader
        monkeypatch.setattr(
            CdnUploader,
            "upload_image",
            lambda self, *args, **kwargs: "/face/confidence_preset.jpg"
        )

        # abc preset has confidence=0.8
        # single_face.jpg has ~0.909 confidence -> kept
        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        with open(file_path, "rb") as f:
            response = client.post(
                "/compress",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
                data={"prefix": "abc"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert len(data["faces"]) == 1

        # Now override with confidence=0.99 via form parameter -> filtered out
        with open(file_path, "rb") as f:
            response = client.post(
                "/compress",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
                data={"prefix": "abc", "confidence": "0.99"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert len(data["faces"]) == 0

    def test_validate_with_confidence_threshold(self, client):
        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        # single_face confidence is ~0.909. When confidence=0.95 -> no face passes -> NO_FACE
        with open(file_path, "rb") as f:
            response = client.post(
                "/validate",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
                data={
                    "maxWidth": "1000",
                    "maxHeight": "1000",
                    "detectFace": "true",
                    "confidence": "0.95",
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["reason"] == "NO_FACE"
        assert len(data["faces"]) == 0

    def test_compress_with_max_file_size_threshold(self, client, monkeypatch):
        from application.cdn_uploader import CdnUploader
        monkeypatch.setattr(
            CdnUploader,
            "upload_image",
            lambda self, *args, **kwargs: "/face/size_test.jpg"
        )

        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        with open(file_path, "rb") as f:
            # First request without maxFileSize: single_face.jpg at quality 85 is ~28-40KB
            response = client.post(
                "/compress",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
                data={
                    "maxWidth": "800",
                    "maxHeight": "800",
                    "detectFace": "true",
                    "qualityCompression": "85",
                },
            )
        assert response.status_code == 200
        initial_data = response.json()
        initial_size = initial_data["image"]["outputSizeBytes"]

        # Now enforce a compressFileSize strictly lower than initial_size (e.g. 15000 bytes)
        target_size = 15000
        assert initial_size > target_size

        with open(file_path, "rb") as f:
            response = client.post(
                "/compress",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
                data={
                    "maxWidth": "800",
                    "maxHeight": "800",
                    "detectFace": "true",
                    "qualityCompression": "85",
                    "compressFileSize": str(target_size),
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["image"]["outputSizeBytes"] <= target_size
        assert data["compression"]["compressFileSize"] == target_size
        # Bounding box coordinates remain valid
        assert len(data["faces"]) == 1
        bbox = data["faces"][0]["boundingBox"]
        assert bbox["x"] >= 0 and bbox["y"] >= 0
        assert bbox["width"] <= data["image"]["width"]
        assert bbox["height"] <= data["image"]["height"]

    def test_compress_compress_file_size_from_preset(self, client, monkeypatch):
        from application.cdn_uploader import CdnUploader
        monkeypatch.setattr(
            CdnUploader,
            "upload_image",
            lambda self, *args, **kwargs: "/face/preset_size.jpg"
        )

        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        with open(file_path, "rb") as f:
            # abc preset has compressFileSize=51200
            response = client.post(
                "/compress",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
                data={"prefix": "abc"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["image"]["outputSizeBytes"] <= 51200
        assert data["compression"]["compressFileSize"] == 51200

    def test_compress_with_preset_and_null_or_empty_form_fields(self, client, monkeypatch):
        from application.cdn_uploader import CdnUploader
        monkeypatch.setattr(
            CdnUploader,
            "upload_image",
            lambda self, *args, **kwargs: "/face/null_override.jpg"
        )

        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        with open(file_path, "rb") as f:
            # Caller sends form data with "null", "None", and "" strings
            response = client.post(
                "/compress",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
                data={
                    "prefix": "ipsotek",
                    "maxWidth": "null",
                    "maxHeight": "",
                    "detectFace": "None",
                    "qualityCompression": "null",
                    "pixelCompression": "",
                    "cropImage": "null",
                    "confidence": "null",
                    "compressFileSize": "null",
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        # ipsotek preset has cropImage=true, compressFileSize=10000
        assert data["crop"]["applied"] is True
        assert data["image"]["outputSizeBytes"] <= 10000
        assert data["compression"]["compressFileSize"] == 10000
        assert len(data["faces"]) == 1

    def test_compress_case_insensitive_parameters(self, client, monkeypatch):
        from application.cdn_uploader import CdnUploader
        monkeypatch.setattr(
            CdnUploader,
            "upload_image",
            lambda self, *args, **kwargs: "/face/caps_test.jpg"
        )

        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        with open(file_path, "rb") as f:
            # Caller sends uppercase & mixed case keys including ImageFile, MAXWIDTH, MaxHeight, etc.
            response = client.post(
                "/compress",
                files={"ImageFile": ("single_face.jpg", f, "image/jpeg")},
                data={
                    "MAXWIDTH": "600",
                    "MaxHeight": "600",
                    "DETECTFACE": "TRUE",
                    "QualityCompression": "80",
                    "compressfilesize": "15000",
                    "CropImage": "true",
                    "Prefix": "ipsotek",
                    "FileName": "CapsFace",
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["image"]["width"] <= 600
        assert data["image"]["height"] <= 600
        assert data["compression"]["compressFileSize"] == 15000

    def test_validate_case_insensitive_imagefile(self, client):
        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        with open(file_path, "rb") as f:
            response = client.post(
                "/validate",
                files={"IMAGEFILE": ("single_face.jpg", f, "image/jpeg")},
                data={
                    "MAXWIDTH": "1500",
                    "MAXHEIGHT": "1500",
                    "DETECTFACE": "true",
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True


    def test_compress_max_file_size_backward_compatibility(self, client, monkeypatch):
        from application.cdn_uploader import CdnUploader
        monkeypatch.setattr(
            CdnUploader,
            "upload_image",
            lambda self, *args, **kwargs: "/face/legacy_param.jpg"
        )

        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        with open(file_path, "rb") as f:
            response = client.post(
                "/compress",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
                data={
                    "maxWidth": "800",
                    "maxHeight": "800",
                    "detectFace": "true",
                    "qualityCompression": "85",
                    "maxFileSize": "15000",
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["image"]["outputSizeBytes"] <= 15000
        assert data["compression"]["compressFileSize"] == 15000

    def test_validate_case_insensitive_parameters(self, client):
        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        with open(file_path, "rb") as f:
            response = client.post(
                "/validate",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
                data={
                    "MAXWIDTH": "1500",
                    "MaxHeight": "1500",
                    "DETECTFACE": "true",
                    "CONFIDENCE": "0.8",
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert len(data["faces"]) == 1

    def test_compress_custom_file_name_and_path(self, client, monkeypatch):
        import uuid
        from application.cdn_uploader import CdnUploader
        captured_upload = {}

        def mock_upload(self, **kwargs):
            captured_upload.update(kwargs)
            return f"/{kwargs.get('path_folder')}/{kwargs.get('filename')}"

        monkeypatch.setattr(CdnUploader, "upload_image", mock_upload)

        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        with open(file_path, "rb") as f:
            response = client.post(
                "/compress",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
                data={
                    "maxWidth": "800",
                    "maxHeight": "800",
                    "detectFace": "true",
                    "fileName": "custom_avatar",
                    "path": "users/profiles",
                },
            )
        assert response.status_code == 200
        assert captured_upload["path_folder"] == "users/profiles"
        assert captured_upload["filename"] == "custom_avatar.jpeg"

    def test_compress_defaults_to_random_uuidv4_filename_and_smartimage_path(self, client, monkeypatch):
        import uuid
        from application.cdn_uploader import CdnUploader
        captured_upload = {}

        def mock_upload(self, **kwargs):
            captured_upload.update(kwargs)
            return f"/{kwargs.get('path_folder')}/{kwargs.get('filename')}"

        monkeypatch.setattr(CdnUploader, "upload_image", mock_upload)

        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        with open(file_path, "rb") as f:
            response = client.post(
                "/compress",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
                data={
                    "maxWidth": "800",
                    "maxHeight": "800",
                    "detectFace": "true",
                },
            )
        assert response.status_code == 200
        # Default path must be 'smartimage'
        assert captured_upload["path_folder"] == "smartimage"
        # Default fileName must be a valid UUIDv4 with format extension
        file_stem = os.path.splitext(captured_upload["filename"])[0]
        parsed_uuid = uuid.UUID(file_stem, version=4)
        assert str(parsed_uuid) == file_stem

    def test_compress_zero_values_treated_as_none(self, client):
        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        with open(file_path, "rb") as f:
            response = client.post(
                "/compress",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
                data={
                    "maxWidth": "0",
                    "maxHeight": "0",
                    "detectFace": "true",
                    "cropImage": "false",
                    "qualityCompression": "0",
                    "pixelCompression": "0",
                    "confidence": "0",
                    "compressFileSize": "0",
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        # Since maxWidth=0 and maxHeight=0 are treated as None, image retains original dimensions 512x512
        assert data["image"]["width"] == 512
        assert data["image"]["height"] == 512
        # qualityCompression=0 -> None -> default 100
        assert data["compression"]["qualityCompression"] == 100
        # pixelCompression=0 -> None -> default 100
        assert data["compression"]["pixelCompression"] == 100
        # compressFileSize=0 -> None
        assert data["compression"]["compressFileSize"] is None

    def test_compress_with_prefix_and_filename_prepends_prefix(self, client, monkeypatch):
        from application.cdn_uploader import CdnUploader
        captured_upload = {}

        def mock_upload(self, **kwargs):
            captured_upload.update(kwargs)
            return f"/{kwargs.get('path_folder')}/{kwargs.get('filename')}"

        monkeypatch.setattr(CdnUploader, "upload_image", mock_upload)

        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        with open(file_path, "rb") as f:
            response = client.post(
                "/compress",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
                data={
                    "prefix": "ipsotek",
                    "fileName": "FaceBoss",
                },
            )
        assert response.status_code == 200
        assert captured_upload["filename"] == "ipsotek_FaceBoss.jpeg"

    def test_compress_with_prefix_and_default_filename_prepends_prefix(self, client, monkeypatch):
        import uuid
        from application.cdn_uploader import CdnUploader
        captured_upload = {}

        def mock_upload(self, **kwargs):
            captured_upload.update(kwargs)
            return f"/{kwargs.get('path_folder')}/{kwargs.get('filename')}"

        monkeypatch.setattr(CdnUploader, "upload_image", mock_upload)

        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        with open(file_path, "rb") as f:
            # Pass prefix without any fileName
            response = client.post(
                "/compress",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
                data={
                    "prefix": "ipsotek",
                },
            )
        assert response.status_code == 200
        filename = captured_upload["filename"]
        assert filename.startswith("ipsotek_")
        assert filename.endswith(".jpeg")
        # Extract UUID part
        uuid_part = filename[len("ipsotek_"):-len(".jpeg")]
        parsed_uuid = uuid.UUID(uuid_part, version=4)
        assert str(parsed_uuid) == uuid_part

    def test_compress_audit_filenames(self, client, monkeypatch):
        from application.cdn_uploader import CdnUploader

        def mock_upload(self, **kwargs):
            self.last_upload_metadata = {
                "intended_file_name": kwargs.get("filename"),
                "response_file_name": "uuid-1234-5678.jpeg",
                "file_url": "/smartimage/uuid-1234-5678.jpeg",
            }
            return "/smartimage/uuid-1234-5678.jpeg"

        monkeypatch.setattr(CdnUploader, "upload_image", mock_upload)

        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        with open(file_path, "rb") as f:
            response = client.post(
                "/compress",
                files={"imageFile": ("single_face.jpg", f, "image/jpeg")},
                data={
                    "prefix": "ipsotek",
                    "fileName": "ridwan",
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["file_url"] == "/smartimage/uuid-1234-5678.jpeg"
        assert data["intended_file_name"] == "ipsotek_ridwan.jpeg"
        assert data["response_file_name"] == "uuid-1234-5678.jpeg"

    def test_webp_upload_converted_to_jpeg(self, client, monkeypatch):
        import base64
        import cv2
        from application.cdn_uploader import CdnUploader

        monkeypatch.setattr(
            CdnUploader,
            "upload_image",
            lambda self, **kwargs: f"/{kwargs.get('path_folder')}/{kwargs.get('filename')}"
        )

        # Encode single_face.jpg into in-memory .webp bytes
        file_path = os.path.join(FIXTURES_DIR, "single_face.jpg")
        img = cv2.imread(file_path)
        success, webp_buf = cv2.imencode(".webp", img, [cv2.IMWRITE_WEBP_QUALITY, 90])
        assert success
        webp_bytes = webp_buf.tobytes()

        # 1. Test /validate accepts .webp
        res_val = client.post(
            "/validate",
            files={"imageFile": ("single_face.webp", webp_bytes, "image/webp")},
            data={"maxWidth": "1500", "maxHeight": "1500", "detectFace": "true"},
        )
        assert res_val.status_code == 200
        val_data = res_val.json()
        assert val_data["valid"] is True
        assert val_data["reason"] == "VALID"
        assert len(val_data["faces"]) == 1

        # 2. Test /compress accepts .webp and converts output to jpeg
        res_comp = client.post(
            "/compress",
            files={"imageFile": ("single_face.webp", webp_bytes, "image/webp")},
            data={"detectFace": "true", "qualityCompression": "85"},
        )
        assert res_comp.status_code == 200
        comp_data = res_comp.json()
        assert comp_data["valid"] is True
        assert comp_data["image"]["originalFormat"] == "webp"
        assert comp_data["image"]["outputFormat"] == "jpeg"
        assert comp_data["contentType"] == "image/jpeg"
        # Verify returned base64 is JPEG (magic bytes \xff\xd8\xff)
        decoded_out = base64.b64decode(comp_data["imageData"])
        assert decoded_out[:3] == b"\xff\xd8\xff"







