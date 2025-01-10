# Live Animal Detector from Camera Feed

The Live Animal Detector is a distributed system that processes network camera video streams through a YOLO (You Only Look Once) object detection model. The server analyzes frames in real-time to detect and classify a wide range of objects and animals. Based on configurable detection confidence thresholds and object classes, the system can trigger notifications to a remote audio server for alarm playback through stereo speakers. This architecture enables efficient wildlife monitoring and automated response capabilities.

## Features

- **Real-time Processing**: Analyzes camera feeds frame by frame using single-shot detection
- **YOLO Detection**: Implements YOLO (You Only Look Once) object detection model
- **Detection Filters**: Configurable confidence thresholds and object class filtering
- **PTZ Camera Interface**: REST-based control system for PTZ camera operations
- **Distributed Architecture**: Web-based communication between detection and audio nodes
- **HTTP REST APIs**: Standardized interfaces for system components and control
- **Remote Object Detection**: Ability to offload neural network computation to remote GPU servers

## Server Archicteture



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
python py/ptz_nav.py
```

### On Remote Audio Server

**Start Audio Player**

```sh
python py/remote_player.py
```
