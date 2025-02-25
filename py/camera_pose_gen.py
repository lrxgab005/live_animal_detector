from typing import List, Optional, Dict, Any, Callable
import logging
import numpy as np

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s: %(message)s")


class PTZCameraPose:
  """
  Represents a camera pose.
  """

  def __init__(self,
               pan: float = 0,
               tilt: float = 0,
               zoom: float = 0,
               wait_time_ms: int = 1000) -> None:
    self.pan = pan
    self.tilt = tilt
    self.zoom = zoom
    self.wait_time_ms = wait_time_ms

  def load_from_dict(self, data: Optional[Dict[str, Any]]) -> 'PTZCameraPose':
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

  def get_list(self) -> List[float]:
    return [self.pan, self.tilt, self.zoom, self.wait_time_ms]

  def __str__(self) -> str:
    return (f"pan: {np.round(self.pan, 2)}, "
            f"tilt: {np.round(self.tilt, 2)}, "
            f"zoom: {np.round(self.zoom, 2)}, "
            f"wait_time_ms: {int(self.wait_time_ms)}")


class SteppedMove:
  """
  Represents a linear sequence of steps between two camera poses.
  """

  def __init__(self,
               pose1: Optional[PTZCameraPose] = None,
               pose2: Optional[PTZCameraPose] = None,
               nr_steps: Optional[int] = None) -> None:
    self.steps: List[PTZCameraPose] = []
    self.total_steps: int = 0
    if all([pose1, pose2, nr_steps]):
      self.add_linspaced_steps(pose1, pose2, nr_steps)

  def add_linspaced_steps(self, pose1: PTZCameraPose, pose2: PTZCameraPose,
                          nr_steps: int) -> None:
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

    logging.info(f"{str(pose1)}->{str(pose2)}")
    logging.info(f"Generated {nr_steps} steps")

  def has_steps(self) -> bool:
    return bool(self.steps)

  def pop_step(self) -> Optional[PTZCameraPose]:
    if not self.has_steps():
      return None

    logging.info(f"Steps Nr: {len(self.steps)}")
    return self.steps.pop(0)

  def __str__(self) -> str:
    return f"""
        Steps: {len(self.steps)}/{self.total_steps}
        Current Pose: {self.steps[0]}
        Final Pose: {self.steps[-1]}
      """


class MCMCSteppedMove:
  """
  Monte-Carlo Markov Chain step move.
  """

  def __init__(self,
               step_size: float = 0.1,
               heat_map: Optional[Callable] = None) -> None:
    self.step_size = step_size
    self.heat_map = heat_map
    self.running = False

  def is_running(self) -> bool:
    return self.running

  def metropolis_hastings(self, num_samples: int,
                          initial_position: List[float],
                          step_size: float) -> np.ndarray:
    samples = []
    current_position = np.array(initial_position)
    current_prob = self.heat_map(*current_position)

    for _ in range(num_samples):
      proposal = current_position + np.random.normal(scale=step_size, size=2)
      proposal_prob = self.heat_map(*proposal)

      acceptance_prob = min(1, proposal_prob / current_prob)
      if np.random.rand() < acceptance_prob:
        current_position = proposal
        current_prob = proposal_prob

      samples.append(current_position)

    return np.array(samples)


class SteppedMover:
  """
  Executes a sequence of camera move steps asynchronously with a delay.
  """

  def __init__(self,
               widget: Any,
               camera: Any,
               stepped_move: SteppedMove,
               mcmc_stepped_move: Optional[MCMCSteppedMove] = None) -> None:
    self.widget = widget
    self.camera = camera
    self.stepped_move = stepped_move
    self.mcmc_stepped_move = mcmc_stepped_move

  def execute(self, callback: Optional[Callable] = None) -> None:
    if self.widget.wait_sequence:
      if self.mcmc_stepped_move:
        self.widget.after(500, lambda: self.execute(callback))
      elif not self.mcmc_stepped_move.is_running:
        self.mcmc_stepped_move.metropolis_hastings(1000,
                                                   initial_position=[0, 0],
                                                   step_size=0.1)

      self.widget.after(500, lambda: self.execute(callback))
      return

    if self.widget.break_sequence:
      self.widget.break_sequence = False
      return

    if not self.stepped_move.has_steps():
      if callback:
        callback()
      return

    next_pose = self.stepped_move.pop_step()

    try:
      self.camera.move_absolute(next_pose.pan, next_pose.tilt, next_pose.zoom)
      logging.info("Status: %s", self.camera.get_status())
    except Exception as e:
      logging.error("Error during move: %s", e)
      if callback:
        callback()
      return

    self.widget.after(int(next_pose.wait_time_ms),
                      lambda: self.execute(callback))
