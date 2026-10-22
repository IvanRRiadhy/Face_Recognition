import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from models.responses import HealthResponse
from detectors.yunet_face_detector import YuNetFaceDetector
from validators.image_validator import ImageValidator
from application.validation_service import ValidationService
from application.compression_service import CompressionService
from api.routes import validation_router, compression_router

from api.paths import get_asset_path

# Load environment variables
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("face_detection_service")

# Configurations
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "9001"))
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))
default_model = get_asset_path("assets/models/face_detection_yunet_2023mar.onnx")
MODEL_PATH = os.getenv("MODEL_PATH", default_model)
SCORE_THRESHOLD = float(os.getenv("SCORE_THRESHOLD", "0.6"))
NMS_THRESHOLD = float(os.getenv("NMS_THRESHOLD", "0.3"))
TOP_K = int(os.getenv("TOP_K", "5000"))
CROP_MARGIN_PERCENT = float(os.getenv("CROP_MARGIN_PERCENT", "25.0"))

# Parse CORS origins
cors_origins_env = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
CORS_ORIGINS = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan handler.
    Initializes the YuNet face detector model ONCE during application startup.
    Keeps model in memory for subsequent requests.
    """
    logger.info("Initializing Image Validation & Face Detection Engine...")
    
    # 1. Initialize image validator
    image_validator = ImageValidator(max_upload_size_mb=MAX_UPLOAD_SIZE_MB)

    # 2. Initialize YuNet face detector once
    face_detector = None
    if os.path.exists(MODEL_PATH):
        try:
            logger.info(f"Loading YuNet model from {MODEL_PATH}...")
            face_detector = YuNetFaceDetector(
                model_path=MODEL_PATH,
                score_threshold=SCORE_THRESHOLD,
                nms_threshold=NMS_THRESHOLD,
                top_k=TOP_K,
            )
            logger.info("YuNet model successfully loaded and ready.")
        except Exception as e:
            logger.error(f"Failed to load YuNet model: {e}", exc_info=True)
    else:
        logger.warning(f"YuNet model not found at {MODEL_PATH}. Face detection will be unavailable.")

    # 3. Initialize validation service singleton
    validation_service = ValidationService(
        image_validator=image_validator,
        face_detector=face_detector,
    )

    # 4. Initialize compression service singleton
    compression_service = CompressionService(
        image_validator=image_validator,
        face_detector=face_detector,
        crop_margin_percent=CROP_MARGIN_PERCENT,
    )

    # Attach to app state
    app.state.image_validator = image_validator
    app.state.face_detector = face_detector
    app.state.validation_service = validation_service
    app.state.compression_service = compression_service

    yield

    # Clean up on shutdown
    logger.info("Shutting down Image Validation & Face Detection Engine.")


app = FastAPI(
    title="Image Validation / Face Detection Engine",
    description="Microservice for image dimension verification, face detection, and compression.",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if CORS_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(validation_router)
app.include_router(compression_router)


@app.get(
    "/",
    summary="Service Information",
    description="Provides basic service metadata and links to OpenAPI documentation.",
)
async def root():
    return {
        "service": "Image Validation / Face Detection Engine",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "validate": "POST /validate",
            "health": "GET /health",
        },
    }


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Returns the health status of the service and model loading state.",
)
async def health():
    detector = getattr(app.state, "face_detector", None)
    model_loaded = detector is not None
    return HealthResponse(
        status="ok",
        service="image-validator",
        faceDetector="yunet" if model_loaded else "none",
        modelLoaded=model_loaded,
    )
