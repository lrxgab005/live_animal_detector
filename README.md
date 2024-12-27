# Live Animal Detector from Camera Feed

## Setup

```
virtualenv env
. env/bin/activate
pip install -r requirements.txt
```

## Run

Start Stream

```
python py/stream_camera.py --force_real_time
```

Start Navigation UI

```
python py/ptz_nav.py
```