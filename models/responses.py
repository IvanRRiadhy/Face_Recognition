from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class ValidationReason(str, Enum):
    VALID = "VALID"
    INVALID_IMAGE = "INVALID_IMAGE"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    IMAGE_TOO_LARGE = "IMAGE_TOO_LARGE"
    NO_FACE = "NO_FACE"
    MULTIPLE_FACES = "MULTIPLE_FACES"
    MULTI_FACE = "MULTI_FACE"
    CROP_REQUIRES_FACE_DETECTION = "CROP_REQUIRES_FACE_DETECTION"


class Point2D(BaseModel):
    x: int = Field(..., description="X coordinate in pixels")
    y: int = Field(..., description="Y coordinate in pixels")


class BoundingBox(BaseModel):
    x: int = Field(..., description="Top-left X coordinate in pixels")
    y: int = Field(..., description="Top-left Y coordinate in pixels")
    width: int = Field(..., description="Width of bounding box in pixels")
    height: int = Field(..., description="Height of bounding box in pixels")


class FaceLandmarks(BaseModel):
    leftEye: Point2D = Field(..., description="Coordinates of the left eye")
    rightEye: Point2D = Field(..., description="Coordinates of the right eye")
    nose: Point2D = Field(..., description="Coordinates of the nose tip")
    leftMouth: Point2D = Field(..., description="Coordinates of the left mouth corner")
    rightMouth: Point2D = Field(..., description="Coordinates of the right mouth corner")


class FaceInfo(BaseModel):
    confidence: float = Field(..., description="Detection confidence score (0.0 to 1.0)")
    boundingBox: BoundingBox = Field(..., description="Face bounding box in original image pixels")
    landmarks: FaceLandmarks = Field(..., description="Five facial landmarks in original image pixels")


class CompressedFaceInfo(BaseModel):
    confidence: float = Field(..., description="Detection confidence score (0.0 to 1.0)")
    originalBoundingBox: BoundingBox = Field(
        ..., description="Face bounding box in the original uploaded image"
    )
    boundingBox: BoundingBox = Field(
        ..., description="Face bounding box in the final processed/cropped/scaled image"
    )
    originalLandmarks: FaceLandmarks = Field(
        ..., description="Facial landmarks in the original uploaded image"
    )
    landmarks: FaceLandmarks = Field(
        ..., description="Facial landmarks in the final processed/cropped/scaled image"
    )


class ImageDimensions(BaseModel):
    width: int = Field(..., description="Actual image width in pixels")
    height: int = Field(..., description="Actual image height in pixels")


class CompressedImageMetadata(BaseModel):
    originalWidth: int = Field(..., description="Original image width before processing")
    originalHeight: int = Field(..., description="Original image height before processing")
    width: int = Field(..., description="Final output image width in pixels")
    height: int = Field(..., description="Final output image height in pixels")
    originalFormat: str = Field(..., description="Original image format (e.g. jpeg, png)")
    outputFormat: str = Field(..., description="Output image format (e.g. jpeg, png)")
    originalSizeBytes: int = Field(..., description="Original uploaded image size in bytes")
    outputSizeBytes: int = Field(..., description="Final compressed image size in bytes")


class CompressionConfig(BaseModel):
    qualityCompression: int = Field(..., description="Quality factor applied (1-100)")
    pixelCompression: int = Field(..., description="Percentage of dimensions retained (1-100)")
    cropImage: bool = Field(..., description="Whether face-aware crop was requested")
    compressFileSize: Optional[int] = Field(None, description="Maximum desired output file size in bytes")


class CropBox(BaseModel):
    x: int = Field(..., description="Crop window top-left X in original image pixels")
    y: int = Field(..., description="Crop window top-left Y in original image pixels")
    width: int = Field(..., description="Crop window width in original image pixels")
    height: int = Field(..., description="Crop window height in original image pixels")


class CropMetadata(BaseModel):
    applied: bool = Field(..., description="Whether crop was successfully applied")
    originalCropBox: Optional[CropBox] = Field(
        None, description="Crop box coordinates in the original image coordinate system"
    )


class ValidationResponse(BaseModel):
    valid: bool = Field(..., description="Whether validation passed")
    reason: ValidationReason = Field(..., description="Validation outcome reason code")
    image: Optional[ImageDimensions] = Field(None, description="Decoded original image dimensions")
    faces: List[FaceInfo] = Field(default_factory=list, description="List of detected faces")


class CompressionResponse(BaseModel):
    valid: bool = Field(..., description="Whether compression and validation passed")
    reason: ValidationReason = Field(..., description="Outcome reason code")
    image: Optional[CompressedImageMetadata] = Field(None, description="Image metadata before and after compression")
    compression: Optional[CompressionConfig] = Field(None, description="Compression settings used")
    crop: Optional[CropMetadata] = Field(None, description="Crop metadata if applied")
    faces: List[CompressedFaceInfo] = Field(default_factory=list, description="Faces in original and output coordinates")
    imageData: Optional[str] = Field(None, description="Base64 encoded processed image data without prefix")
    contentType: Optional[str] = Field(None, description="MIME content type of the processed image (e.g. image/jpeg)")
    file_url: Optional[str] = Field(None, description="Uploaded CDN file URL or failure status")
    intended_file_name: Optional[str] = Field(None, description="Intended filename requested for CDN storage")
    response_file_name: Optional[str] = Field(None, description="Actual filename assigned and stored by the CDN server")


class HealthResponse(BaseModel):
    status: str
    service: str
    faceDetector: str
    modelLoaded: bool
