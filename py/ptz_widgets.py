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
from PIL import Image, ImageTk

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
      text="Interactive Detection Plot",
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
                            self.detection_position_matcher,
                            config.ALARM_COLORS, config.ALARM_NAMES)

  def show_click_drag_dialog(self) -> None:
    """Show the click drag dialog."""
    BBoxMoveDialog(self.root, self.camera, self.bbox_pose_converter)


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


class PanTiltCanvas(tk.Canvas):
  """
    Custom canvas that converts between pan/tilt and canvas coords,
    and draws a heatmap as a single image for performance.
  """

  def __init__(self,
               master,
               width: int,
               height: int,
               center_x: float,
               center_y: float,
               radius,
               heat_radius_px: int = 10,
               **kwargs):
    super().__init__(master, width=width, height=height, bg='white', **kwargs)
    self.center_x = center_x
    self.center_y = center_y
    self.radius = radius
    self.heat_radius_px = heat_radius_px
    self.heatmap_image = None
    self.heatmap_photo = None
    self.heatmap_obj_id = None

    # Draw boundary circle
    self.create_oval(self.center_x - self.radius,
                     self.center_y - self.radius,
                     self.center_x + self.radius,
                     self.center_y + self.radius,
                     outline='black')

    # Draw angle markings
    for angle in range(0, 360, 30):
      rad = math.radians(angle)
      x_outer = self.center_x + self.radius * math.cos(rad)
      y_outer = self.center_y + self.radius * math.sin(rad)
      x_inner = self.center_x + (self.radius - 10) * math.cos(rad)
      y_inner = self.center_y + (self.radius - 10) * math.sin(rad)
      self.create_line(x_inner, y_inner, x_outer, y_outer, fill="black")

      x_label = self.center_x + (self.radius - 20) * math.cos(rad)
      y_label = self.center_y + (self.radius - 20) * math.sin(rad)
      self.create_text(x_label,
                       y_label,
                       text=str(angle),
                       font=("Arial", 10),
                       fill="black")

  def to_canvas_coords(self, pan: float, tilt: float) -> tuple[float, float]:
    pan_rad = math.radians(pan)
    r = ((-tilt + 45) / 90) * self.radius
    r = min(r, self.radius)
    x = self.center_x + r * math.cos(pan_rad)
    y = self.center_y + r * math.sin(pan_rad)
    return x, y

  def to_pan_tilt_coords(self, x: float, y: float) -> tuple[float, float]:
    dx = x - self.center_x
    dy = self.center_y - y
    r_click = math.sqrt(dx * dx + dy * dy)
    clamped_r = min(r_click, self.radius)
    pan = -math.degrees(math.atan2(dy, dx))
    if pan < 0:
      pan += 360
    tilt = -((clamped_r / self.radius) * 90 - 45)
    return pan, tilt

  def add_point_to_heat_buffer(self, cx: int, cy: int, heat_val: float,
                               heat_buffer) -> None:
    w, h = self.winfo_width(), self.winfo_height()

    center_xi = int(cx)
    center_yi = int(cy)

    x_min = max(0, center_xi - self.heat_radius_px)
    x_max = min(w - 1, center_xi + self.heat_radius_px)
    y_min = max(0, center_yi - self.heat_radius_px)
    y_max = min(h - 1, center_yi + self.heat_radius_px)

    for ix in range(x_min, x_max + 1):
      dx = ix - center_xi
      for iy in range(y_min, y_max + 1):
        dy = iy - center_yi
        dist = math.sqrt(dx * dx + dy * dy)
        if dist >= self.heat_radius_px or dist <= 0:
          continue

        falloff = 1.0 - (dist / self.heat_radius_px)
        heat_contribution = heat_val * falloff
        heat_buffer[ix][iy] += heat_contribution

  def draw_heatmap(self, hotpoints: dict[tuple[float, float], float]) -> None:
    """
      Renders a smoothed radial heatmap: each hotpoint has a certain radius
      of influence. We accumulate all heat contributions into a float buffer,
      then map that buffer to a color scale.
    """
    w, h = self.winfo_width(), self.winfo_height()

    heat_buffer = [[0.0] * h for _ in range(w)]
    for (pan, tilt), heat_val in hotpoints.items():
      cx, cy = self.to_canvas_coords(pan, tilt)
      self.add_point_to_heat_buffer(cx, cy, heat_val, heat_buffer)

    self.heatmap_image = Image.new("RGB", (w, h), "white")
    pixels = self.heatmap_image.load()
    for ix in range(w):
      for iy in range(h):
        val = min(1.0, heat_buffer[ix][iy])  # clamp
        r = 255
        g = 255 - int(val * 255)
        b = 255 - int(val * 255)
        pixels[ix, iy] = (r, g, b)

    self.heatmap_photo = ImageTk.PhotoImage(self.heatmap_image)
    if self.heatmap_obj_id:
      self.delete(self.heatmap_obj_id)
    self.heatmap_obj_id = self.create_image(0,
                                            0,
                                            anchor=tk.NW,
                                            image=self.heatmap_photo)

    self.tag_lower(self.heatmap_obj_id)

  def draw_points(self, points, tag="points"):
    self.delete(tag)
    for (pan, tilt, c, r) in points:
      x, y = self.to_canvas_coords(pan, tilt)
      self.create_oval(x - r, y - r, x + r, y + r, fill=c, outline=c, tags=tag)


class TrackMoveSequenceDialog(tk.Toplevel):
  """
    Dialog that controls camera movements, displays a pan/tilt heatmap, 
    and plots detections.
  """

  def __init__(self,
               master: tk.Tk,
               camera,
               seq_folder_path: str,
               detection_pose_matcher,
               class_id_to_color: dict,
               class_id_to_name: dict,
               zoom_step: int = 10,
               title: str = "2D Detection Plot") -> None:
    super().__init__(master)
    self.camera = camera
    self.title(title)
    self.grab_set()

    self.sequences_dict = {}
    self._load_sequences(seq_folder_path)

    self.detection_pose_matcher = detection_pose_matcher
    self.zoom_step = zoom_step

    # Canvas parameters
    self.legend_width = 100
    self.circle_area_width = 800
    self.canvas_width = self.circle_area_width + self.legend_width
    self.canvas_height = 800
    self.center_x = self.circle_area_width / 2
    self.center_y = self.canvas_height / 2
    self.radius = self.center_y - 10
    self.class_id_to_color = {
        cid: f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
        for cid, rgb in class_id_to_color.items()
    }
    self.class_id_to_name = class_id_to_name

    self._build_ui()
    self.break_sequence = False
    self.after(100, self.update_plot)

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

  def _build_ui(self):
    # Sequence selection
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
    self.sequence_var.trace("w", lambda *args: self.on_run())

    # PanTiltCanvas
    self.pt_canvas = PanTiltCanvas(self,
                                   width=self.canvas_width,
                                   height=self.canvas_height,
                                   center_x=self.center_x,
                                   center_y=self.center_y,
                                   radius=self.radius)
    self.pt_canvas.grid(row=2, column=0, columnspan=2, padx=5, pady=5)
    self.pt_canvas.bind("<Button-1>", self.on_canvas_click)

    # Legend on the right side
    legend_start_x = self.circle_area_width + 10
    legend_start_y = 20
    box_size = 20
    spacing = 10
    for idx, (class_id,
              color) in enumerate(sorted(self.class_id_to_color.items())):
      y = legend_start_y + idx * (box_size + spacing)
      self.pt_canvas.create_rectangle(legend_start_x,
                                      y,
                                      legend_start_x + box_size,
                                      y + box_size,
                                      fill=color,
                                      outline=color)
      self.pt_canvas.create_text(legend_start_x + box_size + 5,
                                 y + box_size / 2,
                                 text=self.class_id_to_name.get(
                                     class_id, class_id),
                                 anchor="w",
                                 font=("Arial", 10),
                                 fill="black")

    # Zoom controls
    zoom_frame = tk.Frame(self)
    zoom_frame.grid(row=3, column=0, columnspan=2, padx=5, pady=5)
    self.pose_label = tk.Label(zoom_frame, text="Zoom: 0")
    self.pose_label.grid(row=0, column=0, padx=5)
    tk.Button(zoom_frame, text="-", command=self.decrease_zoom).grid(row=0,
                                                                     column=1,
                                                                     padx=5)
    tk.Button(zoom_frame, text="+", command=self.increase_zoom).grid(row=0,
                                                                     column=2,
                                                                     padx=5)

  def stop_sequence(self) -> None:
    self.break_sequence = True

  def on_canvas_click(self, event: tk.Event):
    # Convert click to pan/tilt, then move camera
    self.stop_sequence()
    pan, tilt = self.pt_canvas.to_pan_tilt_coords(event.x, event.y)
    pose = self.detection_pose_matcher.curr_pose
    zoom = pose.get("zoom", 0)

    self.camera.move_absolute(pan, tilt, zoom)

  def update_plot(self):
    # Update label, draw heatmap, then detection points
    self.update_pose_label()
    hotpoints = self.detection_pose_matcher.heat_map.get_pan_tilt_heat_map()
    self.pt_canvas.draw_heatmap(hotpoints)

    # Show current camera pose
    current_pan = self.detection_pose_matcher.curr_pose.get("pan", 0)
    current_tilt = self.detection_pose_matcher.curr_pose.get("tilt", 0)
    points = [(current_pan, current_tilt, "black", 5)]

    # Show detection points
    match_data = self.detection_pose_matcher.detection_pose_match_queue.copy()
    for data in match_data:
      for pose, class_id in zip(data.get("poses", []),
                                data.get("class_ids", [])):
        color = self.class_id_to_color.get(class_id, 'black')
        points.append((pose.get("pan", 0), pose.get("tilt", 0), color, 3))

    self.pt_canvas.draw_points(points)
    self.after(100, self.update_plot)

  def update_pose_label(self) -> None:
    pitch_value = int(self.detection_pose_matcher.curr_pose.get("pan", 0))
    tilt_value = int(self.detection_pose_matcher.curr_pose.get("tilt", 0))
    zoom_value = int(self.detection_pose_matcher.curr_pose.get("zoom", 0))
    nr_detections = len(self.detection_pose_matcher.detection_pose_match_queue)

    self.pose_label.config(
        text=(f"Nr Detections: {nr_detections}       "
              f"Pitch: {pitch_value}, Tilt: {tilt_value}, Zoom: {zoom_value}"))

  def change_zoom(self, delta_zoom: int) -> None:
    pose = self.detection_pose_matcher.curr_pose
    if "zoom" not in pose:
      logging.error(f"Current pose does not have zoom value: {pose}")
      return
    pose["zoom"] += delta_zoom
    self.camera.move_absolute(pose.get("pan", 0), pose.get("tilt", 0),
                              pose.get("zoom", 0))
    self.pose_label.config(text=f'Zoom: {pose["zoom"]}')

  def increase_zoom(self) -> None:
    self.change_zoom(self.zoom_step)

  def decrease_zoom(self) -> None:
    self.change_zoom(-self.zoom_step)

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
