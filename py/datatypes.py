import numpy as np
import dataclasses


@dataclasses.dataclass
class DetectionFrame:

  image_frame: np.ndarray
  bboxes: np.ndarray = dataclasses.field(
      default_factory=lambda: np.empty((0, 4), dtype=np.int32))
  class_ids: np.ndarray = dataclasses.field(
      default_factory=lambda: np.empty(0, dtype=np.int32))
  scores: np.ndarray = dataclasses.field(
      default_factory=lambda: np.empty(0, dtype=np.float32))
  timestamp: float = 0.0

  @property
  def has_detections(self) -> bool:
    return len(self.bboxes) > 0

  def add_detection(self, bbox, class_id, score):
    self.bboxes = np.vstack([self.bboxes, bbox])
    self.class_ids = np.append(self.class_ids, class_id)
    self.scores = np.append(self.scores, score)

  def apply_min_confidence_filter(self, min_confidence):
    mask = self.scores >= min_confidence

    self.bboxes = self.bboxes[mask]
    self.class_ids = self.class_ids[mask]
    self.scores = self.scores[mask]

  def apply_class_filter(self, accepted_class_ids):
    if accepted_class_ids is None:
      return

    mask = np.isin(self.class_ids, accepted_class_ids)

    self.bboxes = self.bboxes[mask]
    self.class_ids = self.class_ids[mask]
    self.scores = self.scores[mask]

  def to_dict(self):
    return {
        "bboxes": self.bboxes.tolist(),
        "class_ids": self.class_ids.tolist(),
        "scores": self.scores.tolist(),
        "timestamp": self.timestamp,
    }
