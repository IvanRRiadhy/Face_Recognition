from typing import Any, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from models.responses import CompressionResponse
from application.compression_service import CompressionService
from api.paths import get_preset_for_prefix

router = APIRouter(tags=["Compression"])


def get_compression_service(request: Request) -> CompressionService:
    service = getattr(request.app.state, "compression_service", None)
    if not service:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Compression service is not initialized."
        )
    return service


@router.post(
    "/compress",
    response_model=CompressionResponse,
    summary="Validate, detect face, crop, resize and compress image",
    description="""
Process an uploaded image (`.png`, `.jpg`, `.jpeg`, `.webp`) with optional face detection, face-aware cropping, dimension reduction, and lossy/lossless quality compression:

### Parameters:
- **imageFile** (*required*): Multipart binary image.
- **maxWidth** (*optional, >0*): Maximum allowed width in pixels. If omitted or null, no width-based resize is performed.
- **maxHeight** (*optional, >0*): Maximum allowed height in pixels. If omitted or null, no height-based resize is performed.
- **detectFace** (*optional, default false*): Whether to run YuNet face detection (required `true` if `cropImage=true`).
- **qualityCompression** (*default 100 or preset, 1-100*): Encoding quality for JPEG (or lossless tuning for PNG). 100 = highest quality (no lossy compression).
- **pixelCompression** (*default 100 or preset, 1-100*): Percentage of original image dimensions to retain (e.g. 50 = 50% width and 50% height).
- **cropImage** (*default false or preset*): Whether to crop around a single detected face with margin. Requires `detectFace=true`.
- **confidence** (*optional, default or preset, 0.0-1.0*): Minimum face detection confidence threshold. Detected faces with score below this will be ignored.
- **compressFileSize** (*optional, default or preset, bytes*): Maximum desired output file size in bytes. Progressively compresses to fit.
- **fileName** (*optional, defaults to random UUIDv4*): Target filename for CDN storage. If omitted or null, a random UUIDv4 is generated.
- **path** (*optional, default "smartimage"*): Target folder path for CDN storage. If omitted or null, defaults to "smartimage".
- **prefix** (*optional form body parameter, string*): Optional prefix string attached to CDN upload URL query and sets `onlyupload=true` when provided and non-empty. Also looks up default parameter presets configured in `config.json`.

### Response:
Returns metadata about the original and processed image, face coordinates in both original and final coordinate spaces, crop metadata, and the **Base64-encoded processed image**.
    """,
    responses={
        200: {
            "description": "Compression response (whether processing succeeded or encountered validation reasons)",
        },
        400: {"description": "Invalid input parameters"},
        422: {"description": "Unprocessable Entity (parameter out of range or missing)"}
    }
)
async def compress_image(
    request: Request,
    imageFile: Optional[UploadFile] = File(None, description="Uploaded image file (.png, .jpg, .jpeg)"),
    maxWidth: Optional[Any] = Form(None, description="Maximum allowed image width in pixels (or null to use preset)"),
    maxHeight: Optional[Any] = Form(None, description="Maximum allowed image height in pixels (or null to use preset)"),
    detectFace: Optional[Any] = Form(None, description="Enable YuNet face detection (or null to use preset)"),
    qualityCompression: Optional[Any] = Form(None, description="Quality compression percentage (1-100) (or null to use preset)"),
    pixelCompression: Optional[Any] = Form(None, description="Pixel dimension retention percentage (1-100) (or null to use preset)"),
    cropImage: Optional[Any] = Form(None, description="Enable face-aware cropping (or null to use preset)"),
    confidence: Optional[Any] = Form(None, description="Minimum face detection confidence threshold (0.0 to 1.0) (or null to use preset)"),
    compressFileSize: Optional[Any] = Form(None, description="Maximum desired output file size in bytes (or null to use preset)"),
    maxFileSize: Optional[Any] = Form(None, description="Deprecated alias for compressFileSize"),
    fileName: Optional[Any] = Form(None, description="Optional target filename for CDN upload (defaults to UUIDv4)"),
    path: Optional[Any] = Form(None, description="Optional target folder path for CDN upload (defaults to 'smartimage')"),
    prefix: Optional[str] = Form(None, description="Optional prefix string for presets and CDN upload"),
    compression_service: CompressionService = Depends(get_compression_service),
) -> CompressionResponse:
    # 1. Resolve form data (case-insensitive key mapping)
    form_data = {}
    try:
        raw_form = await request.form()
        for k, v in raw_form.items():
            form_data[k.lower()] = v
    except Exception:
        pass

    def _get_form_field(std_name: str, direct_val: Any) -> Any:
        if direct_val is not None:
            return direct_val
        return form_data.get(std_name.lower())

    # Resolve image file case-insensitively (e.g. imageFile, ImageFile, IMAGEFILE)
    effective_image_file = _get_form_field("imageFile", imageFile)

    # Resolve prefix from multipart form body (direct parameter or case-insensitive fallback)
    raw_prefix = _get_form_field("prefix", prefix)
    effective_prefix = str(raw_prefix) if raw_prefix is not None else None

    # 2. Look up preset from config.json if prefix exists
    preset = get_preset_for_prefix(effective_prefix)

    # Helper functions to treat None, "", "null", and "none" as None
    def _clean_val(val):
        if val is None:
            return None
        if isinstance(val, str):
            s = val.strip().lower()
            if s in ("", "null", "none"):
                return None
        return val

    def _clean_int(val, field_name: str, min_val: Optional[int] = None, max_val: Optional[int] = None, zero_as_none: bool = False) -> Optional[int]:
        cleaned = _clean_val(val)
        if cleaned is None:
            return None
        try:
            num = int(cleaned)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=[{
                    "loc": ["body", field_name],
                    "msg": "value is not a valid integer",
                    "type": "type_error.integer",
                }]
            )
        if zero_as_none and num == 0:
            return None
        if min_val is not None and num < min_val:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=[{
                    "loc": ["body", field_name],
                    "msg": f"ensure this value is greater than or equal to {min_val}",
                    "type": "value_error.number.not_ge",
                }]
            )
        if max_val is not None and num > max_val:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=[{
                    "loc": ["body", field_name],
                    "msg": f"ensure this value is less than or equal to {max_val}",
                    "type": "value_error.number.not_le",
                }]
            )
        return num

    def _clean_float(val, field_name: str, min_val: Optional[float] = None, max_val: Optional[float] = None, zero_as_none: bool = False) -> Optional[float]:
        cleaned = _clean_val(val)
        if cleaned is None:
            return None
        try:
            num = float(cleaned)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=[{
                    "loc": ["body", field_name],
                    "msg": "value is not a valid float",
                    "type": "type_error.float",
                }]
            )
        if zero_as_none and num == 0.0:
            return None
        if min_val is not None and num < min_val:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=[{
                    "loc": ["body", field_name],
                    "msg": f"ensure this value is greater than or equal to {min_val}",
                    "type": "value_error.number.not_ge",
                }]
            )
        if max_val is not None and num > max_val:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=[{
                    "loc": ["body", field_name],
                    "msg": f"ensure this value is less than or equal to {max_val}",
                    "type": "value_error.number.not_le",
                }]
            )
        return num

    def _clean_bool(val) -> Optional[bool]:
        cleaned = _clean_val(val)
        if cleaned is None:
            return None
        if isinstance(cleaned, bool):
            return cleaned
        s = str(cleaned).strip().lower()
        if s in ("true", "1", "yes", "t", "y"):
            return True
        if s in ("false", "0", "no", "f", "n"):
            return False
        return None

    # Parse and normalize request body values with case-insensitive fallback (0 is treated as None/null)
    req_max_width = _clean_int(_get_form_field("maxWidth", maxWidth), "maxWidth", zero_as_none=True)
    req_max_height = _clean_int(_get_form_field("maxHeight", maxHeight), "maxHeight", zero_as_none=True)
    req_detect_face = _clean_bool(_get_form_field("detectFace", detectFace))
    req_quality = _clean_int(_get_form_field("qualityCompression", qualityCompression), "qualityCompression", min_val=1, max_val=100, zero_as_none=True)
    req_pixel = _clean_int(_get_form_field("pixelCompression", pixelCompression), "pixelCompression", min_val=1, max_val=100, zero_as_none=True)
    req_crop = _clean_bool(_get_form_field("cropImage", cropImage))
    req_confidence = _clean_float(_get_form_field("confidence", confidence), "confidence", min_val=0.0, max_val=1.0, zero_as_none=True)
    raw_compress_file_size = _get_form_field("compressFileSize", compressFileSize)
    if raw_compress_file_size is None:
        raw_compress_file_size = _get_form_field("maxFileSize", maxFileSize)
    req_compress_file_size = _clean_int(raw_compress_file_size, "compressFileSize", min_val=1, zero_as_none=True)

    # 3. Apply preset values or defaults for missing/null parameters
    final_max_width = req_max_width if req_max_width is not None else preset.get("maxWidth")
    final_max_height = req_max_height if req_max_height is not None else preset.get("maxHeight")
    
    preset_detect_face = preset.get("detectFace")
    final_detect_face = (
        req_detect_face
        if req_detect_face is not None
        else (preset_detect_face if preset_detect_face is not None else False)
    )

    final_quality = (
        req_quality
        if req_quality is not None
        else preset.get("qualityCompression", 100)
    )
    final_pixel = (
        req_pixel
        if req_pixel is not None
        else preset.get("pixelCompression", 100)
    )
    final_crop = (
        req_crop
        if req_crop is not None
        else preset.get("cropImage", False)
    )
    final_confidence = (
        req_confidence
        if req_confidence is not None
        else preset.get("confidence")
    )
    preset_compress_file_size = preset.get("compressFileSize")
    if preset_compress_file_size is None:
        preset_compress_file_size = preset.get("maxFileSize")

    final_compress_file_size = (
        req_compress_file_size
        if req_compress_file_size is not None
        else preset_compress_file_size
    )

    # Optional CDN filename and path
    req_file_name_val = _clean_val(_get_form_field("fileName", fileName))
    final_file_name = str(req_file_name_val).strip() if req_file_name_val is not None else None
    if final_file_name and effective_prefix:
        clean_prefix = effective_prefix.strip().strip("'\"")
        if clean_prefix:
            final_file_name = f"{clean_prefix}_{final_file_name}"

    req_path_val = _clean_val(_get_form_field("path", path))
    final_path = str(req_path_val).strip() if req_path_val is not None else preset.get("path")

    # 4. Validate dimension ranges if specified
    if final_max_width is not None and final_max_width <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="maxWidth must be strictly greater than 0."
        )
    if final_max_height is not None and final_max_height <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="maxHeight must be strictly greater than 0."
        )

    image_bytes = b""
    uploaded_filename = None
    if effective_image_file and hasattr(effective_image_file, "read"):
        uploaded_filename = getattr(effective_image_file, "filename", None)
        try:
            image_bytes = await effective_image_file.read()
        except Exception:
            image_bytes = b""

    response = compression_service.compress(
        image_bytes=image_bytes,
        filename=uploaded_filename,
        max_width=int(final_max_width) if final_max_width is not None else None,
        max_height=int(final_max_height) if final_max_height is not None else None,
        detect_face=bool(final_detect_face),
        quality_compression=int(final_quality),
        pixel_compression=int(final_pixel),
        crop_image=bool(final_crop),
        prefix=effective_prefix,
        confidence=final_confidence,
        compress_file_size=final_compress_file_size,
        path=final_path,
        cdn_filename=final_file_name,
    )

    return response


