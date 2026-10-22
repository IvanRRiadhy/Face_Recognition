from typing import Any, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from models.responses import ValidationResponse
from application.validation_service import ValidationService

router = APIRouter(tags=["Validation"])


def get_validation_service(request: Request) -> ValidationService:
    service = getattr(request.app.state, "validation_service", None)
    if not service:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Validation service is not initialized."
        )
    return service


@router.post(
    "/validate",
    response_model=ValidationResponse,
    summary="Validate uploaded image dimensions and detect faces",
    description="""
Upload an image (`.png`, `.jpg`, `.jpeg`) along with required parameters:
- **imageFile**: Multipart image binary.
- **maxWidth**: Maximum allowed width in pixels (`width <= maxWidth` is valid).
- **maxHeight**: Maximum allowed height in pixels (`height <= maxHeight` is valid).
- **detectFace**: Whether to run the YuNet face detector.
- **confidence** (*optional, 0.0-1.0*): Minimum face detection confidence threshold. Faces with confidence below this threshold are ignored.

### Validation Flow:
1. Decode image safely and verify file size / format.
2. If `width > maxWidth` or `height > maxHeight` -> Returns `IMAGE_TOO_LARGE` immediately without executing face detection.
3. If `detectFace == false` -> Returns `VALID` immediately without invoking face detection.
4. If `detectFace == true` -> Invokes YuNet face detector. If faces meeting confidence threshold are found, returns `VALID` with bounding boxes and 5-point facial landmarks (`leftEye`, `rightEye`, `nose`, `leftMouth`, `rightMouth`) in original pixel coordinates. If no face is found (or none meet confidence), returns `NO_FACE`.
    """,
    responses={
        200: {
            "description": "Validation completed (whether image passed validation or had specific reasons)",
            "content": {
                "application/json": {
                    "example": {
                        "valid": True,
                        "reason": "VALID",
                        "image": {
                            "width": 1280,
                            "height": 960
                        },
                        "faces": [
                            {
                                "confidence": 0.96,
                                "boundingBox": {
                                    "x": 420,
                                    "y": 180,
                                    "width": 300,
                                    "height": 360
                                },
                                "landmarks": {
                                    "leftEye": {"x": 475, "y": 270},
                                    "rightEye": {"x": 560, "y": 268},
                                    "nose": {"x": 520, "y": 320},
                                    "leftMouth": {"x": 480, "y": 365},
                                    "rightMouth": {"x": 555, "y": 363}
                                }
                            }
                        ]
                    }
                }
            }
        },
        400: {"description": "Invalid input parameters (e.g. non-positive dimensions)"},
        422: {"description": "Unprocessable Entity (missing form fields)"}
    }
)
async def validate_image(
    request: Request,
    imageFile: Optional[UploadFile] = File(None, description="Uploaded image file (.png, .jpg, .jpeg)"),
    maxWidth: Optional[Any] = Form(None, description="Maximum allowed image width in pixels"),
    maxHeight: Optional[Any] = Form(None, description="Maximum allowed image height in pixels"),
    detectFace: Optional[Any] = Form(None, description="Enable YuNet face detection if dimensions are valid"),
    confidence: Optional[Any] = Form(None, description="Minimum face detection confidence threshold (0.0 to 1.0)"),
    validation_service: ValidationService = Depends(get_validation_service),
) -> ValidationResponse:
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

    effective_image_file = _get_form_field("imageFile", imageFile)
    if not effective_image_file or not hasattr(effective_image_file, "read"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[{
                "loc": ["body", "imageFile"],
                "msg": "field required",
                "type": "value_error.missing",
            }]
        )

    def _clean_val(val):
        if val is None:
            return None
        if isinstance(val, str):
            s = val.strip().lower()
            if s in ("", "null", "none"):
                return None
        return val

    def _clean_int(val, field_name: str, required: bool = True) -> Optional[int]:
        cleaned = _clean_val(val)
        if cleaned is None:
            if required:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=[{
                        "loc": ["body", field_name],
                        "msg": "field required",
                        "type": "value_error.missing",
                    }]
                )
            return None
        try:
            return int(cleaned)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=[{
                    "loc": ["body", field_name],
                    "msg": "value is not a valid integer",
                    "type": "type_error.integer",
                }]
            )

    def _clean_bool(val, field_name: str, required: bool = True) -> Optional[bool]:
        cleaned = _clean_val(val)
        if cleaned is None:
            if required:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=[{
                        "loc": ["body", field_name],
                        "msg": "field required",
                        "type": "value_error.missing",
                    }]
                )
            return None
        if isinstance(cleaned, bool):
            return cleaned
        s = str(cleaned).strip().lower()
        if s in ("true", "1", "yes", "t", "y"):
            return True
        if s in ("false", "0", "no", "f", "n"):
            return False
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[{
                "loc": ["body", field_name],
                "msg": "value is not a valid boolean",
                "type": "type_error.bool",
            }]
        )

    def _clean_float(val, field_name: str) -> Optional[float]:
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
        if not (0.0 <= num <= 1.0):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=[{
                    "loc": ["body", field_name],
                    "msg": "ensure this value is between 0.0 and 1.0",
                    "type": "value_error.number.not_in_range",
                }]
            )
        return num

    final_max_width = _clean_int(_get_form_field("maxWidth", maxWidth), "maxWidth", required=True)
    final_max_height = _clean_int(_get_form_field("maxHeight", maxHeight), "maxHeight", required=True)
    final_detect_face = _clean_bool(_get_form_field("detectFace", detectFace), "detectFace", required=True)
    final_confidence = _clean_float(_get_form_field("confidence", confidence), "confidence")

    if final_max_width <= 0 or final_max_height <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="maxWidth and maxHeight must be strictly greater than 0."
        )

    # Read binary contents safely
    try:
        image_bytes = await effective_image_file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded file: {str(e)}"
        )

    response = validation_service.validate(
        image_bytes=image_bytes,
        filename=effective_image_file.filename,
        max_width=final_max_width,
        max_height=final_max_height,
        detect_face=final_detect_face,
        confidence=final_confidence,
    )

    return response
