import numpy as np
import cv2
from ultralytics import YOLO
import matplotlib.pyplot as plt


class Detector:
  """YOLO Object detection."""

  def __init__(self, model, class_ids_filter=None, cmap_name='nipy_spectral'):
    self.model = YOLO(model)
    self.class_ids_filter = class_ids_filter
    self.class_id_names = None
    self.colors = None
    self.cmap_name = cmap_name

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

    if self.colors is None:
      num_classes = len(self.class_id_names)
      cmap = plt.get_cmap(self.cmap_name)
      indices = np.linspace(0, 1, num_classes)
      self.colors = (np.array([cmap(i)[:3]
                               for i in indices]) * 255).astype("uint8")

  def draw_bboxes(self, img):
    for bbox, class_id, score in zip(self.bboxes, self.class_ids, self.scores):
      x1, y1, x2, y2 = bbox
      label = f"{self.class_id_names[class_id]}: {score:.2f}"
      color = [int(c) for c in self.colors[class_id]]
      cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
      cv2.putText(img, label, (x1, max(y1 - 10, 0)), cv2.FONT_HERSHEY_SIMPLEX,
                  0.5, color, 2)
    return img
