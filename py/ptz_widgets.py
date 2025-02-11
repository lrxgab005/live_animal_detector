import tkinter as tk
from tkinter import messagebox
import glob
import json
import os
import logging
from functools import partial
import math

import config
import camera_pose_gen as cpg
from ptz_network_lib import PTZCamera
import threading
import detection_tracking as dt

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s: %(message)s")


def start_ptz_controller(camera_config=None) -> None:
  """Initialize the PTZ controller UI and start the Tkinter main loop."""

  if camera_config:
    config.load_cam_settings(camera_config)

  root = tk.Tk()
  root.title("PTZ Navigation")

  ptz_camera = PTZCamera(config.HOST,
                         config.PORT,
                         config.USER,
                         config.PASSWORD,
                         channel=1)
  ctrl = PTZControllerUI(root, ptz_camera)

  # Create a frame to group control buttons
  btn_frame = tk.Frame(root)
  btn_frame.pack(padx=10, pady=10)

  # --- Timed Moves ---
  btn_up = tk.Button(btn_frame,
                     text="↑",
                     command=partial(ctrl.move_timed, 0, ctrl.vel_tilt, 0,
                                     ctrl.t_tilt_ms))
  btn_up.grid(row=0, column=2, padx=5, pady=5)

  btn_down = tk.Button(btn_frame,
                       text="↓",
                       command=partial(ctrl.move_timed, 0, -ctrl.vel_tilt, 0,
                                       ctrl.t_tilt_ms))
  btn_down.grid(row=2, column=2, padx=5, pady=5)

  btn_left = tk.Button(btn_frame,
                       text="←",
                       command=partial(ctrl.move_timed, -ctrl.vel_pan, 0, 0,
                                       ctrl.t_pan_ms))
  btn_left.grid(row=1, column=1, padx=5, pady=5)

  btn_right = tk.Button(btn_frame,
                        text="→",
                        command=partial(ctrl.move_timed, ctrl.vel_pan, 0, 0,
                                        ctrl.t_pan_ms))
  btn_right.grid(row=1, column=3, padx=5, pady=5)

  btn_zoom_in = tk.Button(btn_frame,
                          text="+",
                          command=partial(ctrl.move_timed, 0, 0, ctrl.vel_zoom,
                                          ctrl.t_zoom_ms))
  btn_zoom_in.grid(row=0, column=5, padx=5, pady=5)

  btn_zoom_out = tk.Button(btn_frame,
                           text="-",
                           command=partial(ctrl.move_timed, 0, 0,
                                           -ctrl.vel_zoom, ctrl.t_zoom_ms))
  btn_zoom_out.grid(row=2, column=5, padx=5, pady=5)

  btn_pause = tk.Button(btn_frame, text="⏸", command=ctrl.stop)
  btn_pause.grid(row=1, column=2, padx=5, pady=5)

  # --- Continuous Moves ---
  btn_lleft = tk.Button(btn_frame,
                        text="⟸",
                        command=partial(ctrl.start_continuous_move,
                                        -ctrl.vel_pan, 0, 0))
  btn_lleft.grid(row=1, column=0, padx=5, pady=5)

  btn_rright = tk.Button(btn_frame,
                         text="⟹",
                         command=partial(ctrl.start_continuous_move,
                                         ctrl.vel_pan, 0, 0))
  btn_rright.grid(row=1, column=4, padx=5, pady=5)

  # --- Velocity Adjustment Buttons ---
  btn_inc_pan = tk.Button(
      btn_frame,
      text="++Pan",
      command=lambda: setattr(ctrl, 'vel_pan', min(ctrl.vel_pan + 10, 100)))
  btn_inc_pan.grid(row=3, column=0, padx=5, pady=5)

  btn_dec_pan = tk.Button(
      btn_frame,
      text="--Pan",
      command=lambda: setattr(ctrl, 'vel_pan', max(ctrl.vel_pan - 10, 10)))
  btn_dec_pan.grid(row=4, column=0, padx=5, pady=5)

  btn_inc_tilt = tk.Button(
      btn_frame,
      text="++Tilt",
      command=lambda: setattr(ctrl, 'vel_tilt', min(ctrl.vel_tilt + 10, 100)))
  btn_inc_tilt.grid(row=3, column=2, padx=5, pady=5)

  btn_dec_tilt = tk.Button(
      btn_frame,
      text="--Tilt",
      command=lambda: setattr(ctrl, 'vel_tilt', max(ctrl.vel_tilt - 10, 10)))
  btn_dec_tilt.grid(row=4, column=2, padx=5, pady=5)

  btn_inc_zoom = tk.Button(
      btn_frame,
      text="++Zoom",
      command=lambda: setattr(ctrl, 'vel_zoom', min(ctrl.vel_zoom + 10, 100)))
  btn_inc_zoom.grid(row=3, column=5, padx=5, pady=5)

  btn_dec_zoom = tk.Button(
      btn_frame,
      text="--Zoom",
      command=lambda: setattr(ctrl, 'vel_zoom', max(ctrl.vel_zoom - 10, 10)))
  btn_dec_zoom.grid(row=4, column=5, padx=5, pady=5)

  # --- Absolute Move Dialogs ---
  btn_abs_move = tk.Button(btn_frame,
                           text="Move To",
                           command=ctrl.show_move_to_dialog)
  btn_abs_move.grid(row=5, column=0, columnspan=2, padx=5, pady=10)

  btn_abs_move_step = tk.Button(btn_frame,
                                text="Move To in Steps",
                                command=ctrl.show_move_to_steps_dialog)
  btn_abs_move_step.grid(row=5, column=2, columnspan=2, padx=5, pady=10)

  btn_abs_move_seq = tk.Button(btn_frame,
                               text="Move Sequence",
                               command=lambda: ctrl.show_move_sequence_dialog(
                                   config.CAM_MOVE_SEQS_PATH))
  btn_abs_move_seq.grid(row=5, column=4, columnspan=2, padx=5, pady=10)

  btn_track_move_seq = tk.Button(
      btn_frame,
      text="Track Sequence",
      command=lambda: ctrl.show_track_move_dialog(config.CAM_MOVE_SEQS_PATH))
  btn_track_move_seq.grid(row=6, column=0, columnspan=6, padx=5, pady=10)

  btn_click_drag = tk.Button(btn_frame,
                             text="Click and Drag",
                             command=lambda: ctrl.show_click_drag_dialog())
  btn_click_drag.grid(row=7, column=0, columnspan=6, padx=5, pady=10)

  root.mainloop()


class PTZControllerUI:
  """
    High-level controller bridging the camera API and the UI.
    Offers timed moves (one-shot), continuous moves,
    absolute moves, and preset functions.
    """

  def __init__(self, root: tk.Tk, camera: PTZCamera) -> None:
    self.root = root
    self.camera = camera
    self._keep_moving = False
    self._move_args = (0, 0, 0)

    # Default speeds and durations
    self.vel_pan: int = 50
    self.vel_tilt: int = 50
    self.vel_zoom: int = 50
    self.t_pan_ms: int = 500
    self.t_tilt_ms: int = 500
    self.t_zoom_ms: int = 500
    self.continuous_interval_ms: int = 1000

    # Bounding box to camera pose converter
    self.bbox_pose_converter = dt.BBoxCameraPoseConverter(
        config.IMG_WIDTH, config.IMG_HEIGHT, config.FX_SCALE, config.FY_SCALE)

    # Start DetectionPositionMatcher in a separate thread
    self.detection_position_matcher = dt.DetectionPositionMatcher(
        self.camera, config.FRAME_DATA_PORT, config.MIN_DETECTION_POSE_DT_MS,
        config.FRAME_TO_POSE_LATENCY_MS, config.CAM_DETECTIONS_PATH,
        self.bbox_pose_converter)
    threading.Thread(target=lambda: setattr(self, 'detection_position_matcher',
                                            self.detection_position_matcher),
                     daemon=True).start()

  def move_timed(self, pan: float, tilt: float, zoom: float,
                 duration: int) -> None:
    """Perform a timed move and then stop after the duration."""
    try:
      self.camera.continuous_move(pan, tilt, zoom)
      logging.info(f"Status: {self.camera.get_status()}")
      self.root.after(duration, self.stop)
    except Exception as e:
      logging.error(f"Error during timed move: {e}")
      messagebox.showerror("Error", f"Error during timed move: {e}")

  def start_continuous_move(self, pan: float, tilt: float,
                            zoom: float) -> None:
    """Start a continuous move in the given direction."""
    self._keep_moving = True
    self._move_args = (pan, tilt, zoom)
    self._schedule_continuous_move()

  def _schedule_continuous_move(self) -> None:
    if self._keep_moving:
      pan, tilt, zoom = self._move_args
      try:
        self.camera.continuous_move(pan, tilt, zoom)
      except Exception as e:
        logging.error(f"Error during continuous move: {e}")
        messagebox.showerror("Error", f"Error during continuous move: {e}")
      self.root.after(self.continuous_interval_ms,
                      self._schedule_continuous_move)

  def stop(self) -> None:
    """Stop any ongoing movement."""
    self._keep_moving = False
    try:
      self.camera.stop()
    except Exception as e:
      logging.error(f"Error stopping movement: {e}")
      messagebox.showerror("Error", f"Error stopping movement: {e}")

  def show_move_to_dialog(self) -> None:
    """Show the absolute move dialog."""
    AbsoluteMoveDialog(self.root, self.camera)

  def show_move_to_steps_dialog(self) -> None:
    """Show the stepped absolute move dialog."""
    SteppedAbsoluteMoveDialog(self.root, self.camera)

  def show_move_sequence_dialog(self, seq_folder_path: str) -> None:
    """Show the absolute move sequence dialog."""
    AbsoluteMoveSequenceDialog(self.root, self.camera, seq_folder_path)

  def show_track_move_dialog(self, seq_folder_path: str) -> None:
    """Show the track move sequence dialog."""
    TrackMoveSequenceDialog(self.root, self.camera, seq_folder_path,
                            self.detection_position_matcher)

  def show_click_drag_dialog(self) -> None:
    """Show the click drag dialog."""
    BBoxMoveDialog(self.root, self.camera, self.detection_position_matcher)


class BaseMoveDialog(tk.Toplevel):
  """
    Base dialog for move actions with dynamic fields and a callback.
    """

  def __init__(self,
               master: tk.Tk,
               camera: PTZCamera,
               fields: dict,
               field_types: dict,
               move_callback,
               title: str = "Move") -> None:
    super().__init__(master)
    self.camera = camera
    self.title(title)
    self.grab_set()
    self.fields = fields.copy()  # Default values for each field
    self.field_types = field_types  # e.g. {"pan": float, ...}
    self.move_callback = move_callback
    self._build_ui()

  def _build_ui(self) -> None:
    self.entries = {}
    for i, (field, default) in enumerate(self.fields.items()):
      tk.Label(self, text=f"{field.capitalize()}:").grid(row=i,
                                                         column=0,
                                                         padx=5,
                                                         pady=5)
      entry = tk.Entry(self)
      entry.grid(row=i, column=1, padx=5, pady=5)
      # Prefill with camera status if available; fallback to default
      entry.insert(0, str(self.camera.get_status().get(field, default)))
      self.entries[field] = entry
    tk.Button(self, text="Move", command=self.on_ok).grid(row=len(self.fields),
                                                          column=0,
                                                          padx=5,
                                                          pady=5)
    tk.Button(self, text="Cancel",
              command=self.destroy).grid(row=len(self.fields),
                                         column=1,
                                         padx=5,
                                         pady=5)

  def _parse_fields(self) -> dict:
    values = {}
    for field, conv in self.field_types.items():
      try:
        values[field] = conv(self.entries[field].get())
      except ValueError:
        messagebox.showerror("Invalid Input",
                             f"Please enter valid numeric values for {field}")
        return None
    return values

  def on_ok(self) -> None:
    values = self._parse_fields()
    if values is None:
      return
    self.move_callback(**values)
    self.destroy()


class AbsoluteMoveDialog(BaseMoveDialog):
  """
    Dialog for an immediate absolute move.
    """

  def __init__(self,
               master: tk.Tk,
               camera: PTZCamera,
               title: str = "Absolute Move") -> None:
    fields = {"pan": 0, "tilt": 0, "zoom": 0}
    field_types = {"pan": float, "tilt": float, "zoom": float}
    super().__init__(master, camera, fields, field_types, self.move_absolute,
                     title)

  def move_absolute(self, pan: float, tilt: float, zoom: float) -> None:
    try:
      self.camera.move_absolute(pan, tilt, zoom)
      logging.info(f"Status: {self.camera.get_status()}")
    except Exception as e:
      logging.error(f"Error during absolute move: {e}")
      messagebox.showerror("Error", f"Error during absolute move: {e}")


class SteppedAbsoluteMoveDialog(BaseMoveDialog):
  """
    Dialog for an absolute move executed in steps.
    """

  def __init__(self,
               master: tk.Tk,
               camera: PTZCamera,
               title: str = "Stepped Absolute Move") -> None:
    fields = {
        "pan": 0,
        "tilt": 0,
        "zoom": 0,
        "steps": 20,
        "wait_time_ms": 1500
    }
    field_types = {
        "pan": float,
        "tilt": float,
        "zoom": float,
        "steps": int,
        "wait_time_ms": int
    }
    super().__init__(master, camera, fields, field_types,
                     self.move_absolute_steps, title)

  def on_ok(self) -> None:
    values = self._parse_fields()
    if values is None:
      return
    self.move_absolute_steps(**values)

  def move_absolute_steps(self, pan: float, tilt: float, zoom: float,
                          steps: int, wait_time_ms: int) -> None:
    start_pose = cpg.PTZCameraPose(wait_time_ms=wait_time_ms)
    start_pose.load_from_dict(self.camera.get_status())
    end_pose = cpg.PTZCameraPose(pan, tilt, zoom, wait_time_ms)
    stepped_move = cpg.SteppedMove(start_pose, end_pose, steps)

    step_mover = cpg.SteppedMover(self, self.camera)
    step_mover.execute(stepped_move, callback=self.destroy)


class AbsoluteMoveSequenceDialog(tk.Toplevel):
  """
    Dialog for selecting and executing a sequence of stepped absolute moves
    from predefined JSON sequences.
    """

  def __init__(self,
               master: tk.Tk,
               camera: PTZCamera,
               seq_folder_path: str,
               title: str = "Absolute Move Sequence") -> None:
    super().__init__(master)
    self.camera = camera
    self.title(title)
    self.grab_set()
    self.sequences_dict = {}
    self.seq_moves = cpg.SteppedMove()
    self._load_sequences(seq_folder_path)
    self._build_ui()
    self.sequence_queue = []

  def _load_sequences(self, seq_folder_path: str) -> None:
    files = glob.glob(os.path.join(seq_folder_path, "*.json"))
    for f in files:
      try:
        with open(f, "r") as fp:
          sequences = json.load(fp)
        basename = os.path.basename(f)
        self.sequences_dict[basename] = sequences
      except Exception as e:
        logging.error(f"Error loading {f}: {e}")

  def _build_ui(self) -> None:
    tk.Label(self, text="Select Sequence File:").grid(row=0,
                                                      column=0,
                                                      padx=5,
                                                      pady=5)
    self.sequence_var = tk.StringVar(self)
    options = list(self.sequences_dict.keys())
    if options:
      self.sequence_var.set(options[0])
    tk.OptionMenu(self, self.sequence_var, *options).grid(row=0,
                                                          column=1,
                                                          padx=5,
                                                          pady=5)
    tk.Button(self, text="Run", command=self.on_run).grid(row=1,
                                                          column=0,
                                                          padx=5,
                                                          pady=5)
    tk.Button(self, text="Cancel", command=self.destroy).grid(row=1,
                                                              column=1,
                                                              padx=5,
                                                              pady=5)

  def on_run(self) -> None:
    file_key = self.sequence_var.get()
    if file_key not in self.sequences_dict:
      logging.error("Selected file not found")
      messagebox.showerror("Error", "Selected file not found")
      return

    seq_moves = cpg.SteppedMove()
    for sequence in self.sequences_dict[file_key]:
      start_pose = cpg.PTZCameraPose()
      start_pose.load_from_dict(sequence.get("start_pose"))
      end_pose = cpg.PTZCameraPose()
      end_pose.load_from_dict(sequence.get("end_pose"))
      seq_moves.add_linspaced_steps(start_pose, end_pose,
                                    sequence.get("nr_steps"))

    step_mover = cpg.SteppedMover(self, self.camera)
    step_mover.execute(seq_moves, callback=self.on_run)


class TrackMoveSequenceDialog(tk.Toplevel):
  """
    Dialog for selecting and executing a sequence of stepped absolute moves
    from predefined JSON sequences, including a circular plot for pan-tilt values.
  """

  def __init__(self,
               master: tk.Tk,
               camera: PTZCamera,
               seq_folder_path: str,
               detection_pose_matcher: 'dt.DetectionPositionMatcher',
               title: str = "Absolute Move Sequence") -> None:
    super().__init__(master)
    self.camera = camera
    self.title(title)
    self.grab_set()
    self.sequences_dict = {}
    self.seq_moves = cpg.SteppedMove()
    self._load_sequences(seq_folder_path)
    self.sequence_queue = []
    self.detection_pose_matcher = detection_pose_matcher
    # Start periodic plot updates
    self.after(100, self.update_plot)
    self.canvas_width, self.canvas_height = 400, 400
    self.center_x, self.center_y, self.radius = 200, 200, 190
    self._build_ui()
    self.break_sequence = False

  def _load_sequences(self, seq_folder_path: str) -> None:
    files = glob.glob(os.path.join(seq_folder_path, "*.json"))
    for f in files:
      try:
        with open(f, "r") as fp:
          sequences = json.load(fp)
        basename = os.path.basename(f)
        self.sequences_dict[basename] = sequences
      except Exception as e:
        logging.error(f"Error loading {f}: {e}")

  def _build_ui(self) -> None:
    tk.Label(self, text="Select Sequence File:").grid(row=0,
                                                      column=0,
                                                      padx=5,
                                                      pady=5)
    self.sequence_var = tk.StringVar(self)
    options = list(self.sequences_dict.keys())
    if options:
      self.sequence_var.set(options[0])
    tk.OptionMenu(self, self.sequence_var, *options).grid(row=0,
                                                          column=1,
                                                          padx=5,
                                                          pady=5)
    tk.Button(self, text="Run", command=self.on_run).grid(row=1,
                                                          column=0,
                                                          padx=5,
                                                          pady=5)
    tk.Button(self, text="Cancel", command=self.destroy).grid(row=1,
                                                              column=1,
                                                              padx=5,
                                                              pady=5)
    # Canvas for pan-tilt plot with click-to-move functionality
    self.canvas = tk.Canvas(self,
                            width=self.canvas_width,
                            height=self.canvas_height,
                            bg='white')
    self.canvas.grid(row=2, column=0, columnspan=2, padx=5, pady=5)
    self.canvas.bind("<Button-1>", self.on_canvas_click)
    # Draw circular boundary
    self.canvas.create_oval(self.center_x - self.radius,
                            self.center_y - self.radius,
                            self.center_x + self.radius,
                            self.center_y + self.radius,
                            outline='black')
    # Add degree markings
    for angle in range(0, 360, 90):
      rad = math.radians(angle)
      x_outer = self.center_x + self.radius * math.cos(rad)
      y_outer = self.center_y - self.radius * math.sin(rad)
      x_inner = self.center_x + (self.radius - 10) * math.cos(rad)
      y_inner = self.center_y - (self.radius - 10) * math.sin(rad)
      self.canvas.create_line(x_inner, y_inner, x_outer, y_outer, fill="black")
      x_label = self.center_x + (self.radius - 20) * math.cos(rad)
      y_label = self.center_y - (self.radius - 20) * math.sin(rad)
      self.canvas.create_text(x_label,
                              y_label,
                              text=str(angle),
                              font=("Arial", 10),
                              fill="black")

  def on_canvas_click(self, event: tk.Event) -> None:
    # Move camera to pan/tilt corresponding to clicked position
    self.break_sequence = True
    pan, tilt = self.cartesian_to_pose(event.x, event.y)
    pose = cpg.PTZCameraPose()
    pose.pan = pan
    pose.tilt = tilt
    pose.zoom = self.detection_pose_matcher.curr_pose["zoom"]
    self.camera.move_absolute(pose.pan, pose.tilt, pose.zoom)

  def plot_points(self):
    self.canvas.delete("points")

    cam_pose = self.detection_pose_matcher.curr_pose
    x, y = self.pose_to_cartesian(cam_pose["pan"], cam_pose["tilt"])
    self.canvas.create_oval(x - 5,
                            y - 5,
                            x + 5,
                            y + 5,
                            fill="black",
                            outline="black",
                            tags="points")

    if not self.detection_pose_matcher.detection_pose_match_queue:
      return

    match_data = self.detection_pose_matcher.detection_pose_match_queue.copy()
    for data in match_data:
      for pose, class_id in zip(data.get("poses", []),
                                data.get("class_ids", [])):
        pan = pose.get("pan", 0)
        tilt = pose.get("tilt", 0)
        x, y = self.pose_to_cartesian(pan, tilt)
        color = config.ALARM_COLORS.get(class_id, [0, 0, 0])
        color = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
        self.canvas.create_oval(x - 2,
                                y - 2,
                                x + 2,
                                y + 2,
                                fill=color,
                                outline=color,
                                tags="points")

  def cartesian_to_pose(self, x: float, y: float) -> tuple:
    dx = x - self.center_x
    dy = self.center_y - y  # Invert y-axis
    radius_click = math.sqrt(dx * dx + dy * dy)
    clamped_radius = min(radius_click, self.radius)
    pan = math.degrees(math.atan2(dy, dx))
    if pan < 0:
      pan += 360
    tilt = -((clamped_radius / self.radius) * 180 - 90)
    return pan, tilt

  def pose_to_cartesian(self, pan: float, tilt: float) -> tuple:
    pan_rad = math.radians(pan)
    radius = ((-tilt + 90) / 180) * self.radius
    radius = min(radius, self.radius)
    x = self.center_x + radius * math.cos(pan_rad)
    y = self.center_y - radius * math.sin(pan_rad)
    return x, y

  def update_plot(self):
    self.plot_points()
    self.after(100, self.update_plot)

  def on_run(self) -> None:
    file_key = self.sequence_var.get()
    if file_key not in self.sequences_dict:
      logging.error("Selected file not found")
      messagebox.showerror("Error", "Selected file not found")
      return
    seq_moves = cpg.SteppedMove()
    for sequence in self.sequences_dict[file_key]:
      start_pose = cpg.PTZCameraPose()
      start_pose.load_from_dict(sequence.get("start_pose"))
      end_pose = cpg.PTZCameraPose()
      end_pose.load_from_dict(sequence.get("end_pose"))
      seq_moves.add_linspaced_steps(start_pose, end_pose,
                                    sequence.get("nr_steps"))
    step_mover = cpg.SteppedMover(self, self.camera)
    step_mover.execute(seq_moves, callback=self.on_run)


class BBoxMoveDialog(tk.Toplevel):
  """
    Dialog with a canvas that lets users click and drag to select a bounding box;
    the camera then moves to center on the selected region.
  """

  def __init__(self,
               master: tk.Tk,
               camera,
               converter: 'dt.BBoxCameraPoseConverter',
               title: str = "BBox Move") -> None:
    super().__init__(master)
    self.camera = camera
    self.converter = converter
    self.title(title)
    self.canvas = tk.Canvas(self,
                            width=self.converter.img_width,
                            height=self.converter.img_height,
                            bg="gray")
    self.canvas.pack()
    self.start_x = None
    self.start_y = None
    self.rect = None
    self.raw_bbox = None
    self.canvas.bind("<ButtonPress-1>", self.on_button_press)
    self.canvas.bind("<B1-Motion>", self.on_move_press)
    self.canvas.bind("<ButtonRelease-1>", self.on_button_release)

  def on_button_press(self, event):
    self.start_x = event.x
    self.start_y = event.y
    self.rect = self.canvas.create_rectangle(self.start_x,
                                             self.start_y,
                                             self.start_x,
                                             self.start_y,
                                             outline="red")

  def on_move_press(self, event):
    cur_x, cur_y = event.x, event.y
    self.raw_bbox = [self.start_x, self.start_y, cur_x, cur_y]
    self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

  def on_button_release(self, event):
    x0, y0, x1, y1 = self.raw_bbox
    # x0, y0, x1, y1 = self.canvas.coords(self.rect)
    bbox = [x0, y0, x1, y1]

    try:
      # Assume camera.get_status() returns a dict: {"pan": ..., "tilt": ..., "zoom": ...}
      current_pose = self.camera.get_status()
      new_params = self.converter.convert(bbox, current_pose)
      self.camera.move_absolute(new_params["pan"], new_params["tilt"],
                                new_params["zoom"])
      logging.info(f"Moved camera to: {new_params}")
    except Exception as e:
      logging.error(f"Error moving camera: {e}")
      messagebox.showerror("Error", f"Error moving camera: {e}")
    self.canvas.delete(self.rect)
    self.rect = None
