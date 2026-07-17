"""Probe for connected USB cameras.

OpenCV has no cross-platform "list camera devices" call, so this opens each
candidate index in turn and checks whether it actually produces a frame.
"""

from __future__ import annotations

import cv2
from pydantic import BaseModel


class CameraInfo(BaseModel):
    index: int
    width: int
    height: int
    fps: float


def enumerate_cameras(max_index: int = 10) -> list[CameraInfo]:
    found: list[CameraInfo] = []
    for index in range(max_index):
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        try:
            if not cap.isOpened():
                continue
            ok, _ = cap.read()
            if not ok:
                continue
            found.append(
                CameraInfo(
                    index=index,
                    width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                    height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                    fps=cap.get(cv2.CAP_PROP_FPS),
                )
            )
        finally:
            cap.release()
    return found


if __name__ == "__main__":
    for cam in enumerate_cameras():
        print(cam)
