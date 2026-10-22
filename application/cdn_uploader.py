import json
import logging
import os
from typing import Optional
import httpx
from api.paths import get_asset_path

logger = logging.getLogger(__name__)


class CdnUploader:
    """
    Handles uploading images to the CDN defined in config.json.
    """

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or get_asset_path("config.json")
        self._cached_cdn_url: Optional[str] = None
        self.last_upload_metadata: dict = {}

    def get_cdn_url(self) -> Optional[str]:
        """
        Reads cdnURL from config.json (checks relative or asset path, or next to exe).
        """
        # Try configured/resolved path first
        candidate_paths = [
            self.config_path,
            os.path.join(os.getcwd(), "config.json"),
            get_asset_path("config.json"),
        ]
        
        for path in candidate_paths:
            if path and os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        url = data.get("cdnURL")
                        if url:
                            return url.strip()
                except Exception as e:
                    logger.warning(f"Failed to read config from {path}: {e}")
        return None

    def upload_image(
        self,
        image_bytes: bytes,
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
        path_folder: str = "smartimage",
        timeout: float = 15.0,
        prefix: Optional[str] = None,
        onlyupload: Optional[bool] = None,
    ) -> str:
        """
        Uploads an image to the CDN service with multipart form-data:
        - file_name: string filename
        - path: folder path (e.g. 'smartimage')
        - file: binary file payload
        - (optional) URL query params: prefix=<prefix>&onlyupload=true
        - (optional) onlyupload: "true" parameter in form-data and query string
        
        Returns:
            The uploaded file_url (e.g. '/face/xyz.png') on success,
            or 'cdn_upload failed' on failure.
        """
        cdn_url = self.get_cdn_url()
        if not cdn_url:
            logger.warning("CDN URL not found or not configured in config.json.")
            return "cdn_upload failed"

        # Prepare filename and content type
        file_name = filename or "image.jpg"
        mime_type = content_type or "image/jpeg"

        # Check if prefix is provided and not an empty string
        clean_prefix = prefix.strip() if isinstance(prefix, str) else ""
        has_prefix = bool(clean_prefix and clean_prefix.strip("'\"") != "")

        if onlyupload is None:
            effective_onlyupload = has_prefix
        else:
            effective_onlyupload = bool(onlyupload)

        data = {
            "file_name": file_name,
            "path": path_folder,
        }

        # Build URL with query params
        url_obj = httpx.URL(cdn_url)
        query_params = dict(url_obj.params)

        if effective_onlyupload:
            query_params["onlyupload"] = "true"
            data["onlyupload"] = "true"

        target_url = str(url_obj.copy_with(params=query_params)) if query_params else cdn_url

        try:
            logger.info(
                f"Uploading image to CDN: target_url={target_url}, prefix={prefix}, onlyupload={effective_onlyupload}"
            )
            with httpx.Client(timeout=timeout) as client:
                files = {
                    "file": (file_name, image_bytes, mime_type)
                }
                
                response = client.post(target_url, data=data, files=files)
                
                if response.status_code == 200:
                    res_json = response.json()
                    # Expect collection.file_url or file_url
                    file_url = None
                    cdn_response_filename = None
                    if isinstance(res_json, dict):
                        collection = res_json.get("collection")
                        if isinstance(collection, dict):
                            file_url = collection.get("file_url")
                            cdn_response_filename = collection.get("file_name")
                        elif "file_url" in res_json:
                            file_url = res_json["file_url"]
                            cdn_response_filename = res_json.get("file_name")

                    self.last_upload_metadata = {
                        "intended_file_name": file_name,
                        "response_file_name": cdn_response_filename or (file_url.split("/")[-1] if file_url else None),
                        "file_url": file_url,
                    }

                    if file_url:
                        return str(file_url)
                    else:
                        logger.warning(f"CDN response did not contain file_url: {response.text}")
                        return "cdn_upload failed"
                else:
                    logger.warning(f"CDN upload failed with status {response.status_code}: {response.text}")
                    self.last_upload_metadata = {
                        "intended_file_name": file_name,
                        "response_file_name": None,
                        "file_url": "cdn_upload failed",
                    }
                    return "cdn_upload failed"
        except Exception as e:
            logger.error(f"Exception during CDN upload: {e}")
            self.last_upload_metadata = {
                "intended_file_name": file_name,
                "response_file_name": None,
                "file_url": "cdn_upload failed",
            }
            return "cdn_upload failed"

