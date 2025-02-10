import os
import json

# Audio Server Settings
HOST = "127.0.0.1"
PORT = "5000"
REMOTE_PLAYER_URL = f"http://{HOST}:{PORT}"

# Alarm Settings
ALARM_TRIGGERS = {
    0: 0.8,  # Human
    2: 0.8,  # Car
    14: 0.7,  # Bird
    16: 0.7,  # Dog
    17: 0.5,  # Horse
    18: 0.5,  # Sheep
    19: 0.5,  # Cow
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
