# Live Animal Detector from Camera Feed

The Live Animal Detector is a powerful tool designed to detect and identify animals in real-time from a camera feed using the YOLO (You Only Look Once) object detection algorithm. This project leverages advanced machine learning techniques to provide accurate and efficient animal detection, making it ideal for wildlife monitoring, security, and research applications.

## Features

- **Real-time Detection**: Processes live camera feeds to detect animals in real-time.
- **High Accuracy**: Utilizes the YOLO algorithm for precise object detection.
- **Customizable Filters**: Apply confidence and class filters to refine detection results.
- **PTZ Camera Control**: Control interface for a PTZ camera with REST server interface

## Setup

To set up the environment and install the necessary dependencies, follow these steps:

### 1) Install git LFS
Install git LFS for audio files (used for storing large audio files efficiently):

**Mac**

```sh
brew install git-lfs
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
virtualenv env
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

## Run 

### On Streaming PC

**Start Stream**

```
python py/stream_camera.py --force_real_time
```

**Start Navigation UI**

```
python py/ptz_nav.py
```

### On Remote Audio Server

**Start Audio Player**

```
python py/remote_player.py
```
