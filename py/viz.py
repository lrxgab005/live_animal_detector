from typing import List, Tuple
import numpy as np
import cv2
import matplotlib.pyplot as plt
import datatypes as dt


class FrameDrawer:

  def __init__(self,
               class_id_names: List[str],
               cmap_name: str = 'nipy_spectral') -> None:
    self.class_id_names = class_id_names
    self.cmap_name = cmap_name
    self.colors = self.generate_colors(len(self.class_id_names))

  def draw_detections(self,
                      detection_frame: 'dt.DetectionFrame',
                      bold: bool = False) -> None:
    for bbox, class_id, score in zip(detection_frame.bboxes,
                                     detection_frame.class_ids,
                                     detection_frame.scores):
      self.draw_bbox(detection_frame.image_frame, bbox, class_id, score, bold)

  def draw_bbox(self,
                img: np.ndarray,
                bbox: Tuple[int, int, int, int],
                class_id: int,
                score: float,
                bold: bool = False) -> None:
    x1, y1, x2, y2 = bbox
    label = f"{self.class_id_names[class_id]}: {score:.2f}"
    color = [int(c) for c in self.colors[class_id]]
    line_thickness = 1 if not bold else 4
    cv2.rectangle(img, (x1, y1), (x2, y2), color, line_thickness)
    cv2.putText(img, label, (x1, max(y1 - 10, 0)), cv2.FONT_HERSHEY_SIMPLEX,
                0.5, color, 2)

  def generate_colors(self, nr_colors: int = 80) -> np.ndarray:
    cmap = plt.get_cmap(self.cmap_name)
    indices = np.linspace(0, 1, nr_colors)
    return (np.array([cmap(i)[:3] for i in indices]) * 255).astype("uint8")
