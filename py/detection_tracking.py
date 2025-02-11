import threading
import numpy as np
import time
import json
import os
import datetime
import collections
import network
from ptz_network_lib import PTZCamera
import logging

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s: %(message)s")


class BBoxCameraPoseConverter:

  def __init__(self, img_width, img_height, fx_scale=175, fy_scale=13):
    self.img_width = img_width
    self.img_height = img_height
    self.cx = img_width / 2.0
    self.cy = img_height / 2.0
    self.fx_scale = fx_scale
    self.fy_scale = fy_scale

  def convert(self, bbox, cam_pose):
    x0, y0, x1, y1 = bbox
    x_center = (x0 + x1) / 2.0
    y_center = (y0 + y1) / 2.0

    # Calculate effective focal lengths using intrinsic scaling factors
    fx = cam_pose["zoom"] * self.fx_scale
    fy = cam_pose["zoom"] * self.fy_scale

    # Calculate angular offsets using proper focal lengths
    delta_pan = np.arctan((x_center - self.cx) / fx)
    delta_tilt = np.arctan((y_center - self.cy) / fy)

    new_pan = cam_pose["pan"] + np.degrees(delta_pan)
    new_tilt = cam_pose["tilt"] + np.degrees(delta_tilt)

    # Zoom out if x0 > x1
    if x0 < x1:
      scale = self.img_width / (x1 - x0)
    else:
      scale = (x0 - x1) / self.img_width

    new_zoom = cam_pose["zoom"] * scale

    return {"pan": new_pan, "tilt": new_tilt, "zoom": new_zoom}


class DetectionPositionMatcher:
  """
    Matches detection frames with corresponding PTZ camera poses.
  """

  def __init__(self, camera: PTZCamera, frame_data_port: int, min_dt_ms: int,
               frame_to_pose_latency_ms: int, detection_pose_folder_path: str,
               bbox_to_pose_converter: BBoxCameraPoseConverter) -> None:
    # Convert milliseconds to seconds for internal consistency.
    self.min_dt = min_dt_ms / 1000.0
    self.frame_to_pose_latency = frame_to_pose_latency_ms / 1000.0
    file_name = "pose_detection_matches_" + datetime.datetime.now().strftime(
        "%Y%m%d_%H%M%S") + ".json"
    self.detection_pose_file_path = os.path.join(detection_pose_folder_path,
                                                 file_name)

    self.camera = camera
    self.bbox_to_pose_converter = bbox_to_pose_converter

    self.sock = network.create_udp_socket(frame_data_port, '127.0.0.1')
    self.cam_detection_data_queue = collections.deque(maxlen=1000)
    self.cam_pose_queue = collections.deque(maxlen=1000)
    self.detection_pose_match_queue = collections.deque(maxlen=100)

    threading.Thread(target=self.collect_detection_data, daemon=True).start()
    threading.Thread(target=self.collect_camera_poses, daemon=True).start()
    threading.Thread(target=self.match_detection_and_pose, daemon=True).start()

  def collect_detection_data(self) -> None:
    while True:
      data, _ = network.get_json_and_address(self.sock)
      if not data:
        time.sleep(0.1)
        continue
      # Ensure a timestamp exists in the detection data.
      if "timestamp" not in data:
        data["timestamp"] = time.time()
      self.cam_detection_data_queue.append(data)

  def collect_camera_poses(self) -> None:
    while True:
      pose = self.camera.get_status()
      if not pose:
        time.sleep(0.1)
        continue
      pose["timestamp"] = time.time()
      self.cam_pose_queue.append(pose)

  def match_detection_and_pose(self) -> None:
    while True:
      if not self.cam_detection_data_queue or not self.cam_pose_queue:
        time.sleep(0.01)
        continue

      # Always work with the oldest detection and pose (FIFO order)
      detection = self.cam_detection_data_queue[0]
      pose = self.cam_pose_queue[0]

      # Adjust difference by expected latency (all in seconds)
      dt = pose["timestamp"] - detection[
          "timestamp"] - self.frame_to_pose_latency

      if np.abs(dt) <= self.min_dt:
        detections = self.cam_detection_data_queue.popleft()
        pose = self.cam_pose_queue.popleft()
        self.add_poses_to_detections(detections, pose)
        self.detection_pose_match_queue.append(detections)
        logging.info(f"Nr of matches: {len(self.detection_pose_match_queue)}, "
                     f"buffer sizes: {len(self.cam_detection_data_queue)}, "
                     f"{len(self.cam_pose_queue)}")
        # self.write_detection_pose_pairs()
      elif dt < -self.min_dt:
        self.cam_pose_queue.popleft()
      else:
        self.cam_detection_data_queue.popleft()

  def write_detection_pose_pairs(self) -> None:
    with open(self.detection_pose_file_path, "w") as fp:
      fp.write(json.dumps(list(self.detection_pose_match_queue), indent=2))

  def add_poses_to_detections(self, detections, cam_pose) -> dict:
    detections["poses"] = []
    for bbox in detections["bboxes"]:
      detections["poses"].append(
          self.bbox_to_pose_converter.convert(bbox, cam_pose))
