"""Pydantic models for Sentinela."""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class CameraStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    RECORDING = "recording"
    ERROR = "error"


class CameraModel(BaseModel):
    id: str
    name: str
    ip: str
    port: int = 554
    username: str = "admin"
    password: str = ""
    channel: int = 1
    stream: int = 0  # 0=main, 1=sub
    brand: str = "icsee"  # auto, intelbras, hikvision, icsee, generic, onvif
    codec: str = "h265"  # auto, h264, h265
    enabled: bool = True
    status: CameraStatus = CameraStatus.OFFLINE


class CameraAdd(BaseModel):
    name: str
    ip: str
    port: int = 554
    username: str = "admin"
    password: str = ""
    channel: int = 1
    stream: int = 0
    brand: str = "auto"
    codec: str = "auto"


class CameraUpdate(BaseModel):
    name: Optional[str] = None
    ip: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    channel: Optional[int] = None
    stream: Optional[int] = None
    brand: Optional[str] = None
    codec: Optional[str] = None
    enabled: Optional[bool] = None


class RecordingSettings(BaseModel):
    segment_duration: int = Field(default=1800, description="Duration in seconds (default 30 min)")
    retention_days: int = Field(default=7, description="Days to keep recordings")
    recordings_path: str = "recordings"


class CloudProvider(str, Enum):
    GDRIVE = "gdrive"
    ONEDRIVE = "onedrive"
    DROPBOX = "dropbox"
    S3 = "s3"
    NONE = "none"


class CloudSettings(BaseModel):
    provider: CloudProvider = CloudProvider.NONE
    enabled: bool = False
    sync_interval_minutes: int = 60
    bandwidth_limit: str = "5M"
    remote_name: str = "sentinela"
    remote_path: str = "Sentinela"


class TunnelMode(str, Enum):
    DISABLED = "disabled"
    QUICK = "quick"
    NAMED = "named"


class TunnelSettings(BaseModel):
    mode: TunnelMode = TunnelMode.DISABLED
    public_url: Optional[str] = None
    hostname: Optional[str] = None
    tunnel_name: Optional[str] = None


class SystemSettings(BaseModel):
    web_port: int = 8080
    mediamtx_api_port: int = 9997
    mediamtx_webrtc_port: int = 8889
    default_username: str = "admin"
    default_password: str = "12345678"
    auto_start: bool = False
    language: str = "pt-BR"
    first_run: bool = True


class AppConfig(BaseModel):
    system: SystemSettings = SystemSettings()
    recording: RecordingSettings = RecordingSettings()
    cloud: CloudSettings = CloudSettings()
    tunnel: TunnelSettings = TunnelSettings()
    cameras: list[CameraModel] = []


class DiscoveredCamera(BaseModel):
    ip: str
    port: int = 554
    source: str = "scan"  # "onvif", "scan", "manual"
    name: Optional[str] = None
    already_added: bool = False


class SystemStatus(BaseModel):
    cameras_total: int = 0
    cameras_recording: int = 0
    cameras_online: int = 0
    disk_total_gb: float = 0
    disk_used_gb: float = 0
    disk_free_gb: float = 0
    recordings_size_gb: float = 0
    cpu_percent: float = 0
    ram_percent: float = 0
    cloud_connected: bool = False
    tunnel_active: bool = False
    tunnel_url: Optional[str] = None
    uptime_seconds: int = 0
