import ctypes
import ctypes.wintypes as wintypes
import subprocess
import sys
import threading
import time
from pathlib import Path


WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
GA_ROOT = 2
SW_MAXIMIZE = 3
VK_F2 = 0x71
VK_F3 = 0x72
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
MIN_TRIGGER_INTERVAL_SECONDS = 0.35

SCRIPTS = {
    VK_F2: "MergeText_AI_Quick.jsx",
    VK_F3: "ReleaseClippingMask.jsx",
}

ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong
LowLevelKeyboardProc = ctypes.WINFUNCTYPE(
    wintypes.LPARAM,
    ctypes.c_int,
    wintypes.WPARAM,
    wintypes.LPARAM,
)
EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int,
    LowLevelKeyboardProc,
    wintypes.HINSTANCE,
    wintypes.DWORD,
]
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.CallNextHookEx.argtypes = [
    wintypes.HHOOK,
    ctypes.c_int,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
user32.CallNextHookEx.restype = wintypes.LPARAM
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.IsZoomed.argtypes = [wintypes.HWND]
user32.IsZoomed.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.GetMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG),
    wintypes.HWND,
    wintypes.UINT,
    wintypes.UINT,
]
user32.GetMessageW.restype = wintypes.BOOL

kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL

hook_handle = None
hook_callback_ref = None
last_trigger = {VK_F2: 0.0, VK_F3: 0.0}


def resource_dir() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def resource_path(name: str) -> Path:
    return resource_dir() / name


def get_process_image_path(pid: int) -> str:
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return buffer.value
        return ""
    finally:
        kernel32.CloseHandle(handle)


def is_illustrator_path(path: str) -> bool:
    return Path(path).name.lower() == "illustrator.exe"


def get_foreground_illustrator():
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    root = user32.GetAncestor(hwnd, GA_ROOT) or hwnd
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(root, ctypes.byref(pid))
    if not pid.value:
        return None
    exe_path = get_process_image_path(pid.value)
    if not is_illustrator_path(exe_path):
        return None
    return root, exe_path, bool(user32.IsZoomed(root))


def illustrator_windows():
    windows = []

    def enum_callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value and is_illustrator_path(get_process_image_path(pid.value)):
            windows.append(hwnd)
        return True

    callback_ref = EnumWindowsProc(enum_callback)
    user32.EnumWindows(callback_ref, 0)
    return windows


def restore_maximized_illustrator(original_hwnd: int):
    for delay in (0.05, 0.12, 0.25, 0.5, 1.0, 1.8, 3.0):
        time.sleep(delay)
        if user32.IsWindow(original_hwnd) and not user32.IsZoomed(original_hwnd):
            user32.ShowWindow(original_hwnd, SW_MAXIMIZE)
        for hwnd in illustrator_windows():
            if not user32.IsZoomed(hwnd):
                user32.ShowWindow(hwnd, SW_MAXIMIZE)


def run_script(vk_code: int, illustrator):
    script_name = SCRIPTS.get(vk_code)
    if not script_name:
        return
    script_path = resource_path(script_name)
    if not script_path.exists():
        print(f"Missing bundled script: {script_name}", flush=True)
        return

    hwnd, illustrator_exe, was_maximized = illustrator
    try:
        subprocess.Popen(
            [illustrator_exe, str(script_path)],
            close_fds=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        key_name = "F2" if vk_code == VK_F2 else "F3"
        print(f"{time.strftime('%H:%M:%S')} {key_name}: {script_name}", flush=True)
    except OSError as exc:
        print(f"Failed to run Illustrator script: {exc}", flush=True)
        return

    if was_maximized:
        threading.Thread(
            target=restore_maximized_illustrator,
            args=(hwnd,),
            daemon=True,
        ).start()


def hook_callback(n_code, w_param, l_param):
    if n_code >= 0 and w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
        event = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
        vk_code = int(event.vkCode)
        if vk_code in SCRIPTS:
            illustrator = get_foreground_illustrator()
            if illustrator:
                now = time.monotonic()
                if now - last_trigger[vk_code] >= MIN_TRIGGER_INTERVAL_SECONDS:
                    last_trigger[vk_code] = now
                    run_script(vk_code, illustrator)
                return 1
    return user32.CallNextHookEx(hook_handle, n_code, w_param, l_param)


def validate_bundle() -> int:
    required = ["MergeText_AI.jsx", "MergeText_AI_Quick.jsx", "ReleaseClippingMask.jsx"]
    missing = [name for name in required if not resource_path(name).exists()]
    if missing:
        print("Missing bundled files: " + ", ".join(missing))
        return 2
    print("Bundle OK.")
    print("Scripts: " + str(resource_dir()))
    illustrator = get_foreground_illustrator()
    if illustrator:
        print("Foreground Illustrator: " + illustrator[1])
    else:
        print("Foreground Illustrator: not detected")
    return 0


def start_hook() -> int:
    global hook_handle, hook_callback_ref

    hook_callback_ref = LowLevelKeyboardProc(hook_callback)
    module_handle = kernel32.GetModuleHandleW(None)
    hook_handle = user32.SetWindowsHookExW(WH_KEYBOARD_LL, hook_callback_ref, module_handle, 0)
    if not hook_handle:
        err = ctypes.get_last_error()
        print(f"Failed to install keyboard hook. Windows error: {err}")
        return 1

    print("Illustrator hotkeys are running.")
    print("F2: merge selected text frames")
    print("F3: release selected clipping mask")
    print("Hotkeys only run when Adobe Illustrator is the foreground app.")
    print("Close this window or press Ctrl+C to stop.")
    print()

    msg = wintypes.MSG()
    try:
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            pass
    except KeyboardInterrupt:
        return 0
    finally:
        if hook_handle:
            user32.UnhookWindowsHookEx(hook_handle)
            hook_handle = None
    return 0


def main() -> int:
    if "--test" in sys.argv:
        return validate_bundle()
    return start_hook()


if __name__ == "__main__":
    raise SystemExit(main())
