import cv2
import time
import logging
import config
import yolo_detector
from queue import Queue
import threading
import argparse


class CameraStreamer:
  """
    CameraStreamer handles live streaming from a given RTSP URL.
  """

  def __init__(self, url):
    self.url = url
    self.cap = cv2.VideoCapture(url)
    if not self.cap.isOpened():
      raise RuntimeError("Cannot open stream")

  def read_frame(self):
    ret, frame = self.cap.read()
    if not ret:
      return None
    return frame

  def release(self):
    self.cap.release()


class StatsMeasurer:
  """
    StatsMeasurer keeps track of FPS and frame latency.
  """

  def __init__(self):
    self.last_time = time.time()
    self.frame_count = 0
    self.fps = 0.0

  def update(self, latency_ms):
    self.frame_count += 1
    elapsed = time.time() - self.last_time
    if elapsed >= 1.0:
      self.fps = self.frame_count / elapsed
      logging.info(f"FPS: {self.fps:.2f}")
      self.frame_count = 0
      self.last_time = time.time()
    logging.debug(f"Frame latency: {latency_ms:.2f} ms")


def frame_reader(streamer, frame_queue):
  """
    Continuously read frames from the streamer and put them into the queue.
  """
  while True:
    frame = streamer.read_frame()
    if frame is None:
      break
    frame_queue.put(frame)
  frame_queue.put(None)


def main():
  parser = argparse.ArgumentParser(description='Live stream processing.')
  parser.add_argument(
      '--force_real_time',
      action='store_true',
      help='If set, only the latest frame is shown (skips queued frames).')
  args = parser.parse_args()

  logging.basicConfig(level=logging.INFO,
                      format="%(asctime)s %(levelname)s: %(message)s")
  logging.info(f"Initialized {config.CAMERA_URL}")

  streamer = CameraStreamer(config.CAMERA_URL)
  detector = yolo_detector.Detector(
      config.YOLO_MODEL,
      config.YOLO_CLASS_IDS,
      config.YOLO_MIN_CONFIDENCE,
  )
  stats = StatsMeasurer()

  frame_queue = Queue(maxsize=30)
  t = threading.Thread(target=frame_reader,
                       args=(streamer, frame_queue),
                       daemon=True)
  t.start()

  while True:
    start_time = time.time()
    frame = frame_queue.get(timeout=1)
    while not frame_queue.empty() and args.force_real_time:
      frame = frame_queue.get_nowait()

    if frame is None:
      break

    latency = (time.time() - start_time) * 1000.0
    stats.update(latency)

    detector.detect(frame)
    detector.draw_bboxes(frame)
    cv2.imshow("Live Stream", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
      break

  streamer.release()
  cv2.destroyAllWindows()


if __name__ == "__main__":
  main()
