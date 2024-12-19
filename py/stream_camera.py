import cv2
import time
import logging
import config
import yolo_detector


class CameraStreamer:
  """
    CameraStreamer handles live streaming from a given RTSP URL
    using credentials from config.py. It provides methods for reading
    frames, logging FPS and latency, and displaying frames.
  """

  def __init__(self, url):
    self.url = url
    self.cap = cv2.VideoCapture(url)
    if not self.cap.isOpened():
      raise RuntimeError("Cannot open stream")

    self.last_time = time.time()
    self.frame_count = 0
    self.fps = 0.0
    self.latency = 0

  def read_frame(self):
    start = time.time()
    ret, frame = self.cap.read()
    if not ret:
      return None
    self.latency = (time.time() - start) * 1000
    self.measure_stats()
    return frame

  def measure_stats(self):
    self.frame_count += 1
    elapsed = time.time() - self.last_time
    if elapsed >= 1.0:
      self.fps = self.frame_count / elapsed
      logging.info(f"FPS: {self.fps:.2f}")
      self.frame_count = 0
      self.last_time = time.time()
    logging.debug(f"Frame latency: {self.latency:.2f} ms")

  def release(self):
    self.cap.release()


def main():
  logging.basicConfig(level=logging.INFO,
                      format="%(asctime)s %(levelname)s: %(message)s")
  logging.info(f"Initialized {config.CAMERA_URL}")

  streamer = CameraStreamer(config.CAMERA_URL)

  detector = yolo_detector.Detector(config.YOLO_MODEL)

  while True:
    frame = streamer.read_frame()
    if frame is None:
      logging.error("No frame received. Exiting.")
      break

    detector.detect(frame)
    detector.draw_bboxes(frame)

    cv2.imshow("Live Stream", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
      break

  streamer.release()
  cv2.destroyAllWindows()


if __name__ == "__main__":
  main()
