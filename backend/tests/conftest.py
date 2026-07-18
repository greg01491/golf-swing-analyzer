"""Shared test fixtures: a synthetic golf swing with a full enough marker
set (including elbows) for P-position detection and ideal-pose generation,
not just the metrics engine's own synthetic fixture in test_metrics.py."""

import numpy as np
import pytest

from golf_sim.trc import LandmarkSequence

FPS = 60.0
ADDRESS_FRAMES = 30
BACKSWING_FRAMES = 60
DOWNSWING_FRAMES = 20
FOLLOW_FRAMES = 30
SHOULDER_TURN = 90.0
HIP_TURN = 45.0

MARKER_NAMES = [
    "Hip",
    "RHip",
    "LHip",
    "Neck",
    "Head",
    "RAnkle",
    "LAnkle",
    "RShoulder",
    "LShoulder",
    "RElbow",
    "LElbow",
    "RWrist",
    "LWrist",
]


def _rot(width: float, angle_deg: float) -> tuple[np.ndarray, np.ndarray]:
    a = np.radians(angle_deg)
    half = np.array([np.cos(a), np.sin(a), 0.0]) * width / 2
    return -half, half


def make_synthetic_swing(shoulder_turn=SHOULDER_TURN, hip_turn=HIP_TURN) -> LandmarkSequence:
    n = ADDRESS_FRAMES + BACKSWING_FRAMES + DOWNSWING_FRAMES + FOLLOW_FRAMES
    times = np.arange(n) / FPS

    progress = np.zeros(n)
    top_end = ADDRESS_FRAMES + BACKSWING_FRAMES
    impact_end = top_end + DOWNSWING_FRAMES
    progress[ADDRESS_FRAMES:top_end] = np.linspace(0, 1, BACKSWING_FRAMES)
    progress[top_end:impact_end] = np.linspace(1, 0, DOWNSWING_FRAMES)

    # follow-through progress continues past impact independently (not a
    # mirror of backswing progress) so hands keep rising to a finish
    follow_progress = np.zeros(n)
    follow_progress[impact_end:] = np.linspace(0, 1, n - impact_end)

    hand_height = np.full(n, 0.8)
    hand_height[ADDRESS_FRAMES:top_end] = 0.8 + 0.9 * progress[ADDRESS_FRAMES:top_end]
    hand_height[top_end:impact_end] = np.linspace(1.7, 0.7, DOWNSWING_FRAMES)
    hand_height[impact_end:] = 0.7 + 1.0 * follow_progress[impact_end:]

    coords = np.zeros((n, len(MARKER_NAMES), 3))
    idx = {name: i for i, name in enumerate(MARKER_NAMES)}

    for f in range(n):
        hip_center = np.array([0.0, 0.0, 1.0])
        shoulder_center = np.array([0.0, 0.2, 1.4])
        coords[f, idx["Hip"]] = hip_center
        coords[f, idx["Neck"]] = shoulder_center
        coords[f, idx["Head"]] = shoulder_center + np.array([0.0, 0.0, 0.2])
        coords[f, idx["RAnkle"]] = np.array([0.2, 0.0, 0.05])
        coords[f, idx["LAnkle"]] = np.array([-0.2, 0.0, 0.05])

        # rotation angle: backswing progress going out, follow-through progress
        # going the opposite way (mirrors real swing rotation reversing after impact)
        rot_progress = progress[f] - follow_progress[f]
        l_hip, r_hip = _rot(0.3, hip_turn * rot_progress)
        coords[f, idx["LHip"]] = hip_center + l_hip
        coords[f, idx["RHip"]] = hip_center + r_hip
        l_sh, r_sh = _rot(0.4, shoulder_turn * rot_progress)
        coords[f, idx["LShoulder"]] = shoulder_center + l_sh
        coords[f, idx["RShoulder"]] = shoulder_center + r_sh

        hands = np.array([0.3, 0.3 * rot_progress, hand_height[f]])
        lead_shoulder = coords[f, idx["LShoulder"]]
        elbow = (lead_shoulder + hands) / 2
        coords[f, idx["LWrist"]] = hands
        coords[f, idx["LElbow"]] = elbow
        coords[f, idx["RWrist"]] = hands
        coords[f, idx["RElbow"]] = elbow

    return LandmarkSequence(marker_names=MARKER_NAMES, times=times, coords=coords)


@pytest.fixture
def synthetic_swing_full():
    return make_synthetic_swing()
