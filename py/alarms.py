from typing import Dict, Tuple, Optional
import logging
import pygame
import time
import datatypes as dt
import requests
import config
import os

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s: %(message)s")


class Alarm:

  def __init__(self,
               alarm_triggers: Dict[int, float] = {},
               class_id_names: Dict[int, str] = {},
               notificaion_sound_file_name: Optional[str] = None,
               alarm_sound_file_name: Optional[str] = None,
               alarm_cool_down_s: float = 5,
               remote_player_url: str = "http://127.0.0.1:5000") -> None:
    self.alarm_triggers = alarm_triggers
    self.class_id_names = class_id_names

    self.notificaion_sound_file_path: Optional[str] = None
    if notificaion_sound_file_name:
      pygame.mixer.init()
      self.notificaion_sound_file_path = os.path.join(
          config.SOUNDS_PATH, notificaion_sound_file_name)

    self.alarm_sound_file_name = alarm_sound_file_name
    self.alarm_cool_down_s = alarm_cool_down_s
    self.last_alarm_s = time.time()
    self.remote_player_url = remote_player_url

  def __call__(self, detection_frame: dt.DetectionFrame) -> dt.DetectionFrame:
    alarm_detetions = dt.DetectionFrame(
      image_frame=detection_frame.image_frame,
      timestamp=detection_frame.timestamp,
    )
    alarm = False
    for bbox, class_id, score in zip(detection_frame.bboxes,
                                     detection_frame.class_ids,
                                     detection_frame.scores):

      if self.check_alarm(class_id, score):
        alarm_detetions.add_detection(bbox, class_id, score)
        if self.alarm_cool_down_s > time.time() - self.last_alarm_s:
          alarm = True

    if alarm:
      self.last_alarm_s = time.time()
      if self.notificaion_sound_file_path:
        logging.info(
            f"Playing notification sound: {self.notificaion_sound_file_path}")
        pygame.mixer.Sound(self.notificaion_sound_file_path).play()

      if self.alarm_sound_file_name:
        logging.info(f"Playing alarm sound: {self.alarm_sound_file_name}")
        self.play_sound_on_remote(self.alarm_sound_file_name)

    return alarm_detetions

  def check_alarm(self, class_id: int, score: float) -> bool:
    if class_id not in self.alarm_triggers:
      return False
    if score < self.alarm_triggers[class_id]:
      return False

    logging.info(f"Found a {self.class_id_names[class_id]}!")

    return True

  def play_sound_on_remote(self, sound_file_name: str) -> None:
    try:
      response = requests.post(f"{self.remote_player_url}/play",
                               json={"file_name": sound_file_name})
      if response.status_code != 200:
        logging.error(f"Failed to play sound: {response.text}")
    except Exception as e:
      logging.error(f"Error calling remote player: {e}")
