import logging
from typing import Optional
from models.responses import ValidationReason, ValidationResponse
from validators.image_validator import ImageValidator
from validators.dimension_validator import DimensionValidator
from detectors.face_detector import BaseFaceDetector

logger = logging.getLogger(__name__)


class ValidationService:
    """
    Orchestrates image decoding, dimension validation, and conditional face detection.
    Follows strict pipeline order:
    1. Validate file size & extension
    2. Safely decode image & read width/height
    3. Check width <= maxWidth AND height <= maxHeight (short-circuit on fail -> IMAGE_TOO_LARGE)
    4. If detectFace == False -> return VALID immediately without invoking detector
    5. If detectFace == True -> invoke YuNet face detector
    6. Return faces or NO_FACE
    """

    def __init__(
        self,
        image_validator: ImageValidator,
        face_detector: Optional[BaseFaceDetector] = None,
    ):
        self.image_validator = image_validator
        self.face_detector = face_detector

    def validate(
        self,
        image_bytes: bytes,
        filename: Optional[str],
        max_width: int,
        max_height: int,
        detect_face: bool,
        confidence: Optional[float] = None,
    ) -> ValidationResponse:
        # Step 0: Check if image bytes are present
        if not image_bytes or len(image_bytes) == 0:
            return ValidationResponse(
                valid=False,
                reason=ValidationReason.NO_IMAGE,
                image=None,
                faces=[],
            )

        # Step 1: File size validation
        size_valid, size_reason = self.image_validator.validate_file_size(len(image_bytes))
        if not size_valid:
            return ValidationResponse(
                valid=False,
                reason=size_reason or ValidationReason.FILE_TOO_LARGE,
                image=None,
                faces=[],
            )

        # Step 2: Filename extension validation
        name_valid, name_reason = self.image_validator.validate_filename(filename)
        if not name_valid:
            return ValidationResponse(
                valid=False,
                reason=name_reason or ValidationReason.WRONG_FORMAT,
                image=None,
                faces=[],
            )

        # Step 3: Decode image safely
        decode_valid, decode_reason, img_bgr, dims = self.image_validator.decode_image(image_bytes)
        if not decode_valid or img_bgr is None or dims is None:
            return ValidationResponse(
                valid=False,
                reason=decode_reason or ValidationReason.NO_IMAGE,
                image=None,
                faces=[],
            )

        # Step 4: Dimension validation (width <= max_width and height <= max_height)
        dims_valid, dims_reason = DimensionValidator.validate(
            image_dims=dims,
            max_width=max_width,
            max_height=max_height,
        )
        if not dims_valid:
            # Short-circuit: Do NOT run face detector if dimensions fail
            return ValidationResponse(
                valid=False,
                reason=dims_reason,
                image=dims,
                faces=[],
            )

        # Step 5: Short-circuit if detectFace == False
        if not detect_face:
            return ValidationResponse(
                valid=True,
                reason=ValidationReason.VALID,
                image=dims,
                faces=[],
            )

        # Step 6: Face detection if detectFace == True
        if self.face_detector is None:
            logger.error("Face detector requested but detector is not loaded/available.")
            return ValidationResponse(
                valid=False,
                reason=ValidationReason.NO_FACE,
                image=dims,
                faces=[],
            )

        raw_faces = self.face_detector.detect(img_bgr)
        if confidence is not None:
            faces = [f for f in raw_faces if f.confidence >= confidence]
        else:
            faces = raw_faces

        if len(faces) == 0:
            return ValidationResponse(
                valid=False,
                reason=ValidationReason.NO_FACE,
                image=dims,
                faces=[],
            )

        return ValidationResponse(
            valid=True,
            reason=ValidationReason.VALID,
            image=dims,
            faces=faces,
        )
