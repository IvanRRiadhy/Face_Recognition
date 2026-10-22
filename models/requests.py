from pydantic import BaseModel, Field


class ValidationParameters(BaseModel):
    maxWidth: int = Field(
        ...,
        gt=0,
        description="Maximum allowed image width in pixels. Original image width must be <= maxWidth."
    )
    maxHeight: int = Field(
        ...,
        gt=0,
        description="Maximum allowed image height in pixels. Original image height must be <= maxHeight."
    )
    detectFace: bool = Field(
        ...,
        description="Whether to perform YuNet face detection on the image if dimensions are valid."
    )


class CompressionParameters(BaseModel):
    maxWidth: int = Field(
        ...,
        gt=0,
        description="Maximum allowed width in pixels. Image will be scaled down to fit if larger."
    )
    maxHeight: int = Field(
        ...,
        gt=0,
        description="Maximum allowed height in pixels. Image will be scaled down to fit if larger."
    )
    detectFace: bool = Field(
        ...,
        description="Whether to perform face detection (required if cropImage=true)."
    )
    qualityCompression: int = Field(
        85,
        ge=1,
        le=100,
        description="Encoding quality (1=lowest, 100=highest/least lossy). Default 85."
    )
    pixelCompression: int = Field(
        100,
        ge=1,
        le=100,
        description="Percentage of image dimensions to retain (1-100%). Default 100 (no pixel reduction)."
    )
    cropImage: bool = Field(
        False,
        description="Whether to crop around the detected single face. Requires detectFace=true. Default false."
    )
