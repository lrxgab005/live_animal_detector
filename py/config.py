import os
import json
import numpy as np
import matplotlib.pyplot as plt


def generate_colors(nr_colors):
  cmap = plt.get_cmap('nipy_spectral')
  indices = np.linspace(0, 1, nr_colors)
  return (np.array([cmap(i)[:3] for i in indices]) * 255).astype("uint8")


# Audio Server Settings
HOST = "127.0.0.1"
PORT = "5000"
REMOTE_PLAYER_URL = f"http://{HOST}:{PORT}"

# Frame Data UDP Settings
FRAME_DATA_PORT = 4545

# Frame detection settings
MIN_DETECTION_POSE_DT_MS = 500
FRAME_TO_POSE_LATENCY_MS = -900

# Camera Intrinsics
IMG_WIDTH = 1920
IMG_HEIGHT = 1080
FX_SCALE = 175
FY_SCALE = 17

# Alarm Settings
ALARM_TRIGGERS = {
    0: 0.8,
    2: 0.8,
    14: 0.7,
    16: 0.7,
    17: 0.5,
    18: 0.5,
    19: 0.5,
    20: 0.5,
}
ALARM_NAMES = {
    0: "Human",
    2: "Car",
    14: "Bird",
    16: "Dog",
    17: "Horse",
    18: "Sheep",
    19: "Cow",
    20: "Zebra",
}
ALARM_COLORS = {
    class_id: color
    for class_id, color in zip(ALARM_TRIGGERS.keys(),
                               generate_colors(len(ALARM_TRIGGERS)))
}
NOTIFICATION_SOUND_FILE_NAME = "notification_00.mp3"
ALARM_SOUND_FILE_NAME = "notification_00.mp3"
ALARM_COOL_DOWN_S = 20

# YOLO Settings
YOLO_MODEL = "yolo11x.pt"  # yolo11n
YOLO_CLASS_IDS = None  # [0]
YOLO_MIN_CONFIDENCE = 0.5

# Paths
PY_PATH = os.path.dirname(os.path.abspath(__file__))
ROOT_PATH = os.path.dirname(PY_PATH)
DATA_PATH = os.path.join(ROOT_PATH, "data")
SOUNDS_PATH = os.path.join(DATA_PATH, "sounds")
IMGS_PATH = os.path.join(DATA_PATH, "images")
CAM_CONFIG_PATH = os.path.join(DATA_PATH, "cam_configs")
CAM_MOVE_SEQS_PATH = os.path.join(DATA_PATH, "cam_move_sequences")
CAM_DETECTIONS_PATH = os.path.join(DATA_PATH, "detections")

# Ensure paths are created if they don't exist
os.makedirs(SOUNDS_PATH, exist_ok=True)
os.makedirs(IMGS_PATH, exist_ok=True)
os.makedirs(CAM_CONFIG_PATH, exist_ok=True)


def load_cam_settings(file_path):
  global USER, PASSWORD, HOST, PORT, CHANNEL, CAMERA_URL

  with open(file_path, "r") as f:
    cam = json.load(f)

  USER = cam["USER"]
  PASSWORD = cam["PASSWORD"]
  HOST = cam["HOST"]
  PORT = cam["PORT"]
  CHANNEL = cam["CHANNEL"]
  CAMERA_URL = (f'rtsp://{USER}:{PASSWORD}@{HOST}'
                f':{PORT}/Streaming/Channels/{CHANNEL}')


CAMERA_URL = 0  # Uses webcam by default
