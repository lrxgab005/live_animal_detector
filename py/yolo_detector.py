import numpy as np
from ultralytics import YOLO
import torch
import datatypes as dt
import logging


class Detector:

  def __init__(self, model):
    self.model = YOLO(model)
    self.class_id_names = self.model.names
    self.device = 'cpu'
    if torch.backends.mps.is_available():
      logging.info("Apple Silicon detected. Using GPU.")
      self.device = 'mps'

  def detect(self, img):
    results = self.model.predict(source=img.copy(),
                                 save=False,
                                 save_txt=False,
                                 verbose=False,
                                 device=self.device)
    result = results[0]

    bboxes = np.array(result.boxes.xyxy.cpu(), dtype="int")
    class_ids = np.array(result.boxes.cls.cpu(), dtype="int")
    scores = np.array(result.boxes.conf.cpu(), dtype="float")

    return dt.DetectionFrame(img, bboxes, class_ids, scores)
