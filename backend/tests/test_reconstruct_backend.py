import matplotlib

from golf_sim.pose.reconstruct import _force_headless_matplotlib


def test_forces_headless_backend():
    # Start from a different (but still always-available, no GUI toolkit
    # required) backend so the assertion actually proves the function
    # switches it, rather than passing vacuously.
    matplotlib.use("pdf")
    _force_headless_matplotlib()
    assert matplotlib.get_backend().lower() == "agg"
