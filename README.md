<div align="center">

# 🦅 SENTINELA
### Next-Generation NVR & Surveillance Ecosystem

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![MediaMTX](https://img.shields.io/badge/MediaMTX-Core-orange?style=for-the-badge&logo=rss&logoColor=white)](https://github.com/bluenviron/mediamtx)
[![License](https://img.shields.io/badge/license-MIT-purple?style=for-the-badge)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey?style=for-the-badge&logo=linux)](https://github.com/BIbEsfiha1/Sentinela)

<p align="center">
  <b>Enterprise-Grade Security • Ultra-Low Latency • Cloud Sync • Zero Config</b>
</p>

[Features](#-key-features) • [Architecture](#-system-architecture) • [Quick Start](#-quick-start) • [Configuration](#-configuration) • [API](#-rest-api)

</div>

---

## 📖 Overview

**Sentinela** is not just another camera viewer; it is a **professional, self-hosted NVR (Network Video Recorder)** solution designed for performance, privacy, and extensibility. 

Built on the robust **FastAPI** framework and leveraging **MediaMTX** for state-of-the-art streaming, Sentinela bridges the gap between expensive proprietary hardware and flexible open-source software. It transforms any standard computer into a powerful security hub capable of managing RTSP streams, detecting ONVIF devices, and synchronizing critical footage to the cloud with military-grade reliability.

### 🌟 Why Sentinela?

- **🚀 Zero Latency**: Experience **WebRTC** streaming with sub-second delay. See events as they happen, not 10 seconds later.
- **🔒 Privacy First**: Your data stays on your local network. Cloud upload is optional, encrypted, and fully under your control via **Rclone**.
- **🧠 Intelligent Discovery**: Auto-detects cameras on your local network using WS-Discovery (ONVIF) and subnet scanning.
- **☁️ Hybrid Cloud**: Seamlessly syncs footage to Google Drive, OneDrive, S3, or Dropbox without proprietary subscriptions.

---

## 🏗 System Architecture

Sentinela operates on a modular microservices architecture, ensuring stability and scalability.

```mermaid
graph TD
    subgraph "Local Network (Edge)"
        CAM[IP Cameras\nRTSP/ONVIF]
        
        subgraph "Sentinela Core"
            API[FastAPI Backend\n(Orchestrator)]
            MTX[MediaMTX Server\n(Streaming Engine)]
            REC[Recording Engine\n(Ffmpeg/IO)]
            SYNC[Cloud Sync Agent\n(Rclone Wrapper)]
        end
    end

    subgraph "Clients & Storage"
        WEB[Web Dashboard\n(React/Jinja2)]
        CLOUD[Cloud Storage\n(S3/Drive/Dropbox)]
    end

    CAM -->|RTSP Stream| MTX
    CAM -.->|Discovery| API
    MTX -->|WebRTC/HLS| WEB
    MTX -->|RTSP| REC
    REC -->|Files| SYNC
    SYNC -->|Encrypted Transfer| CLOUD
    API -->|Control| MTX
    API -->|Status| WEB
```

---

## ✨ Key Features

| Feature | Description | Technology |
| :--- | :--- | :--- |
| **High-Performance Streaming** | View multiple cameras simultaneously with negligible latency using WebRTC. | `MediaMTX` `WebRTC` |
| **Smart Recording** | Continuous 24/7 logging with auto-segmentation and retention policies (e.g., "Keep 7 days"). | `FFmpeg` `Python` |
| **Auto-Discovery** | Plug-and-play experience. Automatically finds ONVIF-compliant devices and open RTSP ports. | `WS-Discovery` `Scapy` |
| **Cloud Offload** | Redundant backup to any major cloud provider. Protects against local hardware theft/failure. | `Rclone` |
| **Secure Tunneling** | Access your dashboard remotely without dangerous port forwarding rules. | `Cloudflare Tunnel` |
| **Health Watchdog** | Self-healing processes ensure the system recovers automatically from network glitches. | `Systemd` / `AsyncIO` |

---

## 🚀 Quick Start

### Prerequisites
- **OS**: Windows 10/11 or modern Linux.
- **Python**: 3.10+.
- **Network**: Wired connection recommended for cameras.

### Installation (Automated)

We provide a turnkey setup script that handles dependencies (ffmpeg, rclone, mediamtx) automatically.

1. **Clone the Repository**
   ```bash
   git clone https://github.com/BIbEsfiha1/Sentinela.git
   cd sentinela
   ```

2. **Run the Installer**
   
   **Windows (PowerShell/CMD):**
   ```powershell
   .\setup.bat
   ```
   > This script will create a virtual environment, install Python requirements, and download necessary binaries to the `./tools` directory.

3. **Launch the System**
   ```bash
   python main.py
   ```
   The dashboard will automatically open at `http://localhost:8080`.

---

## ⚙ Configuration

Sentinela uses a strictly typed `config.yaml` for granular control.

<details>
<summary><b>Click to view detailed config.yaml documentation</b></summary>

```yaml
system:
  web_port: 8080              # Interface port
  mediamtx_api_port: 9997     # Internal API for streaming server
  default_username: admin     # Initial login
  default_password: 'changeme' # IMPORTANT: Change this!
  
recording:
  segment_duration: 1800      # 30 minutes per file
  retention_days: 7           # Delete files older than 7 days
  recordings_path: recordings # Local storage path

cloud:
  enabled: true
  provider: gdrive            # Options: gdrive, onedrive, s3, dropbox
  sync_interval_minutes: 60   # How often to offload data
  bandwidth_limit: 5M         # QoS to prevent network saturation

cameras:
  - name: "Front Door"
    url: "rtsp://user:pass@192.168.1.50:554/stream1"
    enabled: true
```
</details>

---

## 📡 REST API

For developers and integrators, Sentinela exposes a full Swagger/OpenAPI documentation.

- **Swagger UI**: Visit `/docs` (e.g., `http://localhost:8080/docs`)
- **ReDoc**: Visit `/redoc`

**Example Endpoint: List Cameras**
```http
GET /api/v1/cameras
```
```json
[
  {
    "id": "cam_01",
    "name": "Backyard",
    "status": "online",
    "stream_url": "http://localhost:8889/cam_01/publish"
  }
]
```

---

## 🛡 Security Best Practices

1. **Change Default Credentials**: Immediately update the `admin` password in `config.yaml`.
2. **Network Isolation**: Ideally, keep your IP cameras on a separate VLAN to prevent unauthorized access to your main network.
3. **Tunneling**: If accessing remotely, prefer the built-in Tunnel feature or a VPN over port forwarding.

---

## 🤝 Contributing

We welcome contributions from the community! Please read our [Contributing Guide](CONTRIBUTING.md) to get started.

1. **Fork** the repository.
2. Create a **Feature Branch** (`git checkout -b feature/AmazingFeature`).
3. **Commit** your changes (`git commit -m 'Add AmazingFeature'`).
4. **Push** to the branch.
5. Open a **Pull Request**.

---

<div align="center">

**Sentinela Project** • *Watching over what matters most.*

Copyright © 2026. Distributed under the MIT License.

</div>
