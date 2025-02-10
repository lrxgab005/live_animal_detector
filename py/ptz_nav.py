#!/usr/bin/env python3
"""
Expanded PTZ controller with timed moves, continuous moves, absolute moves,
and preset management (save preset / go to preset).
"""

import tkinter as tk
from tkinter import messagebox
import config
import logging
import glob
import json
import os
from ptz_network_lib import PTZCamera
import camera_pose_gen as cpg

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s: %(message)s")


class PTZControllerUI:
  """
    High-level controller bridging the camera API and the UI.
    Offers timed moves (one-shot), continuous moves,
    absolute moves, and preset functions.
  """

  def __init__(self, root, camera: PTZCamera):
    self.root = root
    self.camera = camera
    self._keep_moving = False
    self._move_args = (0, 0, 0)

    # Default speeds and durations
    self.vel_pan = 50
    self.vel_tilt = 50
    self.vel_zoom = 50
    self.t_pan_ms = 500
    self.t_tilt_ms = 500
    self.t_zoom_ms = 500
    self.continuous_interval_ms = 1000

  def move_timed(self, pan, tilt, zoom, duration):
    try:
      self.camera.continuous_move(pan, tilt, zoom)
      logging.info("Status:", self.camera.get_status())
      self.root.after(duration, self.stop)
    except Exception as e:
      logging.error("Error during timed move:", e)

  def start_continuous_move(self, pan, tilt, zoom):
    self._keep_moving = True
    self._move_args = (pan, tilt, zoom)
    self._schedule_continuous_move()

  def _schedule_continuous_move(self):
    if self._keep_moving:
      pan, tilt, zoom = self._move_args
      try:
        self.camera.continuous_move(pan, tilt, zoom)
      except Exception as e:
        logging.error("Error during continuous move:", e)
      self.root.after(self.continuous_interval_ms,
                      self._schedule_continuous_move)

  def stop(self):
    self._keep_moving = False
    try:
      self.camera.stop()
    except Exception as e:
      logging.error("Error stopping movement:", e)

  def show_move_to_dialog(self):
    AbsoluteMoveDialog(self.root, self.camera)

  def show_move_to_steps_dialog(self):
    SteppedAbsoluteMoveDialog(self.root, self.camera)

  def show_move_sequence_dialog(self, seq_folder_path):
    AbsoluteMoveSequenceDialog(self.root, self.camera, seq_folder_path)


class BaseMoveDialog(tk.Toplevel):
  """
    Base dialog for move actions with dynamic fields and a callback.
  """

  def __init__(self,
               master,
               camera,
               fields,
               field_types,
               move_callback,
               title="Move"):
    super().__init__(master)
    self.camera = camera
    self.title(title)
    self.grab_set()
    self.fields = fields.copy()  # default values for each field
    self.field_types = field_types  # e.g. {"elevation": float, ...}
    self.move_callback = move_callback
    self._build_ui()

  def _build_ui(self):
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

  def _parse_fields(self):
    values = {}
    for field, conv in self.field_types.items():
      try:
        values[field] = conv(self.entries[field].get())
      except ValueError:
        messagebox.showerror("Invalid Input",
                             "Please enter valid numeric values")
        return None
    return values

  def on_ok(self):
    values = self._parse_fields()
    if values is None:
      return
    self.move_callback(**values)
    self.destroy()


class AbsoluteMoveDialog(BaseMoveDialog):
  """
    Dialog for an immediate absolute move.
  """

  def __init__(self, master, camera, title="Absolute Move"):
    fields = {"pan": 0, "tilt": 0, "zoom": 0}
    field_types = {"pan": float, "tilt": float, "zoom": float}
    super().__init__(master, camera, fields, field_types, self.move_absolute,
                     title)

  def move_absolute(self, pan, tilt, zoom):
    try:
      self.camera.move_absolute(pan, tilt, zoom)
      logging.info("Status: %s", self.camera.get_status())
    except Exception as e:
      logging.error("Error during absolute move: %s", e)


class SteppedAbsoluteMoveDialog(BaseMoveDialog):
  """
    Dialog for an absolute move executed in steps.
  """

  def __init__(self, master, camera, title="Stepped Absolute Move"):
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

  def on_ok(self):
    values = self._parse_fields()
    if values is None:
      return
    self.move_absolute_steps(**values)

  def move_absolute_steps(self, pan, tilt, zoom, steps, wait_time_ms):
    start_pose = cpg.PTZCameraPose().load_from_dict(self.camera.get_status())
    end_pose = cpg.PTZCameraPose(pan, tilt, zoom)
    stepped_move = cpg.SteppedMove(start_pose, end_pose, steps)

    step_mover = cpg.SteppedMover(self, self.camera, wait_time_ms)
    step_mover.execute(stepped_move, callback=self.destroy)


class AbsoluteMoveSequenceDialog(tk.Toplevel):
  """
    Dialog for selecting and executing a sequence of stepped absolute moves
    from predefined JSON sequences.
  """

  def __init__(self,
               master,
               camera,
               seq_folder_path,
               title="Absolute Move Sequence"):
    super().__init__(master)
    self.camera = camera
    self.title(title)
    self.grab_set()
    self.sequences_dict = {}
    self._load_sequences(seq_folder_path)
    self._build_ui()
    self.sequence_queue = []

  def _load_sequences(self, seq_folder_path):
    files = glob.glob(os.path.join(seq_folder_path, "*.json"))
    for f in files:
      try:
        with open(f, "r") as fp:
          sequences = json.load(fp)
        basename = os.path.basename(f)
        self.sequences_dict[basename] = sequences
      except Exception as e:
        logging.error("Error loading %s: %s", f, e)

  def _build_ui(self):
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

  def on_run(self):
    file_key = self.sequence_var.get()
    if file_key not in self.sequences_dict:
      logging.error("Selected file not found")
      return
    self.sequence_queue = self.sequences_dict[file_key][:]
    self.execute_next_sequence()

  def execute_next_sequence(self):
    if not self.sequence_queue:
      self.destroy()
      return

    sequence = self.sequence_queue.pop(0)
    logging.info(f"{len(self.sequence_queue)}: Running sequence: {sequence}")
    self.run_sequence(sequence, self.execute_next_sequence)

  def run_sequence(self, sequence, callback):
    start_pose = cpg.PTZCameraPose().load_from_dict(sequence.get("start_pose"))
    end_pose = cpg.PTZCameraPose().load_from_dict(sequence.get("end_pose"))
    stepped_move = cpg.SteppedMove(start_pose, end_pose,
                                   sequence.get("nr_steps"))

    step_mover = cpg.SteppedMover(self, self.camera,
                                  sequence.get("wait_time_ms"))
    step_mover.execute(stepped_move, callback=callback)


def main():
  import argparse

  parser = argparse.ArgumentParser(
      description="PTZ controller with timed moves, continuous moves, "
      "absolute moves, and preset management.")
  parser.add_argument(
      "--camera_config",
      required=True,
      help="Path to network camera stream config file. "
      "To create run: python py/create_cam_config.py",
  )
  args = parser.parse_args()

  if args.camera_config:
    config.load_cam_settings(args.camera_config)

  root = tk.Tk()
  root.title("PTZ Navigation")

  ptz_camera = PTZCamera(config.HOST,
                         config.PORT,
                         config.USER,
                         config.PASSWORD,
                         channel=1)
  ctrl = PTZControllerUI(root, ptz_camera)

  # --- Original button layout for timed moves and continuous moves ---
  btn_up = tk.Button(
      root,
      text="↑",
      command=lambda: ctrl.move_timed(0, ctrl.vel_tilt, 0, ctrl.t_tilt_ms))
  btn_down = tk.Button(
      root,
      text="↓",
      command=lambda: ctrl.move_timed(0, -ctrl.vel_tilt, 0, ctrl.t_tilt_ms))
  btn_left = tk.Button(
      root,
      text="←",
      command=lambda: ctrl.move_timed(-ctrl.vel_pan, 0, 0, ctrl.t_pan_ms))
  btn_right = tk.Button(
      root,
      text="→",
      command=lambda: ctrl.move_timed(ctrl.vel_pan, 0, 0, ctrl.t_pan_ms))
  btn_zoom_in = tk.Button(
      root,
      text="+",
      command=lambda: ctrl.move_timed(0, 0, ctrl.vel_zoom, ctrl.t_zoom_ms))
  btn_zoom_out = tk.Button(
      root,
      text="-",
      command=lambda: ctrl.move_timed(0, 0, -ctrl.vel_zoom, ctrl.t_zoom_ms))
  btn_pause = tk.Button(root, text="⏸", command=ctrl.stop)

  # Continuous moves for pan left/right:
  btn_lleft = tk.Button(
      root,
      text="⟸",
      command=lambda: ctrl.start_continuous_move(-ctrl.vel_pan, 0, 0))
  btn_rright = tk.Button(
      root,
      text="⟹",
      command=lambda: ctrl.start_continuous_move(ctrl.vel_pan, 0, 0))

  # Velocity adjustment buttons:
  btn_inc_pan = tk.Button(
      root,
      text="++Pan",
      command=lambda: setattr(ctrl, 'vel_pan', min(ctrl.vel_pan + 10, 100)))
  btn_dec_pan = tk.Button(
      root,
      text="--Pan",
      command=lambda: setattr(ctrl, 'vel_pan', max(ctrl.vel_pan - 10, 10)))
  btn_inc_tilt = tk.Button(
      root,
      text="++Tilt",
      command=lambda: setattr(ctrl, 'vel_tilt', min(ctrl.vel_tilt + 10, 100)))
  btn_dec_tilt = tk.Button(
      root,
      text="--Tilt",
      command=lambda: setattr(ctrl, 'vel_tilt', max(ctrl.vel_tilt - 10, 10)))
  btn_inc_zoom = tk.Button(
      root,
      text="++Zoom",
      command=lambda: setattr(ctrl, 'vel_zoom', min(ctrl.vel_zoom + 10, 100)))
  btn_dec_zoom = tk.Button(
      root,
      text="--Zoom",
      command=lambda: setattr(ctrl, 'vel_zoom', max(ctrl.vel_zoom - 10, 10)))

  btn_lleft.grid(row=1, column=0, padx=5, pady=5)
  btn_left.grid(row=1, column=1, padx=5, pady=5)
  btn_up.grid(row=0, column=2, padx=5, pady=5)
  btn_pause.grid(row=1, column=2, padx=5, pady=5)
  btn_down.grid(row=2, column=2, padx=5, pady=5)
  btn_right.grid(row=1, column=3, padx=5, pady=5)
  btn_rright.grid(row=1, column=4, padx=5, pady=5)
  btn_zoom_in.grid(row=0, column=5, padx=5, pady=5)
  btn_zoom_out.grid(row=2, column=5, padx=5, pady=5)

  btn_inc_pan.grid(row=3, column=0, padx=5, pady=5)
  btn_dec_pan.grid(row=4, column=0, padx=5, pady=5)
  btn_inc_tilt.grid(row=3, column=2, padx=5, pady=5)
  btn_dec_tilt.grid(row=4, column=2, padx=5, pady=5)
  btn_inc_zoom.grid(row=3, column=5, padx=5, pady=5)
  btn_dec_zoom.grid(row=4, column=5, padx=5, pady=5)

  btn_abs_move = tk.Button(root,
                           text="Move To",
                           command=ctrl.show_move_to_dialog)
  btn_abs_move_step = tk.Button(root,
                                text="Move To in Steps",
                                command=ctrl.show_move_to_steps_dialog)
  btn_abs_move_seq = tk.Button(root,
                               text="Move Sequence",
                               command=lambda: ctrl.show_move_sequence_dialog(
                                   config.CAM_MOVE_SEQS_PATH))

  btn_abs_move.grid(row=5, column=0, columnspan=2, padx=5, pady=10)
  btn_abs_move_step.grid(row=5, column=2, columnspan=2, padx=5, pady=10)
  btn_abs_move_seq.grid(row=5, column=4, columnspan=2, padx=5, pady=10)

  root.mainloop()


if __name__ == "__main__":
  main()
