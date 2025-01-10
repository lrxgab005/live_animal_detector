import cv2
import numpy as np
import pytesseract


class TextExtractor:

  def __init__(self):
    pass

  def extract_text(self, frame: np.ndarray, bbox: tuple) -> dict:
    x, y, w, h = bbox
    gray_roi = cv2.cvtColor(frame[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
    _, thresh_roi = cv2.threshold(gray_roi, 0, 255,
                                  cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    data = pytesseract.image_to_data(thresh_roi,
                                     output_type=pytesseract.Output.DICT)
    text, conf = self._parse_ocr_result(data)
    return {"text": text, "confidence": conf}

  def _parse_ocr_result(self, ocr_data: dict) -> tuple:
    text = []
    confs = []
    for idx, word in enumerate(ocr_data["text"]):
      if word.strip():
        text.append(word)
        confs.append(
            float(ocr_data["conf"][idx]) if ocr_data["conf"][idx].isdigit(
            ) else 0.0)
    if not confs:
      return "", 0.0
    average_conf = sum(confs) / len(confs)
    return (" ".join(text), average_conf)
