"""
  PTZ controller with non-blocking infinite move scheduling
"""

import tkinter as tk
import requests
from requests.auth import HTTPDigestAuth
import config
import argparse
import xml.etree.ElementTree as ET


class PTZController:

  def __init__(self, root, max_duration_s=3 * 60):
    self.root = root
    self.user = config.USER
    self.password = config.PASSWORD
    self.host = config.HOST
    self.port = config.PORT
    self.channel = 1
    self.base_url = f"http://{self.host}:{self.port}/ISAPI/PTZCtrl/channels/{self.channel}/continuous"
    self.vel_pan = 50
    self.vel_tilt = 50
    self.vel_zoom = 50
    self.t_pan_ms = 500
    self.t_tilt_ms = 500
    self.t_zoom_ms = 500
    self.max_duration_s = max_duration_s
    self._keep_moving = False
    self._move_args = (0, 0, 0)

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

  def get_status(self):
    status_url = f"http://{self.host}:{self.port}/ISAPI/PTZCtrl/channels/{self.channel}/status"
    response = requests.get(status_url,
                            auth=HTTPDigestAuth(self.user, self.password),
                            timeout=3)
    return self.parse_status(response.text)

  def parse_status(self, xml_text):
    """Parse PTZ status XML response and return position values."""

    # Parse XML
    root = ET.fromstring(xml_text)

    # Define namespace
    ns = {"hik": "http://www.hikvision.com/ver20/XMLSchema"}

    # Extract values
    elevation = root.find(".//hik:AbsoluteHigh/hik:elevation", ns).text
    azimuth = root.find(".//hik:AbsoluteHigh/hik:azimuth", ns).text
    zoom = root.find(".//hik:AbsoluteHigh/hik:absoluteZoom", ns).text

    # Convert to appropriate types
    elevation, azimuth, zoom = int(elevation), int(azimuth), int(zoom)

    return {'elevation': elevation, 'azimuth': azimuth, 'zoom': zoom}

  def move(self, pan=0, tilt=0, zoom=0, duration=5000):
    print(f"pan={pan}, tilt={tilt}, zoom={zoom}")
    self.update_velocity(pan, tilt, zoom)
    print(self.get_status())
    if duration > 0:
      self.root.after(duration, self.stop)
    else:
      self._keep_moving = True
      self._move_args = (pan, tilt, zoom)
      self._schedule_continuous_move()

  def _schedule_continuous_move(self):
    # Repeatedly call update_velocityin a non-blocking way
    if self._keep_moving:
      pan, tilt, zoom = self._move_args
      self.update_velocity(pan, tilt, zoom)
      self.root.after(1000, self._schedule_continuous_move)

  def stop(self):
    self._keep_moving = False
    self.update_velocity(0, 0, 0)


def main():

  parser = argparse.ArgumentParser(
      description='PTZ controller with non-blocking infinite move scheduling')
  parser.add_argument('--camera_config',
                      required=True,
                      help='Path to network camera stream config file.'
                      'To create run: python py/create_cam_config.py')
  args = parser.parse_args()

  if args.camera_config is not None:
    config.load_cam_settings(args.camera_config)

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

  btn_lleft = tk.Button(root,
                        text="⟸",
                        command=lambda: ctrl.move(-ctrl.vel_pan, 0, 0, 0))
  btn_rright = tk.Button(root,
                         text="⟹",
                         command=lambda: ctrl.move(ctrl.vel_pan, 0, 0, 0))

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

  btn_lleft.grid(row=1, column=0)
  btn_left.grid(row=1, column=1)
  btn_up.grid(row=0, column=2)
  btn_pause.grid(row=1, column=2)
  btn_down.grid(row=2, column=2)
  btn_right.grid(row=1, column=3)
  btn_rright.grid(row=1, column=4)
  btn_zoom_in.grid(row=0, column=5)
  btn_zoom_out.grid(row=2, column=5)

  btn_inc_pan.grid(row=3, column=0)
  btn_dec_pan.grid(row=4, column=0)
  btn_inc_tilt.grid(row=3, column=2)
  btn_dec_tilt.grid(row=4, column=2)
  btn_inc_zoom.grid(row=3, column=5)
  btn_dec_zoom.grid(row=4, column=5)

  root.mainloop()


if __name__ == "__main__":
  main()
