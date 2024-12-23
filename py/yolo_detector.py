import numpy as np
import cv2
from ultralytics import YOLO
import matplotlib.pyplot as plt
import torch
import logging
import pygame
import time


class Detector:
  """YOLO Object detection."""

  def __init__(self,
               model,
               class_ids_filter=None,
               min_confidence=1.0,
               alarms={},
               notificaion_sound_file=None,
               alarm_cool_down_s=5,
               cmap_name='nipy_spectral'):
    self.model = YOLO(model)
    self.detections = []
    self.class_ids_filter = class_ids_filter
    self.min_confidence = min_confidence
    self.class_id_names = None
    self.colors = None
    self.cmap_name = cmap_name
    self.device = 'cpu'
    if torch.backends.mps.is_available():
      logging.info("Apple Silicon detected. Using GPU.")
      self.device = 'mps'

    self.alarms = alarms
    self.notificaion_sound_file = notificaion_sound_file
    if notificaion_sound_file:
      pygame.mixer.init()
    self.alarm_cool_down_s = alarm_cool_down_s
    self.last_alarm_s = time.time()

  def detect(self, img):
    results = self.model.predict(source=img.copy(),
                                 save=False,
                                 save_txt=False,
                                 verbose=False,
                                 device=self.device)
    result = results[0]
    self.class_id_names = result.names

    if self.colors is None:
      self.set_colors()

    bboxes = np.array(result.boxes.xyxy.cpu(), dtype="int")
    class_ids = np.array(result.boxes.cls.cpu(), dtype="int")
    scores = np.array(result.boxes.conf.cpu(), dtype="float").round(2)
    self.detections = zip(bboxes, class_ids, scores)

    bboxes, class_ids, scores = self.apply_min_confidence_filter(
        bboxes, class_ids, scores)
    bboxes, class_ids, scores = self.apply_class_filter(
        bboxes, class_ids, scores)

    self.detections = zip(bboxes, class_ids, scores)

  def apply_min_confidence_filter(self, bboxes, class_ids, scores):
    mask = scores >= self.min_confidence
    return bboxes[mask], class_ids[mask], scores[mask]

  def apply_class_filter(self, bboxes, class_ids, scores):
    if self.class_ids_filter is None:
      return bboxes, class_ids, scores
    mask = np.isin(class_ids, self.class_ids_filter)
    return bboxes[mask], class_ids[mask], scores[mask]

  def set_colors(self):
    num_classes = len(self.class_id_names)
    cmap = plt.get_cmap(self.cmap_name)
    indices = np.linspace(0, 1, num_classes)
    self.colors = (np.array([cmap(i)[:3]
                             for i in indices]) * 255).astype("uint8")

  def analyze_detections(self, img):
    alarm_sounded = False
    for bbox, class_id, score in self.detections:
      alarm = self.check_alarm(class_id, score)
      if alarm:
        alarm_sounded = True
      self.draw_bbox(img, bbox, class_id, score, alarm)
    return alarm_sounded

  def draw_bbox(self, img, bbox, class_id, score, fill=False):
    x1, y1, x2, y2 = bbox
    label = f"{self.class_id_names[class_id]}: {score:.2f}"
    color = [int(c) for c in self.colors[class_id]]
    line_thickness = 1 if not fill else 4
    cv2.rectangle(img, (x1, y1), (x2, y2), color, line_thickness)
    cv2.putText(img, label, (x1, max(y1 - 10, 0)), cv2.FONT_HERSHEY_SIMPLEX,
                0.5, color, 2)

  def check_alarm(self, class_id, score):
    if class_id not in self.alarms:
      return False
    if score < self.alarms[class_id]:
      return False
    if self.alarm_cool_down_s > time.time() - self.last_alarm_s:
      return False
    self.last_alarm_s = time.time()

    logging.info(f"Found a {self.class_id_names[class_id]}!")

    if self.notificaion_sound_file:
      pygame.mixer.Sound(self.notificaion_sound_file).play()

    return True
