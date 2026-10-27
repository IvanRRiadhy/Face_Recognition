import base64
import logging
import os
from typing import List, Optional
import uuid
import numpy as np

from models.responses import (
    BoundingBox,
    CompressedFaceInfo,
    CompressedImageMetadata,
    CompressionConfig,
    CompressionResponse,
    CropBox,
    CropMetadata,
    FaceInfo,
    FaceLandmarks,
    ValidationReason,
)
from validators.image_validator import ImageValidator
from detectors.face_detector import BaseFaceDetector
from processors.image_cropper import ImageCropper
from processors.image_resizer import ImageResizer
from processors.image_encoder import ImageEncoder
from application.cdn_uploader import CdnUploader

logger = logging.getLogger(__name__)


class CompressionService:
    """
    Orchestrates the /compress workflow:
    1. Validate upload size & file format
    2. Decode original image
    3. Run face detector if detectFace=true
    4. If cropImage=true:
       - Validate detectFace=true (else CROP_REQUIRES_FACE_DETECTION)
       - Validate exactly 1 face (0 -> NO_FACE, >1 -> MULTI_FACE)
       - Apply face-aware crop
    5. Apply pixelCompression and maxWidth/maxHeight constraints (no upscaling, preserve aspect ratio)
    6. Map face coordinates to final output image coordinate space
    7. Encode image with requested quality (JPEG quality or PNG lossless)
    8. Return response with base64 and metadata
    """

    def __init__(
        self,
        image_validator: ImageValidator,
        face_detector: Optional[BaseFaceDetector] = None,
        crop_margin_percent: float = 25.0,
        cdn_uploader: Optional[CdnUploader] = None,
    ):
        self.image_validator = image_validator
        self.face_detector = face_detector
        self.image_cropper = ImageCropper(crop_margin_percent=crop_margin_percent)
        self.cdn_uploader = cdn_uploader or CdnUploader()

    def compress(
        self,
        image_bytes: bytes,
        filename: Optional[str],
        max_width: Optional[int] = None,
        max_height: Optional[int] = None,
        detect_face: bool = False,
        quality_compression: int = 100,
        pixel_compression: int = 100,
        crop_image: bool = False,
        prefix: Optional[str] = None,
        confidence: Optional[float] = None,
        compress_file_size: Optional[int] = None,
        path: Optional[str] = None,
        cdn_filename: Optional[str] = None,
    ) -> CompressionResponse:
        config = CompressionConfig(
            qualityCompression=quality_compression,
            pixelCompression=pixel_compression,
            cropImage=crop_image,
            compressFileSize=compress_file_size,
        )

        # 0. Check if image bytes are present
        if not image_bytes or len(image_bytes) == 0:
            return CompressionResponse(
                valid=False,
                reason=ValidationReason.NO_IMAGE,
                compression=config,
                imageData=None,
            )

        raw_b64 = base64.b64encode(image_bytes).decode("utf-8")
        ext = os.path.splitext(filename or "")[1].lower()
        if ext == ".png":
            orig_format = "png"
            orig_content_type = "image/png"
        elif ext == ".webp":
            orig_format = "webp"
            orig_content_type = "image/webp"
        else:
            orig_format = "jpeg"
            orig_content_type = "image/jpeg"

        # 1. File size validation
        size_valid, size_reason = self.image_validator.validate_file_size(len(image_bytes))
        if not size_valid:
            return CompressionResponse(
                valid=False,
                reason=size_reason or ValidationReason.FILE_TOO_LARGE,
                compression=config,
                imageData=raw_b64,
                contentType=orig_content_type,
            )

        # 2. File format validation
        name_valid, name_reason = self.image_validator.validate_filename(filename)
        if not name_valid:
            return CompressionResponse(
                valid=False,
                reason=name_reason or ValidationReason.WRONG_FORMAT,
                compression=config,
                imageData=raw_b64,
                contentType=orig_content_type,
            )

        # 3. Decode image
        decode_valid, decode_reason, img_bgr, dims = self.image_validator.decode_image(image_bytes)
        if not decode_valid or img_bgr is None or dims is None:
            return CompressionResponse(
                valid=False,
                reason=decode_reason or ValidationReason.NO_IMAGE,
                compression=config,
                imageData=raw_b64,
                contentType=orig_content_type,
            )

        # If input is WebP, convert the fallback as-is image to JPEG so imageData is always JPEG
        fallback_out_format = "png" if ext == ".png" else "jpeg"
        fallback_size_bytes = len(image_bytes)
        if ext == ".webp":
            try:
                jpeg_bytes, raw_b64, _, orig_content_type = ImageEncoder.encode(
                    image=img_bgr,
                    filename="converted.jpg",
                    quality_compression=100,
                )
                fallback_size_bytes = len(jpeg_bytes)
            except Exception:
                pass

        orig_w = dims.width
        orig_h = dims.height
        orig_size_bytes = len(image_bytes)
        orig_image_metadata = CompressedImageMetadata(
            originalWidth=orig_w,
            originalHeight=orig_h,
            width=orig_w,
            height=orig_h,
            originalFormat=orig_format,
            outputFormat=fallback_out_format,
            originalSizeBytes=orig_size_bytes,
            outputSizeBytes=fallback_size_bytes,
        )

        # 4. Optional face detection
        detected_faces: List[FaceInfo] = []
        if detect_face:
            if self.face_detector is None:
                logger.error("Face detector requested but detector is not loaded.")
                return CompressionResponse(
                    valid=False,
                    reason=ValidationReason.NO_FACE,
                    image=orig_image_metadata,
                    compression=config,
                    imageData=raw_b64,
                    contentType=orig_content_type,
                )
            all_faces = self.face_detector.detect(img_bgr)
            if confidence is not None:
                detected_faces = [f for f in all_faces if f.confidence >= confidence]
            else:
                detected_faces = all_faces

        # 5. Crop validation & execution
        applied_crop = False
        crop_box: Optional[CropBox] = None
        working_img = img_bgr

        # Keep track of original face detections
        # If no face detection was run, faces list remains empty
        working_faces_data = []
        for face in detected_faces:
            working_faces_data.append({
                "confidence": face.confidence,
                "orig_bbox": face.boundingBox,
                "curr_bbox": face.boundingBox,
                "orig_landmarks": face.landmarks,
                "curr_landmarks": face.landmarks,
            })

        if crop_image:
            if not detect_face:
                return CompressionResponse(
                    valid=False,
                    reason=ValidationReason.CROP_REQUIRES_FACE_DETECTION,
                    image=orig_image_metadata,
                    compression=config,
                    imageData=raw_b64,
                    contentType=orig_content_type,
                )

            if len(detected_faces) == 0:
                return CompressionResponse(
                    valid=False,
                    reason=ValidationReason.NO_FACE,
                    image=orig_image_metadata,
                    compression=config,
                    imageData=raw_b64,
                    contentType=orig_content_type,
                )

            if len(detected_faces) > 1:
                unprocessed_faces = [
                    CompressedFaceInfo(
                        confidence=f.confidence,
                        originalBoundingBox=f.boundingBox,
                        boundingBox=f.boundingBox,
                        originalLandmarks=f.landmarks,
                        landmarks=f.landmarks,
                    )
                    for f in detected_faces
                ]
                return CompressionResponse(
                    valid=False,
                    reason=ValidationReason.MULTIPLE_FACES,
                    image=orig_image_metadata,
                    compression=config,
                    faces=unprocessed_faces,
                    imageData=raw_b64,
                    contentType=orig_content_type,
                )

            # Exactly one face -> crop around it
            target_face = detected_faces[0]
            cropped_img, crop_box, cropped_bbox, cropped_landmarks = self.image_cropper.crop_face(
                working_img, target_face
            )
            working_img = cropped_img
            applied_crop = True

            working_faces_data = [{
                "confidence": target_face.confidence,
                "orig_bbox": target_face.boundingBox,
                "curr_bbox": cropped_bbox,
                "orig_landmarks": target_face.landmarks,
                "curr_landmarks": cropped_landmarks,
            }]

        crop_metadata = CropMetadata(
            applied=applied_crop,
            originalCropBox=crop_box,
        )

        # 6. Resize with pixelCompression and maxWidth / maxHeight constraints
        resized_img, scale_x, scale_y = ImageResizer.resize_image(
            image=working_img,
            pixel_compression=pixel_compression,
            max_width=max_width,
            max_height=max_height,
        )

        out_h, out_w = resized_img.shape[:2]

        # 7. Initial encode
        curr_quality = quality_compression
        try:
            out_bytes, base64_str, out_format, content_type = ImageEncoder.encode(
                image=resized_img,
                filename=filename,
                quality_compression=curr_quality,
            )
        except Exception as e:
            logger.error(f"Failed to encode image: {e}", exc_info=True)
            return CompressionResponse(
                valid=False,
                reason=ValidationReason.NO_IMAGE,
                image=orig_image_metadata,
                compression=config,
                imageData=raw_b64,
                contentType=orig_content_type,
            )

        # 8. Progressive compression if output size exceeds compress_file_size
        final_img = resized_img
        total_scale_x = scale_x
        total_scale_y = scale_y

        if compress_file_size is not None and compress_file_size > 0 and len(out_bytes) > compress_file_size:
            # Phase A: Progressively reduce JPEG quality (if format is JPEG)
            if out_format == "jpeg":
                while curr_quality > 5 and len(out_bytes) > compress_file_size:
                    step = 5 if curr_quality > 20 else 2
                    curr_quality = max(5, curr_quality - step)
                    out_bytes, base64_str, out_format, content_type = ImageEncoder.encode(
                        image=final_img,
                        filename=filename,
                        quality_compression=curr_quality,
                    )

            # Phase B: If still exceeding compress_file_size, progressively scale down dimensions (both JPEG and PNG)
            while len(out_bytes) > compress_file_size and min(final_img.shape[:2]) > 32:
                cur_h, cur_w = final_img.shape[:2]
                next_w = max(16, int(round(cur_w * 0.9)))
                next_h = max(16, int(round(cur_h * 0.9)))
                if next_w == cur_w and next_h == cur_h:
                    break
                import cv2
                final_img = cv2.resize(final_img, (next_w, next_h), interpolation=cv2.INTER_AREA)
                step_scale_x = next_w / float(cur_w)
                step_scale_y = next_h / float(cur_h)
                total_scale_x *= step_scale_x
                total_scale_y *= step_scale_y

                out_bytes, base64_str, out_format, content_type = ImageEncoder.encode(
                    image=final_img,
                    filename=filename,
                    quality_compression=curr_quality,
                )

            # Update reported quality in config to match final achieved quality
            config.qualityCompression = curr_quality

        out_h, out_w = final_img.shape[:2]

        # 9. Map face coordinates to final image dimensions
        final_faces: List[CompressedFaceInfo] = []
        for f_data in working_faces_data:
            final_bbox, final_landmarks = ImageResizer.scale_face_coordinates(
                bbox=f_data["curr_bbox"],
                landmarks=f_data["curr_landmarks"],
                scale_x=total_scale_x,
                scale_y=total_scale_y,
                target_w=out_w,
                target_h=out_h,
            )
            final_faces.append(
                CompressedFaceInfo(
                    confidence=f_data["confidence"],
                    originalBoundingBox=f_data["orig_bbox"],
                    boundingBox=final_bbox,
                    originalLandmarks=f_data["orig_landmarks"],
                    landmarks=final_landmarks,
                )
            )

        image_metadata = CompressedImageMetadata(
            originalWidth=orig_w,
            originalHeight=orig_h,
            width=out_w,
            height=out_h,
            originalFormat=orig_format,
            outputFormat=out_format,
            originalSizeBytes=orig_size_bytes,
            outputSizeBytes=len(out_bytes),
        )

        # 9. Upload processed image to CDN if configured
        # Determine upload file_name
        if cdn_filename and cdn_filename.strip():
            raw_target_name = cdn_filename.strip()
            stem, target_ext = os.path.splitext(raw_target_name)
            # If user provided a filename without extension or with .webp, use the output format
            if not target_ext or target_ext.lower() == ".webp":
                target_upload_filename = f"{stem}.{out_format}"
            else:
                target_upload_filename = raw_target_name
        else:
            # Default to a random uuidv4, prepended with prefix if available
            base_uuid = str(uuid.uuid4())
            clean_p = prefix.strip().strip("'\"") if (prefix and isinstance(prefix, str)) else ""
            if clean_p:
                target_upload_filename = f"{clean_p}_{base_uuid}.{out_format}"
            else:
                target_upload_filename = f"{base_uuid}.{out_format}"

        # Determine upload path folder (defaults to 'smartimage')
        target_path_folder = path.strip() if (path and path.strip()) else "smartimage"

        upload_kwargs = {
            "image_bytes": out_bytes,
            "filename": target_upload_filename,
            "content_type": content_type,
            "path_folder": target_path_folder,
        }
        if prefix is not None:
            upload_kwargs["prefix"] = prefix

        file_url = self.cdn_uploader.upload_image(**upload_kwargs)

        upload_meta = getattr(self.cdn_uploader, "last_upload_metadata", {})
        intended_file_name = upload_meta.get("intended_file_name", target_upload_filename)
        response_file_name = upload_meta.get("response_file_name")

        return CompressionResponse(
            valid=True,
            reason=ValidationReason.VALID,
            image=image_metadata,
            compression=config,
            crop=crop_metadata,
            faces=final_faces,
            imageData=base64_str,
            contentType=content_type,
            file_url=file_url,
            intended_file_name=intended_file_name,
            response_file_name=response_file_name,
        )
