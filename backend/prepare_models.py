import os
from pathlib import Path


model_root = Path(__file__).resolve().parent / "runtime-models"
os.environ["TORCH_HOME"] = str(model_root)

from rtmlib import BodyWithFeet  # noqa: E402


if __name__ == "__main__":
    BodyWithFeet(mode="balanced", backend="onnxruntime", device="cpu")
    checkpoints = list((model_root / "hub" / "checkpoints").glob("*.onnx"))
    if len(checkpoints) < 2:
        raise RuntimeError("RTMPose model preparation did not produce both ONNX checkpoints")
