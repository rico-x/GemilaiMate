from pathlib import Path
Import("env")
assets = Path(env["PROJECT_DIR"]) / "src/display/webassets"
if not all((assets / name).is_file() for name in ["web_ui.bin", "web_ui_manifest.h", "web_ui_blob.S"]):
    raise RuntimeError("Build the GemilaiMate web UI first: bash scripts/build_webui.sh")
