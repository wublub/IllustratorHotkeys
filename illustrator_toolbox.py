import ctypes
import ctypes.wintypes as wintypes
import json
import os
import queue
import shutil
import string
import subprocess
import sys
import threading
import time
import winreg
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


APP_NAME = "Illustrator Script Toolbox"
SCRIPT_FILES = ("MergeText_AI.jsx", "MergeText_AI_Quick.jsx", "ReleaseClippingMask.jsx")
HOTKEY_MERGE = 1201
HOTKEY_RELEASE = 1202
VK_F2 = 0x71
VK_F3 = 0x72
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
SW_MAXIMIZE = 3
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
COM_TIMEOUT_SECONDS = 15


user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


def resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


def app_data_dir() -> Path:
    bases = [
        os.environ.get("LOCALAPPDATA"),
        os.environ.get("TEMP"),
        os.environ.get("TMP"),
        str(Path.cwd()),
    ]
    last_error = None
    for base in bases:
        if not base:
            continue
        path = Path(base) / "IllustratorScriptToolbox"
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".write_test"
            probe.write_text("ok", encoding="ascii")
            probe.unlink(missing_ok=True)
            return path
        except OSError as exc:
            last_error = exc
    raise last_error or OSError("No writable application data directory found.")


def ensure_runtime_scripts() -> Path:
    target = app_data_dir() / "scripts"
    target.mkdir(parents=True, exist_ok=True)
    for name in SCRIPT_FILES:
        src = resource_path(name)
        dst = target / name
        if not src.exists():
            raise FileNotFoundError(f"Missing bundled script: {name}")
        if not dst.exists() or src.read_bytes() != dst.read_bytes():
            shutil.copy2(src, dst)
    return target


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


def is_illustrator_process(pid: int) -> bool:
    path = get_process_image_path(pid)
    return Path(path).name.lower() == "illustrator.exe"


def foreground_is_illustrator() -> bool:
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return False
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return bool(pid.value and is_illustrator_process(pid.value))


def illustrator_windows():
    windows = []
    enum_proc_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value and is_illustrator_process(pid.value):
            windows.append((hwnd, bool(user32.IsZoomed(hwnd))))
        return True

    callback_ref = enum_proc_type(callback)
    user32.EnumWindows(callback_ref, 0)
    return windows


def restore_maximized_illustrator(snapshot):
    if not any(was_zoomed for _hwnd, was_zoomed in snapshot):
        return
    for delay in (0.15, 0.35, 0.75, 1.25):
        time.sleep(delay)
        for hwnd, _was_zoomed in illustrator_windows():
            user32.ShowWindow(hwnd, SW_MAXIMIZE)


def subprocess_command_args(*args: str):
    if getattr(sys, "frozen", False):
        return [sys.executable, *args]
    return [sys.executable, str(Path(__file__).resolve()), *args]


def execute_jsx_file(script_path: Path, timeout: int = COM_TIMEOUT_SECONDS):
    if not script_path.exists():
        raise FileNotFoundError(str(script_path))

    before_windows = illustrator_windows()
    result_path = app_data_dir() / ("run_result_%s_%d.json" % (os.getpid(), int(time.time() * 1000)))
    try:
        try:
            completed = subprocess.run(
                subprocess_command_args("--run-jsx", str(script_path), str(result_path)),
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                "Illustrator 自动化入口 %d 秒内没有响应。"
                "这通常是 Illustrator COM 自动化服务未正常注册或被后台实例卡住。"
                % timeout
            ) from exc

        payload = {}
        if result_path.exists():
            try:
                payload = json.loads(result_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = {}

        if completed.returncode != 0 or not payload.get("ok", False):
            detail = payload.get("message") or (completed.stderr or completed.stdout or "").strip()
            raise RuntimeError(detail or "Illustrator automation failed.")

        return payload.get("message", "")
    finally:
        restore_maximized_illustrator(before_windows)
        try:
            result_path.unlink(missing_ok=True)
        except OSError:
            pass


def execute_jsx_file_com(script_path: Path):
    if not script_path.exists():
        raise FileNotFoundError(str(script_path))

    pythoncom = None
    initialized = False
    try:
        import pythoncom
        from win32com.client import dynamic

        pythoncom.CoInitialize()
        initialized = True
        try:
            dispatch = pythoncom.GetActiveObject("Illustrator.Application")
            app = dynamic.Dispatch(dispatch)
        except Exception:
            app = dynamic.Dispatch("Illustrator.Application")
        try:
            app.Visible = True
        except Exception:
            pass
        app.DoJavaScriptFile(str(script_path))
        return ""
    finally:
        if initialized and pythoncom is not None:
            pythoncom.CoUninitialize()


def prepare_menu_script(script_name: str):
    ensure_runtime_scripts()
    script_dirs = find_script_dirs()
    if not script_dirs:
        raise RuntimeError("没有自动找到 Illustrator 的 Scripts/脚本 目录。请点“选择目录”手动指定后安装。")

    target = script_dirs[0]
    install_scripts(target)
    menu_name = Path(script_name).stem
    return (
        "已安装/更新到 Illustrator 菜单目录：\n%s\n\n"
        "请重启 Illustrator，然后从 文件 > 脚本 > %s 运行。"
        % (target, menu_name)
    )


def test_illustrator_bridge():
    test_path = app_data_dir() / "bridge_test.jsx"
    try:
        with open(test_path, "w", encoding="utf-8") as test_file:
            test_file.write("var __illustratorToolboxBridgeTest = true;\n")
        execute_jsx_file(test_path)
        return "Illustrator COM bridge test passed."
    finally:
        try:
            test_path.unlink(missing_ok=True)
        except OSError:
            pass


def registry_illustrator_roots():
    roots = set()
    hives = (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER)
    keys = (
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    )
    for hive in hives:
        for key_path in keys:
            try:
                with winreg.OpenKey(hive, key_path) as key:
                    count = winreg.QueryInfoKey(key)[0]
                    for index in range(count):
                        try:
                            sub_name = winreg.EnumKey(key, index)
                            with winreg.OpenKey(key, sub_name) as sub:
                                display = _reg_value(sub, "DisplayName")
                                if "illustrator" not in display.lower():
                                    continue
                                for value_name in ("InstallLocation", "DisplayIcon"):
                                    value = _reg_value(sub, value_name)
                                    root = illustrator_root_from_path(value)
                                    if root:
                                        roots.add(root)
                        except OSError:
                            continue
            except OSError:
                continue
    return roots


def _reg_value(key, name: str) -> str:
    try:
        value, _kind = winreg.QueryValueEx(key, name)
        return str(value).strip('"')
    except OSError:
        return ""


def illustrator_root_from_path(value: str):
    if not value:
        return None
    raw = value.split(",")[0].strip().strip('"')
    path = Path(raw)
    candidates = []
    if path.is_file():
        candidates.extend(path.parents)
    else:
        candidates.append(path)
        candidates.extend(path.parents)
    for candidate in candidates:
        if (candidate / "Presets").exists() and "illustrator" in candidate.name.lower():
            return candidate
    for candidate in candidates:
        if "illustrator" in candidate.name.lower():
            return candidate
    return None


def common_illustrator_roots():
    roots = set()
    parents = []
    for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(env_name)
        if base:
            parents.append(Path(base) / "Adobe")

    drives_mask = kernel32.GetLogicalDrives()
    for i, letter in enumerate(string.ascii_uppercase):
        if drives_mask & (1 << i):
            root = Path(f"{letter}:\\")
            parents.extend(
                [
                    root / "Adobe",
                    root / "Adode",
                    root / "Program Files" / "Adobe",
                    root / "Program Files (x86)" / "Adobe",
                ]
            )

    for parent in parents:
        if not parent.exists():
            continue
        try:
            for child in parent.iterdir():
                if child.is_dir() and "illustrator" in child.name.lower():
                    roots.add(child)
        except OSError:
            continue
    return roots


def find_script_dirs():
    roots = set()
    roots.update(registry_illustrator_roots())
    roots.update(common_illustrator_roots())
    script_dirs = []
    seen = set()

    for root in sorted(roots, key=lambda p: str(p).lower()):
        presets = root / "Presets"
        if not presets.exists():
            continue
        try:
            locale_dirs = [p for p in presets.iterdir() if p.is_dir()]
        except OSError:
            locale_dirs = []
        if not locale_dirs:
            locale_dirs = [presets / "zh_CN"]
        for locale_dir in locale_dirs:
            preferred_names = ("脚本", "Scripts") if locale_dir.name.lower().startswith("zh") else ("Scripts", "脚本")
            existing = []
            for name in preferred_names:
                candidate = locale_dir / name
                if candidate.exists():
                    existing.append(candidate)
            candidates = existing or [locale_dir / preferred_names[0]]
            for candidate in candidates:
                key = str(candidate).lower()
                if key not in seen:
                    seen.add(key)
                    script_dirs.append(candidate)

    return script_dirs


def install_scripts(target_dir: Path):
    target_dir.mkdir(parents=True, exist_ok=True)
    for name in SCRIPT_FILES:
        src = resource_path(name)
        if not src.exists():
            raise FileNotFoundError(f"Missing bundled script: {name}")
        dst = target_dir / name
        if dst.exists() and src.read_bytes() == dst.read_bytes():
            continue
        shutil.copy2(src, dst)


class HotkeyManager:
    def __init__(self, callback, error_callback):
        self.callback = callback
        self.error_callback = error_callback
        self.thread = None
        self.ready = threading.Event()
        self.stop_event = threading.Event()
        self.thread_id = None
        self.started = False

    def start(self):
        if self.thread and self.thread.is_alive():
            return True
        self.ready.clear()
        self.stop_event.clear()
        self.started = False
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        self.ready.wait(2)
        return self.started

    def stop(self):
        self.stop_event.set()
        if self.thread_id:
            user32.PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0)
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        self.thread = None
        self.thread_id = None
        self.started = False

    def _loop(self):
        self.thread_id = kernel32.GetCurrentThreadId()
        ok_merge = user32.RegisterHotKey(None, HOTKEY_MERGE, 0, VK_F2)
        ok_release = user32.RegisterHotKey(None, HOTKEY_RELEASE, 0, VK_F3)
        if not (ok_merge and ok_release):
            err = ctypes.get_last_error()
            if ok_merge:
                user32.UnregisterHotKey(None, HOTKEY_MERGE)
            if ok_release:
                user32.UnregisterHotKey(None, HOTKEY_RELEASE)
            self.error_callback(f"快捷键注册失败，可能已被其他程序占用。Windows 错误码: {err}")
            self.ready.set()
            return

        self.started = True
        self.ready.set()
        msg = wintypes.MSG()
        try:
            while not self.stop_event.is_set():
                ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if ret == 0 or ret == -1:
                    break
                if msg.message == WM_HOTKEY:
                    self.callback(int(msg.wParam))
        finally:
            user32.UnregisterHotKey(None, HOTKEY_MERGE)
            user32.UnregisterHotKey(None, HOTKEY_RELEASE)


class IllustratorToolbox(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Illustrator 脚本工具箱")
        self.geometry("760x560")
        self.minsize(700, 500)

        self.work_queue = queue.Queue()
        self.script_dirs = []
        self.selected_dir = tk.StringVar()
        self.hotkeys_enabled = tk.BooleanVar(value=False)
        self.is_running = False
        self.hotkeys = HotkeyManager(self._hotkey_event, self._hotkey_error)

        self._build_ui()
        self._scan_script_dirs()
        self.after(100, self._poll_queue)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        header = ttk.Frame(self, padding=(16, 14, 16, 8))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Illustrator 脚本工具箱", font=("Microsoft YaHei UI", 16, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            header,
            text="把文本合并、快速合并、释放剪切蒙版集中到一个界面里。",
            foreground="#4b5563",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        run_frame = ttk.LabelFrame(self, text="菜单脚本", padding=12)
        run_frame.grid(row=1, column=0, sticky="ew", padx=16, pady=8)
        for i in range(5):
            run_frame.columnconfigure(i, weight=1)
        self.btn_merge = ttk.Button(
            run_frame,
            text="安装合并文本",
            command=lambda: self._run_script("MergeText_AI.jsx", "合并文本"),
        )
        self.btn_merge.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.btn_quick = ttk.Button(
            run_frame,
            text="安装快速合并",
            command=lambda: self._run_script("MergeText_AI_Quick.jsx", "快速合并"),
        )
        self.btn_quick.grid(row=0, column=1, sticky="ew", padx=8)
        self.btn_release = ttk.Button(
            run_frame,
            text="安装释放蒙版",
            command=lambda: self._run_script("ReleaseClippingMask.jsx", "释放剪切蒙版"),
        )
        self.btn_release.grid(row=0, column=2, sticky="ew", padx=8)
        self.btn_bridge_test = ttk.Button(run_frame, text="COM 自测", command=self._test_bridge)
        self.btn_bridge_test.grid(row=0, column=3, sticky="ew", padx=8)
        self.btn_runtime_dir = ttk.Button(run_frame, text="打开工作目录", command=self._open_runtime_dir)
        self.btn_runtime_dir.grid(row=0, column=4, sticky="ew", padx=(8, 0))

        hotkey_frame = ttk.LabelFrame(self, text="快捷键", padding=12)
        hotkey_frame.grid(row=2, column=0, sticky="ew", padx=16, pady=8)
        hotkey_frame.columnconfigure(1, weight=1)
        ttk.Checkbutton(
            hotkey_frame,
            text="启用 F2/F3 全局快捷键（仅 Illustrator 在前台时准备菜单脚本）",
            variable=self.hotkeys_enabled,
            command=self._toggle_hotkeys,
        ).grid(row=0, column=0, sticky="w")
        self.hotkey_status = ttk.Label(hotkey_frame, text="未启用", foreground="#6b7280")
        self.hotkey_status.grid(row=0, column=1, sticky="e")

        install_frame = ttk.LabelFrame(self, text="安装到 Illustrator 菜单", padding=12)
        install_frame.grid(row=3, column=0, sticky="nsew", padx=16, pady=8)
        install_frame.columnconfigure(0, weight=1)
        self.dir_combo = ttk.Combobox(install_frame, textvariable=self.selected_dir, state="readonly")
        self.dir_combo.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 8))
        ttk.Button(install_frame, text="重新扫描", command=self._scan_script_dirs).grid(
            row=1, column=0, sticky="ew", padx=(0, 8)
        )
        ttk.Button(install_frame, text="选择目录", command=self._choose_dir).grid(
            row=1, column=1, sticky="ew", padx=8
        )
        ttk.Button(install_frame, text="安装脚本", command=self._install_selected).grid(
            row=1, column=2, sticky="ew", padx=8
        )
        ttk.Button(install_frame, text="打开目录", command=self._open_selected_dir).grid(
            row=1, column=3, sticky="ew", padx=(8, 0)
        )

        log_frame = ttk.LabelFrame(self, text="状态", padding=12)
        log_frame.grid(row=4, column=0, sticky="nsew", padx=16, pady=(8, 16))
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        self.log = tk.Text(log_frame, height=9, wrap="word", state="disabled", font=("Consolas", 10))
        self.log.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(log_frame, command=self.log.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=scrollbar.set)

    def _set_buttons_state(self, state: str):
        for button in (self.btn_merge, self.btn_quick, self.btn_release, self.btn_bridge_test, self.btn_runtime_dir):
            button.configure(state=state)

    def _log(self, text: str):
        stamp = time.strftime("%H:%M:%S")
        self.log.configure(state="normal")
        self.log.insert("end", f"[{stamp}] {text}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _scan_script_dirs(self):
        self.script_dirs = find_script_dirs()
        values = [str(p) for p in self.script_dirs]
        self.dir_combo.configure(values=values)
        if values:
            self.selected_dir.set(values[0])
            self._log(f"找到 Illustrator 脚本目录: {values[0]}")
        else:
            self.selected_dir.set("")
            self._log("没有自动找到 Illustrator 脚本目录，可以点“选择目录”手动指定。")

    def _choose_dir(self):
        chosen = filedialog.askdirectory(title="选择 Illustrator 的 Scripts/脚本 目录")
        if not chosen:
            return
        if chosen not in self.dir_combo["values"]:
            values = list(self.dir_combo["values"]) + [chosen]
            self.dir_combo.configure(values=values)
        self.selected_dir.set(chosen)
        self._log(f"已选择目录: {chosen}")

    def _install_selected(self):
        selected = self.selected_dir.get().strip()
        if not selected:
            messagebox.showwarning("未选择目录", "请先选择 Illustrator 的 Scripts/脚本 目录。")
            return
        target = Path(selected)
        self._run_background(lambda: install_scripts(target), f"安装脚本到 {target}", success_message="安装完成。重启 Illustrator 后，在“文件 > 脚本”里可以看到这些脚本。")

    def _run_script(self, script_name: str, label: str):
        self._run_background(
            lambda: prepare_menu_script(script_name),
            label,
            success_message=f"{label} 菜单脚本已准备好。",
        )

    def _test_bridge(self):
        self._run_background(test_illustrator_bridge, "COM 自测", success_message="COM 自测通过，Illustrator 可以接收脚本。")

    def _run_background(self, func, label: str, success_message: str):
        if self.is_running:
            self._log("已有任务正在运行，请稍等。")
            return
        self.is_running = True
        self._set_buttons_state("disabled")
        self._log(f"开始: {label}")

        def worker():
            try:
                result = func()
                self.work_queue.put(("success", success_message, result))
            except Exception as exc:
                self.work_queue.put(("error", str(exc), None))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_queue(self):
        try:
            while True:
                kind, message, detail = self.work_queue.get_nowait()
                if kind == "success":
                    self._log(message)
                    if detail:
                        self._log(str(detail))
                    self.is_running = False
                    self._set_buttons_state("normal")
                elif kind == "error":
                    self._log(f"错误: {message}")
                    messagebox.showerror("执行失败", message)
                    self.is_running = False
                    self._set_buttons_state("normal")
                elif kind == "hotkey":
                    self._handle_hotkey(detail)
                elif kind == "hotkey_error":
                    self.hotkeys_enabled.set(False)
                    self.hotkey_status.configure(text="启用失败", foreground="#b91c1c")
                    self._log(message)
                    messagebox.showerror("快捷键失败", message)
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    def _toggle_hotkeys(self):
        if self.hotkeys_enabled.get():
            if self.hotkeys.start():
                self.hotkey_status.configure(text="已启用 F2/F3", foreground="#047857")
                self._log("快捷键已启用：F2 准备快速合并脚本，F3 准备释放剪切蒙版脚本。")
            else:
                self.hotkeys_enabled.set(False)
                self.hotkey_status.configure(text="启用失败", foreground="#b91c1c")
        else:
            self.hotkeys.stop()
            self.hotkey_status.configure(text="未启用", foreground="#6b7280")
            self._log("快捷键已关闭。")

    def _hotkey_event(self, hotkey_id: int):
        self.work_queue.put(("hotkey", "", hotkey_id))

    def _hotkey_error(self, message: str):
        self.work_queue.put(("hotkey_error", message, None))

    def _handle_hotkey(self, hotkey_id: int):
        if not foreground_is_illustrator():
            return
        if hotkey_id == HOTKEY_MERGE:
            self._run_script("MergeText_AI_Quick.jsx", "F2 快速合并")
        elif hotkey_id == HOTKEY_RELEASE:
            self._run_script("ReleaseClippingMask.jsx", "F3 释放剪切蒙版")

    def _open_runtime_dir(self):
        try:
            os.startfile(str(ensure_runtime_scripts()))
        except Exception as exc:
            messagebox.showerror("打开失败", str(exc))

    def _open_selected_dir(self):
        selected = self.selected_dir.get().strip()
        if not selected:
            messagebox.showwarning("未选择目录", "请先选择目录。")
            return
        path = Path(selected)
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(str(path))

    def _on_close(self):
        self.hotkeys.stop()
        self.destroy()


def main():
    if "--run-jsx" in sys.argv:
        index = sys.argv.index("--run-jsx")
        script_path = Path(sys.argv[index + 1])
        result_path = Path(sys.argv[index + 2])
        try:
            message = execute_jsx_file_com(script_path)
            result_path.write_text(json.dumps({"ok": True, "message": message}), encoding="utf-8")
            return 0
        except BaseException as exc:
            result_path.write_text(json.dumps({"ok": False, "message": str(exc)}), encoding="utf-8")
            return 1
    if "--self-test" in sys.argv:
        script_dir = ensure_runtime_scripts()
        missing = [name for name in SCRIPT_FILES if not (script_dir / name).exists()]
        if missing:
            print("Missing runtime scripts: " + ", ".join(missing))
            return 2
        print("Runtime scripts: " + str(script_dir))
        print("Illustrator script dirs: " + repr([str(p) for p in find_script_dirs()]))
        return 0
    if "--bridge-test" in sys.argv:
        try:
            print(test_illustrator_bridge())
            return 0
        except Exception as exc:
            print("Illustrator COM bridge test failed: %s" % exc)
            return 1
    app = IllustratorToolbox()
    app.mainloop()


if __name__ == "__main__":
    sys.exit(main())
