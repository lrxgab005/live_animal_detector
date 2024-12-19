from ultralytics import YOLO
from collections import defaultdict
import numpy as np
import cv2


class Detector:
  """YOLO Object detection."""

  def __init__(self, model, class_ids_filter=None):
    self.model = YOLO(model)
    self.class_ids_filter = class_ids_filter
    self.class_id_names = None

  def detect(self, img):
    results = self.model.predict(source=img.copy(),
                                 save=False,
                                 save_txt=False,
                                 verbose=False)
    result = results[0]

    self.bboxes = np.array(result.boxes.xyxy.cpu(), dtype="int")
    self.class_ids = np.array(result.boxes.cls.cpu(), dtype="int")
    self.scores = np.array(result.boxes.conf.cpu(), dtype="float").round(2)
    self.class_id_names = result.names

  def draw_bboxes(self, img):
    for bbox, class_id, score in zip(self.bboxes, self.class_ids, self.scores):
      x1, y1, x2, y2 = bbox
      label = f"{self.class_id_names[class_id]}: {score:.2f}"
      color = (0, 255, 0)
      cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
      cv2.putText(img, label, (x1, max(y1 - 10, 0)), cv2.FONT_HERSHEY_SIMPLEX,
                  0.5, color, 2)

    return img
