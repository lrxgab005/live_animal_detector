#!/usr/bin/env python3
"""
Expanded PTZ controller with timed moves, continuous moves, absolute moves,
and preset management (save preset / go to preset).
"""

import tkinter as tk
from tkinter import messagebox  # For error dialogs
import requests
from requests.auth import HTTPDigestAuth
import xml.etree.ElementTree as ET
import config  # your config module provides HOST, PORT, USER, PASSWORD
import numpy as np
import time


class PTZCamera:
  """
    Low-level API wrapper for the PTZ camera.
    Provides methods for continuous and absolute moves as well as preset management.
  """

  def __init__(self, host, port, user, password, channel=1):
    self.host = host
    self.port = port
    self.user = user
    self.password = password
    self.channel = channel
    self.session = requests.Session()
    self.session.auth = HTTPDigestAuth(user, password)
    self.session.headers.update({"Content-Type": "text/xml"})
    self.base_url = f"http://{host}:{port}/ISAPI/PTZCtrl/channels/{channel}"

  def _put(self, endpoint, xml_data, timeout=3):
    url = f"{self.base_url}/{endpoint}"
    response = self.session.put(url, data=xml_data, timeout=timeout)
    response.raise_for_status()
    return response.text

  def _post(self, endpoint, xml_data, timeout=3):
    url = f"{self.base_url}/{endpoint}"
    response = self.session.post(url, data=xml_data, timeout=timeout)
    response.raise_for_status()
    return response.text

  def continuous_move(self, pan, tilt, zoom):
    xml_data = f"""
                <PTZData>
                  <pan>{pan}</pan>
                  <tilt>{tilt}</tilt>
                  <zoom>{zoom}</zoom>
                </PTZData>
                """
    return self._put("continuous", xml_data)

  def stop(self):
    return self.continuous_move(0, 0, 0)

  def move_absolute(self, elevation, azimuth, zoom):
    xml_data = f"""
                <PTZData>
                  <AbsoluteHigh>
                  <elevation>{int(elevation)}</elevation>
                  <azimuth>{int(azimuth * 10)}</azimuth>
                  <absoluteZoom>{int(zoom)}</absoluteZoom>
                  </AbsoluteHigh>
                </PTZData>
                """
    return self._put("absolute", xml_data)

  def get_status(self):
    status_url = f"{self.base_url}/status"
    response = self.session.get(status_url, timeout=3)
    response.raise_for_status()

    ns = {"hik": "http://www.hikvision.com/ver20/XMLSchema"}
    root = ET.fromstring(response.text)
    elevation = int(root.find(".//hik:AbsoluteHigh/hik:elevation", ns).text)
    azimuth = int(root.find(".//hik:AbsoluteHigh/hik:azimuth", ns).text)
    zoom = int(root.find(".//hik:AbsoluteHigh/hik:absoluteZoom", ns).text)
    return {"elevation": elevation, "azimuth": azimuth / 10.0, "zoom": zoom}

  def go_to_preset(self, preset_id):
    return self._put(f"presets/{preset_id}/goto", "")

  def save_preset(self, preset_id):
    xml_data = f"""<PTZPreset>
                    <id>{preset_id}</id>
                    <presetName>{preset_id}</presetName>
                  </PTZPreset>
                """
    return self._post("presets", xml_data)

  def list_presets(self):
    url = f"{self.base_url}/presets"
    response = self.session.get(url, timeout=3)
    response.raise_for_status()
    presets = {}
    ns = {"hik": "http://www.hikvision.com/ver20/XMLSchema"}
    root = ET.fromstring(response.text)
    for preset in root.findall(".//hik:PTZPreset", ns):
      pid = preset.find("hik:id", ns).text
      name = preset.find("hik:presetName", ns).text
      presets[pid] = name
    return presets


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
      print("Status:", self.camera.get_status())
      self.root.after(duration, self.stop)
    except Exception as e:
      print("Error during timed move:", e)

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
        print("Error during continuous move:", e)
      self.root.after(self.continuous_interval_ms,
                      self._schedule_continuous_move)

  def stop(self):
    self._keep_moving = False
    try:
      self.camera.stop()
    except Exception as e:
      print("Error stopping movement:", e)

  def move_absolute(self, elevation, azimuth, zoom):
    try:
      self.camera.move_absolute(elevation, azimuth, zoom)
    except Exception as e:
      print("Error during absolute move:", e)

  def move_absolute_with_speed(self,
                               target_elevation,
                               target_azimuth,
                               target_zoom,
                               steps=10,
                               wait_time_ms=1000):
    try:
      current_status = self.camera.get_status()
    except Exception as e:
      print("Error retrieving camera status:", e)
      return

    # Extract the current positions.
    current_elev = current_status["elevation"]
    current_azim = current_status["azimuth"]
    current_zoom = current_status["zoom"]

    # Compute the intermediate positions with numpy.linspace.
    elev_steps = np.linspace(current_elev, target_elevation, steps)
    azim_steps = np.linspace(current_azim, target_azimuth, steps)
    zoom_steps = np.linspace(current_zoom, target_zoom, steps)

    for elev, azim, zoom in zip(elev_steps, azim_steps, zoom_steps):
      try:
        # Send an absolute move command for the current step.
        self.camera.move_absolute(elev, azim, zoom)
        time.sleep(wait_time_ms / 1000)
      except Exception as e:
        print(f"Error at step: {elev}, {azim}, {zoom}: {e}")

  def goto_preset(self, preset_id):
    try:
      self.camera.go_to_preset(preset_id)
    except Exception as e:
      print("Error going to preset:", e)

  def save_preset(self, preset_id):
    try:
      self.camera.save_preset(preset_id)
    except Exception as e:
      print("Error saving preset:", e)

  def show_move_absolute_dialog(self):
    AbsoluteMoveSpeedDialog(self.root, self.move_absolute_with_speed,
                            self.camera.get_status())

  def show_save_preset_dialog(self):
    PresetSaveDialog(self.root, self.save_preset)

  def show_goto_preset_dialog(self):
    PresetGotoDialog(self.root, self.goto_preset)


class AbsoluteMoveSpeedDialog(tk.Toplevel):
  """
    A dialog that collects absolute move target values along with 
    movement speed parameters. The dialog includes fields for elevation, 
    azimuth, zoom, number of steps, and wait time (ms).
  """

  def __init__(self, master, callback, status, steps=10, wait_time_ms=2000):
    super().__init__(master)
    self.callback = callback
    self.title("Absolute Move with Speed")
    self.grab_set()

    self.field_names = [
        "elevation", "azimuth", "zoom", "steps", "wait_time_ms"
    ]
    self.fields = {}
    status["steps"] = steps
    status["wait_time_ms"] = wait_time_ms

    for i, field in enumerate(self.field_names):
      tk.Label(self, text=field.capitalize() + ":").grid(row=i,
                                                         column=0,
                                                         padx=5,
                                                         pady=5)
      entry = tk.Entry(self)
      entry.grid(row=i, column=1, padx=5, pady=5)
      entry.insert(0, str(status.get(field, "")))
      self.fields[field] = entry

    btn_ok = tk.Button(self, text="Move", command=self.on_ok)
    btn_ok.grid(row=len(self.field_names), column=0, padx=5, pady=5)
    btn_cancel = tk.Button(self, text="Cancel", command=self.destroy)
    btn_cancel.grid(row=len(self.field_names), column=1, padx=5, pady=5)

  def on_ok(self):
    try:
      elevation = float(self.fields["elevation"].get())
      azimuth = float(self.fields["azimuth"].get())
      zoom = float(self.fields["zoom"].get())
      steps = int(self.fields["steps"].get())
      wait_time_ms = int(self.fields["wait_time_ms"].get())
    except ValueError:
      messagebox.showerror("Invalid Input",
                           "Please enter valid numeric values")
      return
    self.callback(elevation, azimuth, zoom, steps, wait_time_ms)
    self.destroy()


class PresetSaveDialog(tk.Toplevel):
  """
    A dialog window that collects a preset ID to save the current position.
  """

  def __init__(self, master, callback):
    super().__init__(master)
    self.callback = callback
    self.title("Save Preset")
    self.grab_set()  # Make modal

    tk.Label(self, text="Preset ID:").grid(row=0, column=0, padx=5, pady=5)
    self.entry_preset = tk.Entry(self)
    self.entry_preset.grid(row=0, column=1, padx=5, pady=5)

    btn_ok = tk.Button(self, text="Save", command=self.on_ok)
    btn_ok.grid(row=1, column=0, padx=5, pady=5)
    btn_cancel = tk.Button(self, text="Cancel", command=self.destroy)
    btn_cancel.grid(row=1, column=1, padx=5, pady=5)

  def on_ok(self):
    try:
      preset_id = int(self.entry_preset.get())
    except ValueError:
      messagebox.showerror("Invalid Input",
                           "Please enter a valid numeric preset ID")
      return
    self.callback(preset_id)
    self.destroy()


class PresetGotoDialog(tk.Toplevel):
  """
    A dialog window that collects a preset ID to move to a saved position.
  """

  def __init__(self, master, callback):
    super().__init__(master)
    self.callback = callback
    self.title("Go To Preset")
    self.grab_set()  # Make modal

    tk.Label(self, text="Preset ID:").grid(row=0, column=0, padx=5, pady=5)
    self.entry_preset = tk.Entry(self)
    self.entry_preset.grid(row=0, column=1, padx=5, pady=5)

    btn_ok = tk.Button(self, text="Go", command=self.on_ok)
    btn_ok.grid(row=1, column=0, padx=5, pady=5)
    btn_cancel = tk.Button(self, text="Cancel", command=self.destroy)
    btn_cancel.grid(row=1, column=1, padx=5, pady=5)

  def on_ok(self):
    try:
      preset_id = int(self.entry_preset.get())
    except ValueError:
      messagebox.showerror("Invalid Input",
                           "Please enter a valid numeric preset ID")
      return
    self.callback(preset_id)
    self.destroy()


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

  # --- Layout (grid as per your original design) ---
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

  # --- New buttons for custom absolute move and preset management ---
  btn_abs_move = tk.Button(root,
                           text="Absolute Move",
                           command=ctrl.show_move_absolute_dialog)
  btn_save_preset = tk.Button(root,
                              text="Save Preset",
                              command=ctrl.show_save_preset_dialog)
  btn_goto_preset = tk.Button(root,
                              text="Go To Preset",
                              command=ctrl.show_goto_preset_dialog)

  # Place these new buttons on a new row below the existing controls:
  btn_abs_move.grid(row=5, column=0, columnspan=2, padx=5, pady=10)
  btn_save_preset.grid(row=5, column=2, columnspan=2, padx=5, pady=10)
  btn_goto_preset.grid(row=5, column=4, columnspan=2, padx=5, pady=10)

  root.mainloop()


if __name__ == "__main__":
  main()
