import flask
from typing import Dict, Any, Optional
import pygame
import logging
import os
import config
import argparse

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s: %(message)s")


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description='Audio server')
  parser.add_argument('--host',
                      type=str,
                      default='0.0.0.0',
                      help='IP address to bind to (default: 127.0.0.1)')
  parser.add_argument('--port',
                      type=int,
                      default=5000,
                      help='Port to listen on (default: 5000)')
  return parser.parse_args()


app = flask.Flask(__name__)
pygame.mixer.init()


@app.route('/play', methods=['POST'])
def play_endpoint() -> tuple[flask.Response, int]:
  data: Optional[Dict[str, Any]] = flask.request.json
  if data is None:
    logging.error("Invalid JSON in flask.request")
    return flask.jsonify({"error": "Invalid JSON"}), 400

  file_path: str = os.path.join(config.SOUNDS_PATH, data.get("file_name", ""))

  if not os.path.exists(file_path):
    logging.error(f"Cant find {file_path}")
    return flask.jsonify({"error": f"Cant find {file_path}"}), 400

  try:
    pygame.mixer.music.stop()
    pygame.mixer.music.load(file_path)
    pygame.mixer.music.play(0)
    logging.info(f"Playing audio: {file_path}")
    return flask.jsonify({
        "file": os.path.basename(file_path),
        "status": "Playing",
    }), 200
  except Exception as e:
    logging.error(f"Failed to play audio {file_path}: {str(e)}")
    return flask.jsonify({"error": str(e)}), 500


@app.route('/stop', methods=['POST'])
def stop_endpoint() -> tuple[flask.Response, int]:
  pygame.mixer.music.stop()
  logging.info("Stopped audio playback")
  return flask.jsonify({"status": "Stopped"}), 200


if __name__ == '__main__':
  args: argparse.Namespace = parse_args()
  logging.info(f"Starting audio server on {args.host}:{args.port}")
  app.run(host=args.host, port=args.port)
