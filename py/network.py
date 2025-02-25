from typing import Any, Dict, Optional, Tuple, Union
import io
import json
import socket
import collections
import logging
import numpy as np

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s: %(message)s")

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def pythonize(d: Any) -> Any:
  """Transforms numpy arrays, float32, int64 to native Python dtypes."""
  if isinstance(d, dict):
    return {pythonize(k): pythonize(v) for k, v in d.items()}
  if isinstance(d, (np.ndarray, list)):
    return [pythonize(v) for v in d]
  if isinstance(d, np.float32):
    return float(d)
  if isinstance(d, np.int64):
    return int(d)
  if isinstance(d, collections.abc.KeysView):
    return list(d)
  return d


def send(port: int,
         data: Any,
         address: str = '127.0.0.1',
         sock: socket.socket = sock) -> None:
  msg = json.dumps(pythonize(data)).encode('utf8')
  sock.sendto(msg + b'\n', (address, port))


def create_udp_socket(port: int,
                      address: str,
                      timeout: Union[int, float] = 0) -> socket.socket:
  """Creates a UDP socket.

  Args:
    port: port to listen on
    address: address to listen on
    timeout: setting `None` makes the socket blocking, otherwise every call
      to `recvfrom()` will wait up to `timeout` seconds
  """
  sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  sock.settimeout(timeout)
  sock.bind((address, port))
  return sock


def get_json_and_address(
    sock: socket.socket,
    max_size: int = 4096) -> Tuple[Optional[Dict], Optional[Tuple]]:
  try:
    data, address = sock.recvfrom(max_size)
  except (socket.timeout, io.BlockingIOError):
    return None, None
  try:
    data = json.loads(data.decode('utf8'))
    return data, address
  except json.JSONDecodeError as e:
    logging.warning('Could not decode {!r} : {}'.format(data, e))
    return None, None


def get_json(sock: socket.socket, data: Any, max_size: int = 4096) -> Any:
  newdata, _ = get_json_and_address(sock, max_size=max_size)
  if newdata:
    return newdata
  return data


def get_ip() -> str:
  try:
    return socket.gethostbyname(socket.gethostname())
  except socket.gaierror:
    return 'get_ip:gaierror'
