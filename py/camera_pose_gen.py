import logging
import numpy as np

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s: %(message)s")


class PTZCameraPose:
  """
    Represents a camera pose.
  """

  def __init__(self, pan=0, tilt=0, zoom=0, wait_time_ms=1000):
    self.pan = pan
    self.tilt = tilt
    self.zoom = zoom
    self.wait_time_ms = wait_time_ms

  def load_from_dict(self, data):
    if not data:
      logging.error("Invalid data for PTZCameraPose")

    if not all([key in data for key in ["pan", "tilt", "zoom"]]):
      logging.error(f"Invalid data for PTZCameraPose: {data}")

    self.pan = data.get("pan", 0)
    self.tilt = data.get("tilt", 0)
    self.zoom = data.get("zoom", 0)
    if "wait_time_ms" in data:
      self.wait_time_ms = data.get("wait_time_ms")

    return self

  def get_list(self):
    return [self.pan, self.tilt, self.zoom, self.wait_time_ms]

  def __str__(self):
    return (f"pan: {np.round(self.pan, 2)}, "
            f"tilt: {np.round(self.tilt, 2)}, "
            f"zoom: {np.round(self.zoom, 2)}, "
            f"wait_time_ms: {int(self.wait_time_ms)}")


class SteppedMove:
  """
    Represents a linear sequence of steps between two camera poses.
  """

  def __init__(self, pose1=None, pose2=None, nr_steps=None):
    self.steps = []
    self.total_steps = 0
    if all([pose1, pose2, nr_steps]):
      self.add_linspaced_steps(pose1, pose2, nr_steps)

    logging.info(f"Generated {nr_steps} steps")

  def add_linspaced_steps(self, pose1, pose2, nr_steps):
    pan_steps = np.linspace(pose1.pan, pose2.pan, nr_steps)
    tilt_steps = np.linspace(pose1.tilt, pose2.tilt, nr_steps)
    zoom_steps = np.linspace(pose1.zoom, pose2.zoom, nr_steps)
    wait_times_ms = np.linspace(pose1.wait_time_ms, pose2.wait_time_ms,
                                nr_steps)

    self.steps += [
        PTZCameraPose(pan, tilt, zoom,
                      wait_time_ms) for pan, tilt, zoom, wait_time_ms in zip(
                          pan_steps, tilt_steps, zoom_steps, wait_times_ms)
    ]
    self.total_steps = len(self.steps)

  def has_steps(self):
    return bool(self.steps)

  def pop_step(self):
    if not self.has_steps():
      return None

    logging.info(f"Steps Nr: {len(self.steps)}")
    return self.steps.pop(0)

  def __str__(self):
    return f"""
              Steps: {len(self.steps)}/{self.total_steps}
              Current Pose: {self.steps[0]}
              Final Pose: {self.steps[-1]}
            """


class SteppedMover:
  """
    Executes a sequence of camera move steps asynchronously with a delay.
  """

  def __init__(self, widget, camera):
    self.widget = widget
    self.camera = camera

  def execute(self, stepped_move, callback=None):
    if not stepped_move.has_steps():
      if callback:
        callback()
      return

    print(str(stepped_move))
    next_pose = stepped_move.pop_step()

    try:
      self.camera.move_absolute(next_pose.pan, next_pose.tilt, next_pose.zoom)
      logging.info("Status: %s", self.camera.get_status())
    except Exception as e:
      logging.error("Error during move: %s", e)
      if callback:
        callback()
      return
    self.widget.after(int(next_pose.wait_time_ms),
                      lambda: self.execute(stepped_move, callback))
