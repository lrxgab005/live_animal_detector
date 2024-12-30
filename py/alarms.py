import logging
import pygame
import time
import datatypes as dt


class Alarm:

  def __init__(
      self,
      alarm_triggers={},
      class_id_names={},
      notificaion_sound_file=None,
      alarm_cool_down_s=5,
  ):
    self.alarm_triggers = alarm_triggers
    self.class_id_names = class_id_names
    self.notificaion_sound_file = notificaion_sound_file
    if notificaion_sound_file:
      pygame.mixer.init()
    self.alarm_cool_down_s = alarm_cool_down_s
    self.last_alarm_s = time.time()

  def __call__(self, detection_frame):
    alarm_detetions = dt.DetectionFrame(detection_frame.image_frame)
    for bbox, class_id, score in zip(detection_frame.bboxes,
                                     detection_frame.class_ids,
                                     detection_frame.scores):

      if self.check_alarm(class_id, score):
        alarm_detetions.add_detection(bbox, class_id, score)

    if alarm_detetions.has_detections:
      self.last_alarm_s = time.time()
      pygame.mixer.Sound(self.notificaion_sound_file).play()

    return alarm_detetions

  def check_alarm(self, class_id, score):
    if class_id not in self.alarm_triggers:
      return False
    if score < self.alarm_triggers[class_id]:
      return False
    if self.alarm_cool_down_s > time.time() - self.last_alarm_s:
      return False

    logging.info(f"Found a {self.class_id_names[class_id]}!")

    return True
