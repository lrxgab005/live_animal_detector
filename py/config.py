from typing import Dict, Optional, Any
import os
import json
import numpy as np
import matplotlib.pyplot as plt


def generate_colors(nr_colors: int) -> np.ndarray:
  cmap = plt.get_cmap('nipy_spectral')
  indices = np.linspace(0, 1, nr_colors)
  return (np.array([cmap(i)[:3] for i in indices]) * 255).astype("uint8")


# Audio Server Settings
HOST: str = "127.0.0.1"
PORT: str = "5000"
REMOTE_PLAYER_URL: str = f"http://{HOST}:{PORT}"

# Frame Data UDP Settings
FRAME_DATA_PORT: int = 4545

# Frame detection settings
MIN_DETECTION_POSE_DT_MS: int = 500
FRAME_TO_POSE_LATENCY_MS: int = -1350

# Camera Intrinsics
IMG_WIDTH: int = 1920
IMG_HEIGHT: int = 1080
FX_SCALE: int = 175
FY_SCALE: int = 17

# Alarm Settings
ALARM_TRIGGERS: Dict[int, float] = {
    0: 0.0,
    2: 0.8,
    14: 0.8,
    15: 0.0,
    16: 0.0,
    17: 0.0,
    18: 0.0,
    19: 0.0,
    21: 0.0,
    22: 0.0,
    23: 0.0,
}
ALARM_NAMES: Dict[int, str] = {
    0: "Human",
    2: "Car",
    14: "Bird",
    15: "cat",
    16: "Dog",
    17: "Horse",
    18: "Sheep",
    19: "Cow",
    21: "Bear",
    22: "Zebra",
    23: "Giraffe",
}
ALARM_COLORS: Dict[int, np.ndarray] = {
    class_id: color
    for class_id, color in zip(ALARM_TRIGGERS.keys(),
                               generate_colors(len(ALARM_TRIGGERS)))
}
NOTIFICATION_SOUND_FILE_NAME: Optional[str] = None  # "notification_00.mp3"
ALARM_SOUND_FILE_NAME: str = "notification_00.mp3"
ALARM_COOL_DOWN_S: int = 20

# YOLO Settings
YOLO_MODEL: str = "yolo11x.pt"  # yolo11n
YOLO_CLASS_IDS: Optional[list[int]] = None  # [0]
YOLO_MIN_CONFIDENCE: float = 0.5

# Paths
PY_PATH: str = os.path.dirname(os.path.abspath(__file__))
ROOT_PATH: str = os.path.dirname(PY_PATH)
DATA_PATH: str = os.path.join(ROOT_PATH, "data")
SOUNDS_PATH: str = os.path.join(DATA_PATH, "sounds")
IMGS_PATH: str = os.path.join(DATA_PATH, "images")
CAM_CONFIG_PATH: str = os.path.join(DATA_PATH, "cam_configs")
CAM_MOVE_SEQS_PATH: str = os.path.join(DATA_PATH, "cam_move_sequences")
CAM_DETECTIONS_PATH: str = os.path.join(DATA_PATH, "detections")

# Ensure paths are created if they don't exist
os.makedirs(SOUNDS_PATH, exist_ok=True)
os.makedirs(IMGS_PATH, exist_ok=True)
os.makedirs(CAM_CONFIG_PATH, exist_ok=True)

# Camera Settings
USER: Optional[str] = None
PASSWORD: Optional[str] = None
HOST: Optional[str] = None
PORT: Optional[str] = None
CHANNEL: Optional[str] = None
CAMERA_URL: Any = None


def load_cam_settings(file_path: str) -> None:
  global USER, PASSWORD, HOST, PORT, CHANNEL, CAMERA_URL

  with open(file_path, "r") as f:
    cam: Dict[str, str] = json.load(f)

  USER = cam["USER"]
  PASSWORD = cam["PASSWORD"]
  HOST = cam["HOST"]
  PORT = cam["PORT"]
  CHANNEL = cam["CHANNEL"]
  CAMERA_URL = (f'rtsp://{USER}:{PASSWORD}@{HOST}'
                f':{PORT}/Streaming/Channels/{CHANNEL}')


# Default to webcam if no config loaded
CAMERA_URL = 0
