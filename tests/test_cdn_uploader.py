import json
import pytest
import httpx
from application.cdn_uploader import CdnUploader


class TestCdnUploader:
    def test_upload_image_with_prefix(self, monkeypatch, tmp_path):
        # Setup config
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"cdnURL": "https://cdn.example.com/api/upload"}))

        uploader = CdnUploader(config_path=str(config_file))
        captured = {}

        def mock_post(client, url, data=None, files=None, **kwargs):
            captured["url"] = str(url)
            captured["data"] = data
            captured["files"] = files
            return httpx.Response(200, json={"file_url": "/face/result123.jpg"})

        monkeypatch.setattr(httpx.Client, "post", mock_post)

        result = uploader.upload_image(
            image_bytes=b"fake-bytes",
            filename="test.jpg",
            content_type="image/jpeg",
            path_folder="face",
            prefix="avatar_prefix",
        )

        assert result == "/face/result123.jpg"
        assert "prefix" not in captured["url"]
        assert "prefix" not in captured["data"]
        assert "onlyupload=true" in captured["url"]
        assert captured["data"]["onlyupload"] == "true"
        assert captured["data"]["file_name"] == "test.jpg"
        assert captured["data"]["path"] == "face"

    def test_upload_image_with_quoted_prefix(self, monkeypatch, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"cdnURL": "https://cdn.example.com/api/upload"}))

        uploader = CdnUploader(config_path=str(config_file))
        captured = {}

        def mock_post(client, url, data=None, files=None, **kwargs):
            captured["url"] = str(url)
            captured["data"] = data
            return httpx.Response(200, json={"collection": {"file_url": "/face/collection_url.jpg"}})

        monkeypatch.setattr(httpx.Client, "post", mock_post)

        result = uploader.upload_image(
            image_bytes=b"fake-bytes",
            filename="test.png",
            content_type="image/png",
            prefix='"my_string"',
        )

        assert result == "/face/collection_url.jpg"
        assert "prefix" not in captured["url"]
        assert "prefix" not in captured["data"]
        assert "onlyupload=true" in captured["url"]
        assert captured["data"]["onlyupload"] == "true"

    def test_upload_image_without_prefix(self, monkeypatch, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"cdnURL": "https://cdn.example.com/api/upload"}))

        uploader = CdnUploader(config_path=str(config_file))
        captured = {}

        def mock_post(client, url, data=None, files=None, **kwargs):
            captured["url"] = str(url)
            captured["data"] = data
            return httpx.Response(200, json={"file_url": "/face/no_prefix.jpg"})

        monkeypatch.setattr(httpx.Client, "post", mock_post)

        result = uploader.upload_image(
            image_bytes=b"fake-bytes",
            filename="test.jpg",
            prefix=None,
        )

        assert result == "/face/no_prefix.jpg"
        assert "prefix" not in captured["url"]
        assert "onlyupload" not in captured["url"]
        assert "onlyupload" not in captured["data"]

    def test_upload_image_with_empty_prefix_string(self, monkeypatch, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"cdnURL": "https://cdn.example.com/api/upload"}))

        uploader = CdnUploader(config_path=str(config_file))
        captured = {}

        def mock_post(client, url, data=None, files=None, **kwargs):
            captured["url"] = str(url)
            captured["data"] = data
            return httpx.Response(200, json={"file_url": "/face/empty.jpg"})

        monkeypatch.setattr(httpx.Client, "post", mock_post)

        # Empty string
        uploader.upload_image(image_bytes=b"fake-bytes", prefix="")
        assert "prefix" not in captured["url"]
        assert "onlyupload" not in captured["url"]
        assert "onlyupload" not in captured["data"]

        # Whitespace
        uploader.upload_image(image_bytes=b"fake-bytes", prefix="   ")
        assert "prefix" not in captured["url"]
        assert "onlyupload" not in captured["url"]
        assert "onlyupload" not in captured["data"]

        # Empty quotes '""'
        uploader.upload_image(image_bytes=b"fake-bytes", prefix='""')
        assert "prefix" not in captured["url"]
        assert "onlyupload" not in captured["url"]
        assert "onlyupload" not in captured["data"]

    def test_upload_image_explicit_onlyupload(self, monkeypatch, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"cdnURL": "https://cdn.example.com/api/upload"}))

        uploader = CdnUploader(config_path=str(config_file))
        captured = {}

        def mock_post(client, url, data=None, files=None, **kwargs):
            captured["url"] = str(url)
            captured["data"] = data
            return httpx.Response(200, json={"file_url": "/face/onlyupload.jpg"})

        monkeypatch.setattr(httpx.Client, "post", mock_post)

        # Explicitly passing onlyupload=True without prefix
        uploader.upload_image(image_bytes=b"fake-bytes", onlyupload=True)
        assert "onlyupload=true" in captured["url"]
        assert captured["data"]["onlyupload"] == "true"
