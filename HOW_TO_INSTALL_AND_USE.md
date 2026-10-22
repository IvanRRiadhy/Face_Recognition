# Face Detection Engine - Standalone Server

A self-contained, high-performance Windows microservice for image validation, YuNet face detection, face-aware cropping, and image compression running on **Port 9001**.

> **No Python installation or dependencies are required on the host computer.** Everything needed is bundled inside this package.

---

## 📦 Package Contents

| File / Folder | Description |
| :--- | :--- |
| `FaceDetectionEngine.exe` | Standalone microservice executable |
| `_internal/` | Bundled runtime, ONNX model (`face_detection_yunet_2023mar.onnx`), OpenCV, and FastAPI libraries |
| `config.json` | Configuration file for port number and CDN upload URL |
| `nssm.exe` | Non-Sucking Service Manager for managing the Windows background service |
| `InstallAsService.bat` | **1-Click Installer**: Registers and starts the engine as a background Windows Service |
| `UninstallService.bat` | **1-Click Uninstaller**: Stops and removes the background Windows Service |
| `HOW_TO_INSTALL_AND_USE.md` | This setup and user guide |
| `README.md` | Detailed architecture, API specs, and technical documentation |

---

## 🚀 Installation & Running

### Option 1: Run as a Windows Service (Recommended for Production)

Running as a Windows Service ensures the engine runs silently in the background, starts automatically when Windows boots, and automatically restarts if unexpectedly terminated.

1. **Extract** this entire folder to your desired location (for example: `C:\Face_Detection` or `D:\FaceDetectionEngine`).
2. **Right-click `InstallAsService.bat`** and select **"Run as administrator"**.
3. The script will:
   - Register `FaceDetectionService` in Windows Services.
   - Configure automatic startup on boot (`SERVICE_AUTO_START`).
   - Enable log rotation to `service_output.log` and `service_error.log` (10 MB max size / daily rotation).
   - Start the service immediately.
4. Verify the service is running:
   - Open your browser to: **http://localhost:9001/docs**
   - Or run in PowerShell: `Get-Service FaceDetectionService`

---

### Option 2: Run in Console Mode (For Testing & Debugging)

1. Simply **double-click `FaceDetectionEngine.exe`** (or execute it from Command Prompt / PowerShell).
2. The server will start and display live logs in the console window.
3. Press `Ctrl + C` in the console window to stop the server.

---

## 🛑 How to Uninstall the Windows Service

1. **Right-click `UninstallService.bat`** and select **"Run as administrator"**.
2. The script will stop the service if running and remove it cleanly from Windows Services.

---

## ⚙️ Configuration (`config.json`)

You can customize port and CDN upload settings by editing `config.json` located next to `FaceDetectionEngine.exe`:

```json
{
    "port": 9001,
    "cdnURL": "https://be-vms.app.bio-experience.com/cdn/upload",
    "presets": {
        "ipsotek": {
            "maxWidth": 800,
            "maxHeight": 800,
            "detectFace": true,
            "confidence": 0.8,
            "cropImage": true,
            "qualityCompression": 85,
            "pixelCompression": 100,
            "compressFileSize": 10000
        },
        "falco": {
            "maxWidth": 920,
            "maxHeight": 1280,
            "detectFace": true,
            "confidence": 0.8,
            "cropImage": false, 
            "qualityCompression": 75,
            "pixelCompression": 100,
            "compressFileSize": 25000
        },
        "abc": {
            "maxWidth": 400,
            "maxHeight": 960,
            "detectFace": true,
            "confidence": 0.8,
            "cropImage": false,
            "qualityCompression": 85,
            "pixelCompression": 100,
            "compressFileSize": 51200
        },
        "xyz": {
            "maxWidth": 920,
            "maxHeight": 1280,
            "detectFace": true,
            "confidence": 0.8,
            "cropImage": false,
            "qualityCompression": 75,
            "pixelCompression": 100
        }
    }
}
```

- **`port`**: HTTP port for the service (default: `9001`).
- **`cdnURL`**: Endpoint for uploading processed images.
- **`presets`**: Configurable default request parameters mapped by prefix name. When callers specify `prefix=<name>` in the request body, default values (`maxWidth`, `maxHeight`, `detectFace`, `confidence`, `qualityCompression`, `pixelCompression`, `cropImage`, `compressFileSize`) are automatically loaded from the preset so callers only need to provide `imageFile` and `prefix`.

> **Note**: If running as a Windows Service, restart the service after modifying `config.json`:
> ```powershell
> nssm.exe restart FaceDetectionService
> ```

---

## 📡 API Usage & Endpoints

Base URL: `http://localhost:9001` (or `http://<LAN_IP>:9001`)

### 1. Interactive Swagger Documentation
Open your browser to:
- **Swagger UI**: [http://localhost:9001/docs](http://localhost:9001/docs)
- **ReDoc**: [http://localhost:9001/redoc](http://localhost:9001/redoc)

---

### 2. Health Check (`GET /health`)

Check service status and verify whether the YuNet AI model is loaded:

```powershell
curl.exe -s http://localhost:9001/health
```

**Response Example:**
```json
{
  "status": "ok",
  "service": "image-validator",
  "faceDetector": "yunet",
  "modelLoaded": true
}
```

---

### 3. Compress & Face-Aware Crop (`POST /compress`)

Process an image with optional YuNet face detection, face-aware cropping, dimension reduction, and quality compression. Uploads the processed image to CDN if configured.

#### URL:
```
POST http://localhost:9001/compress
```

#### Multipart Form Fields:
- `imageFile` (*binary, required*): Uploaded image (`.jpg`, `.jpeg`, `.png`).
- `prefix` (*string, optional*): Optional prefix string.
  - Automatically loads default parameter values from `presets` in `config.json` (e.g. `prefix="abc"` or `prefix="xyz"`), making form parameters optional!
  - Adds the prefix query string (`?prefix="string"`) to the CDN upload URL.
  - Adds the parameter `onlyupload=true` to the CDN request.
- `maxWidth` (*int, optional*): Maximum allowed width in pixels. If omitted or null, no width-based resizing is performed.
- `maxHeight` (*int, optional*): Maximum allowed height in pixels. If omitted or null, no height-based resizing is performed.
- `detectFace` (*bool, optional, default false*): `true` to run face detection (required if `cropImage=true`). Defaults to `false`.
- `confidence` (*float 0.0-1.0, optional if preset exists*): Minimum face detection confidence threshold (e.g. `0.8`). Faces below this score will not be counted as valid faces.
- `compressFileSize` (*int > 0, optional if preset exists*): Maximum desired output file size in bytes (e.g. `51200` for 50 KB). If output size exceeds this threshold, compression is progressively applied (quality reduction and dimension scaling) until the file size is under the maximum (also backwards-compatible with `maxFileSize`).
- `qualityCompression` (*int 1-100, default 100 or preset*): Encoding quality percentage (default `100` = no quality compression).
- `pixelCompression` (*int 1-100, default 100 or preset*): Percentage of dimensions to retain.
- `cropImage` (*bool, default false or preset*): Crop tightly around a single detected face with margin.
- `fileName` (*string, optional*): Custom filename for CDN storage. If omitted or null, defaults to a random UUIDv4 (e.g. `123e4567-e89b-12d3-a456-426614174000.jpg`). Jika `prefix` juga disertakan (misal `prefix="ipsotek"` dan `fileName="FaceBoss"`), maka otomatis menjadi `{prefix}_{fileName}` (contoh: `ipsotek_FaceBoss.jpg`).
- `path` (*string, optional*): Custom folder path for CDN storage. If omitted or null, defaults to `"smartimage"`.
> **Catatan Nilai `0`**: Mengirimkan nilai `0` pada parameter `maxWidth`, `maxHeight`, `qualityCompression`, `pixelCompression`, `confidence`, maupun `compressFileSize` akan diabaikan dan diperlakukan sama seperti `null` (tidak ada batasan/menggunakan default atau preset).

#### Example Call using Preset (PowerShell):
```powershell
# Using prefix preset 'abc' in body - no need to specify maxWidth, maxHeight, or detectFace!
curl.exe -X POST "http://localhost:9001/compress" `
  -F "imageFile=@single_face.jpg" `
  -F "prefix=abc"
```

#### Example Call without Preset / Custom Overrides (PowerShell):
```powershell
curl.exe -X POST "http://localhost:9001/compress" `
  -F "imageFile=@single_face.jpg" `
  -F "prefix=\"avatar\"" `
  -F "maxWidth=1000" `
  -F "maxHeight=800" `
  -F "detectFace=true" `
  -F "cropImage=true" `
  -F "qualityCompression=85" `
  -F "pixelCompression=80"
```

#### Response Fields:
- `valid` (*bool*): Whether validation and processing succeeded.
- `reason` (*string*): Outcome code (`VALID`, `IMAGE_TOO_LARGE`, `NO_FACE`, `MULTIPLE_FACES`, `CROP_REQUIRES_FACE_DETECTION`, `FILE_TOO_LARGE`, `UNSUPPORTED_FORMAT`, `INVALID_IMAGE`).
- `image`: Output and original metadata (`width`, `height`, `originalWidth`, `originalHeight`, `outputSizeBytes`, `originalSizeBytes`, `outputFormat`, `originalFormat`).
- `compression`: Applied compression configuration (`qualityCompression`, `pixelCompression`, `cropImage`, `compressFileSize`).
- `crop`: Crop metadata (`applied`, `originalCropBox`).
- `faces`: Face bounding boxes and 5 landmarks in both original and final coordinate systems.
- `imageData`: Base64 string of processed image without prefix.
- `contentType`: MIME type (`image/jpeg` or `image/png`).
- `file_url`: Uploaded CDN URL (e.g. `/face/xxx.jpg`) or `"cdn_upload failed"` if CDN is unreachable.
- `intended_file_name`: Filename requested for CDN storage.
- `response_file_name`: Filename returned by CDN server.

---

### 4. Validate Image (`POST /validate`)

Validates file format, file size, dimensions (`width <= maxWidth`, `height <= maxHeight`), and optional YuNet face detection without modifying the image. If dimensions exceed limits, returns `IMAGE_TOO_LARGE` immediately without executing face detection.

#### Multipart Form Fields:
- `imageFile` (*binary, required*): Uploaded image (`.jpg`, `.jpeg`, `.png`).
- `maxWidth` (*int > 0, required*): Maximum allowed width in pixels.
- `maxHeight` (*int > 0, required*): Maximum allowed height in pixels.
- `detectFace` (*bool, required*): Whether to run YuNet face detector (`true`/`false`).
- `confidence` (*float 0.0-1.0, optional*): Minimum face detection confidence threshold (e.g. `0.8`). Faces below this threshold are ignored.

#### Example Call (PowerShell):
```powershell
curl.exe -X POST "http://localhost:9001/validate" `
  -F "imageFile=@photo.jpg" `
  -F "maxWidth=1500" `
  -F "maxHeight=1500" `
  -F "detectFace=true" `
  -F "confidence=0.8"
```

---

## 🔍 Log Files

When running as a service, logs are stored in the installation directory:
- `service_output.log` — Standard output logs (HTTP requests, upload URLs, status).
- `service_error.log` — Error and warning logs.
