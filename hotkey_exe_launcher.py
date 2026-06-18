import subprocess
import sys
from pathlib import Path


TOOLS = {
    "merge": {
        "script": "start_merge_hotkey.ps1",
        "key": "F2",
        "label": "MergeText_AI hotkey",
    },
    "release": {
        "script": "start_release_clipping_mask.ps1",
        "key": "F3",
        "label": "ReleaseClippingMask hotkey",
    },
}


def resource_dir() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def detect_tool() -> str:
    if "--release" in sys.argv:
        return "release"
    if "--merge" in sys.argv:
        return "merge"
    exe_name = Path(sys.argv[0]).stem.lower()
    if "release" in exe_name or "clipping" in exe_name:
        return "release"
    return "merge"


def main() -> int:
    tool = TOOLS[detect_tool()]
    script_path = resource_dir() / tool["script"]
    if not script_path.exists():
        print(f"Missing bundled PowerShell script: {script_path}")
        return 2

    args = [
        "powershell.exe",
        "-NoProfile",
        "-Sta",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        "-Key",
        tool["key"],
    ]

    if "--test" in sys.argv:
        args.append("-Test")

    print(f"{tool['label']} launcher")
    print(f"Script: {script_path}")
    print("Close this window to stop the hotkey.")
    print()
    return subprocess.call(args)


if __name__ == "__main__":
    raise SystemExit(main())
