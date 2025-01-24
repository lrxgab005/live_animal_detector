# Live Animal Detector from Camera Feed

A distributed system that processes network camera video streams using YOLO object detection for real-time wildlife monitoring and interaction. Combines PTZ camera tracking with configurable audio responses through remote-controlled speakers.

## Server Architecture

The system consists of three interconnected components:

```
+-----------------+         +-----------------+
|  Detection Node |         |   Audio Node    |
|                 |  HTTP   |                 |
|  - YOLO Model   |-------->|  - REST API     |
|  - PTZ Control  |         |  - Audio Player |
+--------+--------+         +-----------------+
         |
         | RTSP + HTTP
         v
+------------------+
|   PTZ Camera     |
|  - Video Feed    |
|  - Movement API  |
+------------------+
```

### **Object Detection Server**
- Captures RTSP video stream from network camera
- Runs YOLO object detection on captured frames
- Sends alarm triggers via HTTP POST to Audio Server
- Controls PTZ camera via HTTP/REST with digest authentication

### **Audio Server**
- REST API endpoints:
  - POST /play - Plays specified audio file
  - POST /stop - Stops current playback
- Manages local audio files stored on git LFS
- Controls system audio output via pygame

### **PTZ Network Camera**
- Provides RTSP video stream
- Sends HTTP/REST commands for PTZ control
- Uses digest authentication for API security

### Communication Protocols
- Camera Stream: RTSP over TCP
- PTZ Control: HTTP REST with digest authentication
- Audio Control: HTTP REST (JSON)

## Setup

To set up the environment and install the necessary dependencies, follow these steps:

### 1) Install git LFS
Install git LFS for audio files (used for storing large audio files efficiently):

**Mac**

```sh
brew install git-lfs
brew install tesseract
```

**Windows:**

Download and install from the [Git LFS website](https://git-lfs.com/).

**Raspbian**

```sh
sudo apt-get install git-lfs
```

### 2) Enable Git LFS

```sh
git lfs install
git lfs pull
```

### 3) Setup Virtual Env:

```sh
python3.10 -m venv env
. env/bin/activate
```

### 3) Install Python Packages

**On Video Stream PC**

```sh
pip install -r requirements.txt
```

**On Audio Server**
```sh
pip install -r requirements_audio_server.txt
```

### 4) Create camera configs

Create a camera config file for each camera you want to interface with.

```sh
python py/create_cam_config.py
```

## Run 

### On Streaming PC

**Start Stream**

```sh
python py/stream_camera.py --camera_config PATH_TO_CAM_CONFIG
```

**Start Navigation UI**

```sh
python py/ptz_nav.py --camera_config PATH_TO_CAM_CONFIG
```

### On Remote Audio Server

**Start Audio Player**

```sh
tmux new-session -d -s audio_player
./auto_restarter.sh py/remote_player.py
```
