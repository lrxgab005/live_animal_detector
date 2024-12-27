"""
    Simple Tkinter interface for PTZ velocity control
"""

import tkinter as tk
import requests
from requests.auth import HTTPDigestAuth
import config


class PTZController:

  def __init__(self, root, max_duration_s=3 * 60):
    self.root = root
    self.user = config.USER
    self.password = config.PASSWORD
    self.host = config.HOST
    self.channel = 1
    self.base_url = f"http://{self.host}/ISAPI/PTZCtrl/channels/{self.channel}/continuous"
    self.vel_pan = 60
    self.vel_tilt = 50
    self.vel_zoom = 100
    self.t_pan_ms = 500
    self.t_tilt_ms = 1000
    self.t_zoom_ms = 500
    self.max_duration_s = max_duration_s

  def update_velocity(self, pan=0, tilt=0, zoom=0):
    xml_data = f"""
      <PTZData version="2.0" xmlns="http://www.isapi.org/ver20/XMLSchema">
        <pan>{pan}</pan>
        <tilt>{tilt}</tilt>
        <zoom>{zoom}</zoom>
      </PTZData>
    """
    requests.put(self.base_url,
                 data=xml_data,
                 headers={"Content-Type": "text/xml"},
                 auth=HTTPDigestAuth(self.user, self.password),
                 timeout=3)

  def move(self, pan=0, tilt=0, zoom=0, duration=5000):
    self.update_velocity(pan, tilt, zoom)
    if duration > 0:
      self.root.after(duration, self.stop)

  def stop(self):
    self.update_velocity(0, 0, 0)


def main():
  root = tk.Tk()
  root.title("PTZ Navigation")
  ctrl = PTZController(root)

  btn_up = tk.Button(
      root,
      text="↑",
      command=lambda: ctrl.move(0, ctrl.vel_tilt, 0, ctrl.t_tilt_ms))
  btn_down = tk.Button(
      root,
      text="↓",
      command=lambda: ctrl.move(0, -ctrl.vel_tilt, 0, ctrl.t_tilt_ms))
  btn_left = tk.Button(
      root,
      text="←",
      command=lambda: ctrl.move(-ctrl.vel_pan, 0, 0, ctrl.t_pan_ms))
  btn_right = tk.Button(
      root,
      text="→",
      command=lambda: ctrl.move(ctrl.vel_pan, 0, 0, ctrl.t_pan_ms))
  btn_zoom_in = tk.Button(
      root,
      text="+",
      command=lambda: ctrl.move(0, 0, ctrl.vel_zoom, ctrl.t_zoom_ms))
  btn_zoom_out = tk.Button(
      root,
      text="-",
      command=lambda: ctrl.move(0, 0, -ctrl.vel_zoom, ctrl.t_zoom_ms))
  btn_pause = tk.Button(root, text="⏸", command=ctrl.stop)

  # Infinite pan buttons
  btn_lleft = tk.Button(root,
                        text="⟸",
                        command=lambda: ctrl.move(-ctrl.vel_pan, 0, 0, 0))
  btn_rright = tk.Button(root,
                         text="⟹",
                         command=lambda: ctrl.move(ctrl.vel_pan, 0, 0, 0))

  btn_lleft.grid(row=1, column=0)
  btn_left.grid(row=1, column=1)
  btn_up.grid(row=0, column=2)
  btn_pause.grid(row=1, column=2)
  btn_down.grid(row=2, column=2)
  btn_right.grid(row=1, column=3)
  btn_rright.grid(row=1, column=4)
  btn_zoom_in.grid(row=0, column=5)
  btn_zoom_out.grid(row=2, column=5)

  root.mainloop()


if __name__ == "__main__":
  main()
