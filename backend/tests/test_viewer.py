import numpy as np

from golf_sim.pose.viewer import plot_frames, read_trc

_TRC_CONTENT = """PathFileType\t4\t(X/Y/Z)\ttest.trc
DataRate\tCameraRate\tNumFrames\tNumMarkers\tUnits\tOrigDataRate\tOrigDataStartFrame\tOrigNumFrames
60.0\t60.0\t3\t2\tm\t60.0\t0\t3
Frame#\tTime\tHip\t\t\tNeck\t\t
\t\tX1\tY1\tZ1\tX2\tY2\tZ2

0\t0.000\t0.1\t0.2\t0.9\t0.1\t0.2\t1.5
1\t0.017\t0.11\t0.21\t0.91\t0.11\t0.21\t1.51
2\t0.033\t0.12\t0.22\t0.92\t0.12\t0.22\t1.52
"""


def test_read_trc_parses_markers_times_and_coords(tmp_path):
    trc = tmp_path / "test.trc"
    trc.write_text(_TRC_CONTENT)

    marker_names, times, coords = read_trc(trc)

    assert marker_names == ["Hip", "Neck"]
    assert coords.shape == (3, 2, 3)
    assert times[1] == 0.017
    assert coords[0, 0].tolist() == [0.1, 0.2, 0.9]
    assert coords[2, 1].tolist() == [0.12, 0.22, 1.52]
    assert not np.isnan(coords).any()


def test_plot_frames_writes_png(tmp_path):
    trc = tmp_path / "test.trc"
    trc.write_text(_TRC_CONTENT)
    out = tmp_path / "qa.png"

    result = plot_frames(trc, out, num_frames=2)

    assert result == out
    assert out.stat().st_size > 0
