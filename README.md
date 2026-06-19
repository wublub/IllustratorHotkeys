# Illustrator Scripts and Hotkeys

Windows 下的 Adobe Illustrator 辅助脚本。当前保留的是稳定的分开入口：

- `MergeText_AI.jsx`：合并选中的文本框，带参数对话框
- `MergeText_AI_Quick.jsx`：快速合并入口，适合 `F2` 快捷键
- `ReleaseClippingMask.jsx`：释放选中的剪切蒙版，适合 `F3` 快捷键
- `start_merge_hotkey.bat`：启动 `F2` 快速合并监听
- `start_release_clipping_mask.bat`：启动 `F3` 释放剪切蒙版监听

已经删除旧的合并版 `IllustratorHotkeys.exe` 相关文件，因为合并版里 `F3` 使用体验不好。需要同时用 `F2` 和 `F3` 时，分别启动上面两个 BAT。

## 功能

- 合并多个选中的 Illustrator 文本框。
- 按视觉阅读顺序排序文本框。
- 不同 Y 轴行会分行合并，避免全部挤成一行。
- 支持 90 度旋转文本的常见合并场景。
- 可安装到 Illustrator 的 `文件 > 脚本` 菜单。
- 可用分开的 `F2` / `F3` 热键监听脚本操作。
- 提供 Tkinter 工具箱界面，用于扫描脚本目录、安装脚本和做 COM 自测。

## 文件说明

| 文件 | 用途 |
| --- | --- |
| `MergeText_AI.jsx` | 主文本合并脚本，带参数对话框 |
| `MergeText_AI_Quick.jsx` | 快速合并入口，不弹对话框，适合快捷键 |
| `ReleaseClippingMask.jsx` | 释放选中的剪切蒙版 |
| `install.ps1` | 自动查找 Illustrator 脚本目录并安装 JSX |
| `install_to_illustrator_menu.bat` | 双击运行的安装入口 |
| `start_merge_hotkey.ps1` / `.bat` | `F2` 快速合并热键入口 |
| `start_release_clipping_mask.ps1` / `.bat` | `F3` 释放剪切蒙版热键入口 |
| `hotkey_exe_launcher.py` | 分开打包 F2/F3 热键 EXE 的通用启动器 |
| `start_merge_hotkey.spec` | 打包 F2 热键 EXE 的 PyInstaller 配置 |
| `start_release_clipping_mask.spec` | 打包 F3 热键 EXE 的 PyInstaller 配置 |
| `illustrator_toolbox.py` | 图形化工具箱源码 |
| `IllustratorToolbox.spec` | 打包工具箱 EXE 的 PyInstaller 配置 |

## 使用热键

启动快速合并：

```powershell
.\start_merge_hotkey.bat
```

启动释放剪切蒙版：

```powershell
.\start_release_clipping_mask.bat
```

窗口保持打开即可。切到 Illustrator 后：

- 按 `F2` 快速合并选中的文本框
- 按 `F3` 释放选中的剪切蒙版

热键只在 Adobe Illustrator 是前台窗口时生效。关闭对应窗口即可停止对应热键。

测试热键脚本：

```powershell
powershell.exe -NoProfile -Sta -ExecutionPolicy Bypass -File .\start_merge_hotkey.ps1 -Test
powershell.exe -NoProfile -Sta -ExecutionPolicy Bypass -File .\start_release_clipping_mask.ps1 -Test
```

## 安装到 Illustrator 菜单

最简单方式是双击：

```text
install_to_illustrator_menu.bat
```

或者在 PowerShell 里运行：

```powershell
.\install.ps1
```

安装完成后重启 Illustrator，然后从：

```text
文件 > 脚本
```

运行 `MergeText_AI`、`MergeText_AI_Quick` 或 `ReleaseClippingMask`。

只查看自动识别到的目录，不复制文件：

```powershell
.\install.ps1 -ListOnly
```

如果自动识别失败，可以手动指定 Illustrator 脚本目录：

```powershell
.\install.ps1 -ScriptsDir "C:\Program Files\Adobe\Adobe Illustrator 2021\Presets\zh_CN\脚本"
```

## 从源码运行

需要 Windows、Adobe Illustrator、PowerShell 和 Python。

安装打包/COM 相关依赖：

```powershell
python -m pip install pyinstaller pywin32
```

运行图形化工具箱：

```powershell
python illustrator_toolbox.py
```

工具箱自测：

```powershell
python illustrator_toolbox.py --self-test
python illustrator_toolbox.py --bridge-test
```

## 重新打包

打包 F2 热键程序：

```powershell
pyinstaller start_merge_hotkey.spec
```

打包 F3 热键程序：

```powershell
pyinstaller start_release_clipping_mask.spec
```

打包工具箱程序：

```powershell
pyinstaller IllustratorToolbox.spec
```

构建结果会输出到 `dist\`。源码仓库默认不提交 `dist\` 和 `build\`。

## 常见问题

### Illustrator 菜单里看不到脚本

重新运行 `.\install.ps1 -ListOnly` 检查识别到的目录。确认复制完成后，需要重启 Illustrator。

### F2 / F3 没反应

先确认对应的 BAT 窗口还开着，并且 Illustrator 是当前前台窗口。如果快捷键被其他软件占用，关闭冲突软件后重新启动热键脚本。

### 自动识别不到 Illustrator

用 `-ScriptsDir` 手动指定 Illustrator 的 `Scripts` 或 `脚本` 目录。

### 不想用热键监听

可以只安装 JSX 到 Illustrator 菜单，再用 Illustrator 的动作面板给菜单脚本绑定快捷键。
