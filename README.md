# Live Animal Detector from Camera Feed

The Live Animal Detector is a powerful tool designed to detect and identify animals in real-time from a camera feed using the YOLO (You Only Look Once) object detection algorithm. This project leverages advanced machine learning techniques to provide accurate and efficient animal detection, making it ideal for wildlife monitoring, security, and research applications.

## Features

- **Real-time Detection**: Processes live camera feeds to detect animals in real-time.
- **High Accuracy**: Utilizes the YOLO algorithm for precise object detection.
- **Customizable Filters**: Apply confidence and class filters to refine detection results.
- **PTZ Camera Control**: Control interface for a PTZ camera with REST server interface

## Setup

To set up the environment and install the necessary dependencies, follow these steps:

```sh
virtualenv env
. env/bin/activate
pip install -r requirements.txt
```

## Run

**Start Stream**

```
python py/stream_camera.py --force_real_time
```

**Start Navigation UI**

```
python py/ptz_nav.py
```
