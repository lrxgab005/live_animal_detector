#!/usr/bin/env python3
"""
Expanded PTZ controller with timed moves, continuous moves, absolute moves,
and preset management (save preset / go to preset).
"""

import logging
import ptz_widgets as pw

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s: %(message)s")


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

  pw.start_ptz_controller(args.camera_config)


if __name__ == "__main__":
  main()
