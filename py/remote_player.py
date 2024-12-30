from flask import Flask, request, jsonify
import pygame
import logging
import os
import config

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s: %(message)s")

app = Flask(__name__)
pygame.mixer.init()


@app.route('/play', methods=['POST'])
def play_endpoint():
  data = request.json
  if data is None:
    logging.error("Invalid JSON in request")
    return jsonify({"error": "Invalid JSON"}), 400

  file_path = os.path.join(config.SOUNDS_PATH, data.get("file_name", ""))

  if not os.path.exists(file_path):
    logging.error(f"Cant find {file_path}")
    return jsonify({"error": f"Cant find {file_path}"}), 400

  try:
    pygame.mixer.music.load(file_path)
    pygame.mixer.music.play()
    logging.info(f"Playing audio: {file_path}")
    return jsonify({
        "file": os.path.basename(file_path),
        "status": "Playing",
    }), 200
  except Exception as e:
    logging.error(f"Failed to play audio {file_path}: {str(e)}")
    return jsonify({"error": str(e)}), 500


@app.route('/stop', methods=['POST'])
def stop_endpoint():
  pygame.mixer.music.stop()
  logging.info("Stopped audio playback")
  return jsonify({"status": "Stopped"}), 200


if __name__ == '__main__':
  logging.info("Starting audio server on port 5000")
  app.run(port=5000)
