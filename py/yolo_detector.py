import numpy as np
import cv2
from ultralytics import YOLO
import matplotlib.pyplot as plt


class Detector:
  """YOLO Object detection."""

  def __init__(self,
               model,
               class_ids_filter=None,
               yolo_min_confidence=1.0,
               cmap_name='nipy_spectral'):
    self.model = YOLO(model)
    self.detections = []
    self.class_ids_filter = class_ids_filter
    self.yolo_min_confidence = yolo_min_confidence
    self.class_id_names = None
    self.colors = None
    self.cmap_name = cmap_name

  def detect(self, img):
    results = self.model.predict(source=img.copy(),
                                 save=False,
                                 save_txt=False,
                                 verbose=False)
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
    mask = scores >= self.yolo_min_confidence
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

  def draw_bboxes(self, img):
    for bbox, class_id, score in self.detections:
      x1, y1, x2, y2 = bbox
      label = f"{self.class_id_names[class_id]}: {score:.2f}"
      color = [int(c) for c in self.colors[class_id]]
      cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
      cv2.putText(img, label, (x1, max(y1 - 10, 0)), cv2.FONT_HERSHEY_SIMPLEX,
                  0.5, color, 2)
    return img
