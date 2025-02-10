import logging
from tenacity import retry, stop_after_attempt, wait_fixed
import requests
from requests.auth import HTTPDigestAuth
import xml.etree.ElementTree as ET

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s: %(message)s")


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

  @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
  def _put(self, endpoint, xml_data, timeout=3):
    url = f"{self.base_url}/{endpoint}"
    response = self.session.put(url, data=xml_data, timeout=timeout)
    response.raise_for_status()
    return response.text

  @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
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

  def move_absolute(self, pan, tilt, zoom):
    xml_data = f"""
                <PTZData>
                  <AbsoluteHigh>
                  <elevation>{int(tilt)}</elevation>
                  <azimuth>{int(pan * 10)}</azimuth>
                  <absoluteZoom>{int(zoom)}</absoluteZoom>
                  </AbsoluteHigh>
                </PTZData>
                """
    return self._put("absolute", xml_data)

  @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
  def get_status(self):
    status_url = f"{self.base_url}/status"
    response = self.session.get(status_url, timeout=3)
    response.raise_for_status()

    ns = {"hik": "http://www.hikvision.com/ver20/XMLSchema"}
    root = ET.fromstring(response.text)
    pan = int(root.find(".//hik:AbsoluteHigh/hik:azimuth", ns).text)
    tilt = int(root.find(".//hik:AbsoluteHigh/hik:elevation", ns).text)
    zoom = int(root.find(".//hik:AbsoluteHigh/hik:absoluteZoom", ns).text)
    return {"pan": pan / 10.0, "tilt": tilt, "zoom": zoom}

  def go_to_preset(self, preset_id):
    return self._put(f"presets/{preset_id}/goto", "")

  def save_preset(self, preset_id):
    xml_data = f"""<PTZPreset>
                    <id>{preset_id}</id>
                    <presetName>{preset_id}</presetName>
                  </PTZPreset>
                """
    return self._post("presets", xml_data)

  @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
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
