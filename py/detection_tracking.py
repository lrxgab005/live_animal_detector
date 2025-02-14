import threading
import numpy as np
import time
import json
import os
import datetime
import collections
import network
from ptz_network_lib import PTZCamera
from scipy.ndimage import gaussian_filter
import logging

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s: %(message)s")


class DynamicHeatmap:
  """
    Heatmap for tracking object presence in tilt-yaw space with improved consistency,
    boundary handling, and vectorized localized decay.
  """

  def __init__(self,
               pan_bins: int = 360,
               tilt_bins: int = 100,
               global_decay: float = 0.99,
               local_decay: float = 0.8,
               motion_blur: float = 1,
               max_zoom: float = 200,
               tilt_range: list = [1, 10],
               pan_range: list = [2, 50]) -> None:
    self.heatmap = np.zeros((pan_bins, tilt_bins))
    self.global_decay = global_decay
    self.local_decay = local_decay
    self.motion_blur = motion_blur
    self.pan_bins = pan_bins
    self.tilt_bins = tilt_bins
    self.total_bins = tilt_bins * pan_bins
    self.max_zoom = max_zoom
    self.pan_area_range = pan_range
    self.tilt_area_range = tilt_range

  def pan_tilt_to_bin(self, pan: float, tilt: float) -> tuple:
    p_idx = int((pan % 360) / 360 * self.pan_bins)
    t_idx = int((tilt + 90) / 180 * self.tilt_bins)
    p_idx = np.clip(p_idx, 0, self.pan_bins - 1)
    t_idx = np.clip(t_idx, 0, self.tilt_bins - 1)
    return p_idx, t_idx

  def bin_to_pan_tilt(self, p_idx: int, t_idx: int) -> tuple:
    pan = (p_idx / self.pan_bins) * 360
    tilt = (t_idx / self.tilt_bins) * 180 - 90
    return pan, tilt

  def get_heatval_at_pan_tilt(self, pan: float, tilt: float) -> float:
    p_idx, t_idx = self.pan_tilt_to_bin(pan, tilt)
    return self.heatmap[p_idx, t_idx]

  def convertPoseToBinArea(self, pose: dict) -> tuple:
    pan_width = np.interp((self.max_zoom - pose["zoom"]), [0, self.max_zoom],
                          self.pan_area_range)
    tilt_height = np.interp((self.max_zoom - pose["zoom"]), [0, self.max_zoom],
                            self.tilt_area_range)

    pan_min = pose["pan"] - pan_width / 2
    pan_max = pose["pan"] + pan_width / 2
    tilt_min = pose["tilt"] - tilt_height / 2
    tilt_max = pose["tilt"] + tilt_height / 2

    p_min, t_min = self.pan_tilt_to_bin(pan_min, tilt_min)
    p_max, t_max = self.pan_tilt_to_bin(pan_max, tilt_max)

    bins = []
    for p_idx in range(p_min, p_max):
      for t_idx in range(t_min, t_max):
        bins.append((p_idx, t_idx))

    return bins

  def update(self, detections: dict, camera_pose: dict) -> None:
    self.heatmap *= self.global_decay  # Global decay

    # # Decay over camera view area
    # decay_bins = self.convertPoseToBinArea(camera_pose)
    # decay_scale = len(decay_bins) / self.total_bins
    # self.heatmap[decay_bins] *= self.local_decay * decay_scale  # Local decay

    for pose, score in zip(detections["poses"], detections["scores"]):
      p_idx, t_idx = self.pan_tilt_to_bin(pose["pan"], pose["tilt"])
      self.heatmap[p_idx, t_idx] += score

    self.heatmap = gaussian_filter(self.heatmap, sigma=self.motion_blur)

  def get_map(self) -> np.ndarray:
    return self.heatmap

  def get_norm_heatval(self, p_idx, t_idx) -> float:
    # return self.heatmap[p_idx, t_idx] / np.max(self.heatmap)
    return np.clip(self.heatmap[p_idx, t_idx], 0, 1)

  def get_pan_tilt_heat_map(self) -> dict:
    pan_tilt_map = {}
    for p_idx in range(self.pan_bins):
      for t_idx in range(self.tilt_bins):
        heat = self.get_norm_heatval(p_idx, t_idx)
        if heat < 0.01:
          continue
        pan, tilt = self.bin_to_pan_tilt(p_idx, t_idx)
        pan_tilt_map[(pan, tilt)] = np.clip(self.heatmap[p_idx, t_idx], 0, 1)
    return pan_tilt_map


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

    new_zoom = cam_pose["zoom"] * scale * 0.1

    return {"pan": new_pan, "tilt": new_tilt, "zoom": new_zoom}


class DetectionPositionMatcher:
  """
    Matches detection frames with corresponding PTZ camera poses.
  """

  def __init__(self,
               camera: PTZCamera,
               frame_data_port: int,
               min_dt_ms: int,
               frame_to_pose_latency_ms: int,
               detection_pose_folder_path: str,
               bbox_to_pose_converter: BBoxCameraPoseConverter,
               write_detections: bool = False) -> None:
    # Convert milliseconds to seconds for internal consistency.
    self.min_dt = min_dt_ms / 1000.0
    self.frame_to_pose_latency = frame_to_pose_latency_ms / 1000.0
    file_name = "pose_detection_matches_" + datetime.datetime.now().strftime(
        "%Y%m%d_%H%M%S") + ".json"
    self.detection_pose_file_path = os.path.join(detection_pose_folder_path,
                                                 file_name)

    self.camera = camera
    self.bbox_to_pose_converter = bbox_to_pose_converter
    self.write_detections = write_detections

    self.sock = network.create_udp_socket(frame_data_port, '127.0.0.1')
    self.cam_detection_data_queue = collections.deque(maxlen=1000)
    self.cam_pose_queue = collections.deque(maxlen=1000)
    self.curr_pose = {}
    self.detection_pose_match_queue = collections.deque(maxlen=100)

    self.heat_map = DynamicHeatmap()

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
      self.curr_pose = pose
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
        cam_pose = self.cam_pose_queue.popleft()
        self.add_poses_to_detections(detections, cam_pose)
        self.heat_map.update(detections, cam_pose)
        self.detection_pose_match_queue.append(detections)
        logging.debug(
            f"Nr of matches: {len(self.detection_pose_match_queue)}, "
            f"buffer sizes: {len(self.cam_detection_data_queue)}, "
            f"{len(self.cam_pose_queue)}")
        if self.write_detections:
          self.write_detection_pose_pairs()
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
