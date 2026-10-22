# Image Validation / Face Detection Engine

A lightweight, standalone Python AI microservice for validating image dimensions, performing face detection, and applying face-aware cropping & compression using **FastAPI** and **OpenCV YuNet (`FaceDetectorYN`)**.

Built following the modular, clean architecture of the Floorplan Detector AI engine.

---

## Features

- **Decoupled Architecture**: Layered design with distinct `api/`, `application/`, `processors/`, `validators/`, `detectors/`, and `models/`.
- **OpenCV YuNet ONNX**: High-performance face detection with 5-point facial landmark extraction loaded once as an application startup singleton (lifespan).
- **Two Independent Endpoints**:
  1. `POST /validate`: Answers *"Is this image valid as-is?"* (rejects images exceeding dimensions with `IMAGE_TOO_LARGE`).
  2. `POST /compress`: Answers *"Process this image according to my requested dimensions, compression quality, optional face detection, and optional face-aware cropping, then return the processed image."*
- **Compression & Cropping Pipeline**:
  - `pixelCompression` ($1-100\%$ dimension retention).
  - `maxWidth` / `maxHeight` aspect-ratio-preserving downscaling (never upscales).
  - `cropImage`: Face-aware cropping around a single detected face with configurable margin (default $25\%$).
  - Dual coordinate tracking: returns both original and output image face coordinates.
  - Returns raw Base64-encoded image string with `contentType`.
- **Thread Safety**: Model inference is protected by a thread synchronization lock for concurrent request safety.

---

## Project Structure

```text
Face_Detection/
├── api/
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── validation.py         # POST /validate endpoint
│   │   └── compression.py        # POST /compress endpoint
│   ├── __init__.py
│   └── main.py                   # FastAPI lifespan singleton, CORS, GET / and GET /health
├── application/
│   ├── __init__.py
│   ├── validation_service.py     # Orchestrator for /validate
│   └── compression_service.py    # Orchestrator for /compress
├── detectors/
│   ├── __init__.py
│   ├── face_detector.py          # Abstract BaseFaceDetector interface
│   └── yunet_face_detector.py    # OpenCV FaceDetectorYN with thread safety lock
├── validators/
│   ├── __init__.py
│   ├── image_validator.py        # File size, allowed formats, safe cv2.imdecode
│   └── dimension_validator.py    # width <= maxWidth and height <= maxHeight
├── processors/
│   ├── __init__.py
│   ├── image_resizer.py          # Aspect-ratio scaling, no upscaling, coordinate mapping
│   ├── image_cropper.py          # Face-aware expanded crop, boundary clamping
│   └── image_encoder.py          # JPEG quality & PNG lossless encoder to base64
├── models/
│   ├── __init__.py
│   ├── requests.py               # ValidationParameters, CompressionParameters
│   └── responses.py              # ValidationResponse, CompressionResponse, FaceInfo, Landmarks
├── assets/
│   └── models/
│       └── face_detection_yunet_2023mar.onnx
├── tests/
│   ├── fixtures/
│   │   ├── single_face.jpg       # Local single face fixture
│   │   ├── multiple_faces.jpg    # Local multi-face fixture
│   │   └── no_face.jpg           # Local non-face fixture
│   ├── __init__.py
│   ├── test_dimension_validation.py
│   ├── test_face_detection.py
│   ├── test_coordinates.py
│   ├── test_compression.py
│   └── test_api.py
├── requirements.txt
├── .env.example
├── README.md
└── .gitignore
```

---

## Installation & Setup

### 1. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 2. YuNet Model Setup & Licensing

The engine uses `face_detection_yunet_2023mar.onnx` from the official [OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet).

- **License**: Apache 2.0 / MIT (OpenCV Model Zoo)
- **Model location**: `assets/models/face_detection_yunet_2023mar.onnx`
- To download:
  ```powershell
  python -c "import urllib.request, os; os.makedirs('assets/models', exist_ok=True); urllib.request.urlretrieve('https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx', 'assets/models/face_detection_yunet_2023mar.onnx')"
  ```

---

## Running the Service

### Start Uvicorn Server (Default Port 9001)

```powershell
python -m uvicorn api.main:app --host 0.0.0.0 --port 9001
```

Expected log output:

```text
INFO:     Started server process [....]
INFO:     Waiting for application startup.
INFO:     Initializing Image Validation & Face Detection Engine...
INFO:     Loading YuNet model from assets/models/face_detection_yunet_2023mar.onnx...
INFO:     YuNet model successfully loaded and ready.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:9001 (Press CTRL+C to quit)
```

---

## Windows Service & Local Network (WLAN/LAN) Access

Two batch scripts are provided in the root directory to run this service permanently in the background as a native Windows Service and expose it to other devices connected to your Wi-Fi/Router:

### 1. Install & Run as Windows Service
Right-click **`install_service.bat`** and choose **"Run as administrator"**.

The script will automatically:
1. Verify Python and package paths.
2. Register the service as **`FaceDetectionEngine`** set to auto-start with Windows (`SERVICE_AUTO_START`).
3. Direct stdout and stderr to `service.log` and `service_error.log`.
4. Open inbound port **9001 TCP** in the **Windows Defender Firewall** (`profile=private,public`) so other computers and phones on your router/WLAN can access it.
5. Display your local machine's IP addresses (e.g. `http://192.168.1.166:9001/docs`).

### 2. Uninstall Windows Service
Right-click **`uninstall_service.bat`** and choose **"Run as administrator"**.
It stops and removes the service and deletes the firewall rule.

---

## API Documentation

Interactive Swagger documentation is available at:
👉 **`http://localhost:9001/docs`**

### Endpoints Overview

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Service metadata and links |
| `GET` | `/health` | Health status and YuNet detector load status |
| `POST` | `/validate` | Validates image dimensions (`width <= maxWidth`) and optional face detection |
| `POST` | `/compress` | Resizes, face-crops, quality-compresses, and returns the processed image |

---

## Endpoint Details

### 1. `POST /validate`

Multipart Form Fields:
- `imageFile` (*binary*): `.png`, `.jpg`, or `.jpeg`
- `maxWidth` (*int > 0*): Maximum allowed width.
- `maxHeight` (*int > 0*): Maximum allowed height.
- `detectFace` (*bool*): Whether to run YuNet.
- `confidence` (*float 0.0-1.0, optional*): Minimum face confidence threshold (e.g. `0.8`). Faces below this score will be ignored.

If image dimensions exceed `maxWidth` or `maxHeight`, rejects with `IMAGE_TOO_LARGE`.

---

### 2. `POST /compress`

Query Parameters:
- `prefix` (*string, optional*): Optional prefix parameter, e.g. `http://IP:9001/compress?prefix=abc`. If provided:
  - Looks up configured presets in `config.json` (`presets.<prefix>`) and uses them as default request parameters (`maxWidth`, `maxHeight`, `detectFace`, `confidence`, `qualityCompression`, `pixelCompression`, `cropImage`, `compressFileSize`). This allows callers to omit request body fields entirely.
  - Forwards the same prefix query string (`?prefix="string"`) to the CDN upload URL and adds `onlyupload = true`.

Multipart Form Fields:
- `imageFile` (*binary*): `.png`, `.jpg`, or `.jpeg`
- `maxWidth` (*int > 0, optional*): Target maximum width. If omitted or null, no width-based resizing is performed.
- `maxHeight` (*int > 0, optional*): Target maximum height. If omitted or null, no height-based resizing is performed.
- `detectFace` (*bool, optional, default false*): Run YuNet face detection (must be `true` if `cropImage=true`). Defaults to `false`.
- `confidence` (*float 0.0-1.0, optional if preset configured*): Minimum face confidence threshold (e.g. `0.8`). Any face detected below this score is excluded. If no faces meet this threshold, `NO_FACE` is reported.
- `compressFileSize` (*int > 0, optional if preset configured*): Maximum desired output file size in bytes (e.g. `51200` for 50 KB). If output size exceeds this threshold, compression is progressively applied (quality reduction and dimension scaling) until the file size is under the maximum (also backwards-compatible with `maxFileSize`).
- `qualityCompression` (*int 1-100, default 100 or preset*): Encoding quality for JPEG / lossless tuning for PNG (default `100` = no quality compression).
- `pixelCompression` (*int 1-100, default 100 or preset*): Percentage of dimensions to retain.
- `cropImage` (*bool, default false or preset*): Face-aware cropping around a single detected face.
- `fileName` (*string, optional*): Custom filename for CDN storage. If omitted or null, defaults to a random UUIDv4 (e.g. `123e4567-e89b-12d3-a456-426614174000.jpg`). If `prefix` is present, it is automatically prepended: `{prefix}_{fileName}`.
- `path` (*string, optional*): Custom folder path for CDN storage. If omitted or null, defaults to `"smartimage"`.
- `prefix` (*string, optional*): Fallback if not supplied in query string.

> **Note on Value `0`**: Sending `0` for `maxWidth`, `maxHeight`, `qualityCompression`, `pixelCompression`, `confidence`, or `compressFileSize` is treated as `null` (falls back to defaults or preset).

#### Compression Example with Preset (PowerShell / cURL):

```powershell
# Call with preset (e.g. abc):
curl.exe -X POST "http://localhost:9001/compress?prefix=abc" `
  -F "imageFile=@tests\fixtures\single_face.jpg"
```

#### Compression Example with Custom Fields (PowerShell / cURL):

```powershell
curl.exe -X POST "http://localhost:9001/compress?prefix=\"string\"" `
  -F "imageFile=@tests\fixtures\single_face.jpg" `
  -F "maxWidth=1000" `
  -F "maxHeight=800" `
  -F "detectFace=true" `
  -F "qualityCompression=85" `
  -F "pixelCompression=70" `
  -F "cropImage=true"
```

#### Compression Response Example:

```json
{
  "valid": true,
  "reason": "VALID",
  "image": {
    "originalWidth": 512,
    "originalHeight": 512,
    "width": 249,
    "height": 315,
    "originalFormat": "jpeg",
    "outputFormat": "jpeg",
    "originalSizeBytes": 91814,
    "outputSizeBytes": 15420
  },
  "compression": {
    "qualityCompression": 85,
    "pixelCompression": 70,
    "cropImage": true
  },
  "crop": {
    "applied": true,
    "originalCropBox": {
      "x": 172,
      "y": 131,
      "width": 218,
      "height": 276
    }
  },
  "faces": [
    {
      "confidence": 0.909,
      "originalBoundingBox": {
        "x": 208,
        "y": 183,
        "width": 146,
        "height": 207
      },
      "boundingBox": {
        "x": 41,
        "y": 59,
        "width": 167,
        "height": 236
      },
      "originalLandmarks": {
        "leftEye": { "x": 272, "y": 269 },
        "rightEye": { "x": 328, "y": 276 },
        "nose": { "x": 310, "y": 313 },
        "leftMouth": { "x": 271, "y": 342 },
        "rightMouth": { "x": 311, "y": 348 }
      },
      "landmarks": {
        "leftEye": { "x": 114, "y": 158 },
        "rightEye": { "x": 178, "y": 166 },
        "nose": { "x": 158, "y": 208 },
        "leftMouth": { "x": 113, "y": 241 },
        "rightMouth": { "x": 159, "y": 248 }
      }
    }
  ],
  "imageData": "/9j/4AAQSkZJRgABAQ...",
  "contentType": "image/jpeg",
  "file_url": "/face/6d2c4637-bda6-4248-885a-92b87aaa891f.jpeg",
  "intended_file_name": "6d2c4637-bda6-4248-885a-92b87aaa891f.jpeg",
  "response_file_name": "6d2c4637-bda6-4248-885a-92b87aaa891f.jpeg"
}
```

---

## Running Automated Tests

Run the complete test suite:

```powershell
python -m pytest -v
```

All 44 test cases cover:
- Dimension validation edge cases (exact, smaller, width too large, height too large, both too large).
- Face detection with local fixtures (single face, multiple faces, non-face).
- Coordinate boundaries (bounding box & landmark pixels within original image dimensions).
- Compression pipeline tests (pixel compression, dimension scaling, aspect ratio preservation, no upscaling, multiple qualities).
- Face-aware cropping with margin and coordinate translation.
- End-to-end API tests for both `POST /validate` and `POST /compress` (valid requests, invalid images, missing parameters, parameter ranges 422, multiple faces ambiguity, etc.).
