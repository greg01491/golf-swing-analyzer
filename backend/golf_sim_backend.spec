from PyInstaller.utils.hooks import collect_all


datas = []
binaries = []
hiddenimports = []

for package in (
    "Pose2Sim",
    "cv2",
    "fastapi",
    "imageio_ffmpeg",
    "matplotlib",
    "onnxruntime",
    "opensim",
    "openvino",
    "pygrabber",
    "rtmlib",
    "sounddevice",
    "uvicorn",
):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

a = Analysis(
    ["run_server.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="golf-sim-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="golf-sim-backend",
)
