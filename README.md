# IllustratorHotkeys

Windows 下的 Adobe Illustrator 辅助脚本工具。它把常用的文本框合并、快速合并和释放剪切蒙版做成 Illustrator 菜单脚本，也提供一个独立热键程序：

- `F2`：快速合并当前选中的文本框
- `F3`：释放当前选中的剪切蒙版
- 热键只在 Adobe Illustrator 是前台窗口时生效
- 触发脚本后会尽量保持 Illustrator 原本的最大化窗口状态

## 功能

- 合并多个选中的 Illustrator 文本框。
- 按视觉阅读顺序排序文本框。
- 不同 Y 轴行会分行合并，避免全部挤成一行。
- 支持 90 度旋转文本的常见合并场景。
- 可安装到 Illustrator 的 `文件 > 脚本` 菜单。
- 可运行独立 EXE，使用 `F2` / `F3` 快捷键操作。
- 提供 Tkinter 工具箱界面，用于扫描脚本目录、安装脚本和做 COM 自测。

## 文件说明

| 文件 | 用途 |
| --- | --- |
| `MergeText_AI.jsx` | 主文本合并脚本，带参数对话框 |
| `MergeText_AI_Quick.jsx` | 快速合并入口，不弹对话框，适合快捷键 |
| `MergeText_AI_Rotated.jsx` | 旋转文本合并入口 |
| `ReleaseClippingMask.jsx` | 释放选中的剪切蒙版 |
| `install.ps1` | 自动查找 Illustrator 脚本目录并安装 JSX |
| `install_to_illustrator_menu.bat` | 双击运行的安装入口 |
| `illustrator_hotkeys_standalone.py` | 独立热键程序源码 |
| `illustrator_toolbox.py` | 图形化工具箱源码 |
| `IllustratorHotkeys.spec` | 打包热键 EXE 的 PyInstaller 配置 |
| `IllustratorToolbox.spec` | 打包工具箱 EXE 的 PyInstaller 配置 |

## 直接使用 EXE

如果已经有构建好的程序：

```powershell
.\dist\IllustratorHotkeys.exe
```

窗口保持打开即可。切到 Illustrator 后：

- 按 `F2` 快速合并选中的文本框
- 按 `F3` 释放选中的剪切蒙版

测试打包文件是否完整：

```powershell
.\dist\IllustratorHotkeys.exe --test
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

运行独立热键源码：

```powershell
python illustrator_hotkeys_standalone.py
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

打包热键程序：

```powershell
pyinstaller IllustratorHotkeys.spec
```

打包工具箱程序：

```powershell
pyinstaller IllustratorToolbox.spec
```

构建结果会输出到 `dist\`。源码仓库默认不提交 `dist\` 和 `build\`，EXE 更适合放到 GitHub Release。

## 上传到 GitHub

当前仓库远程地址是：

```text
https://github.com/wublub/IllustratorHotkeys.git
```

第一次整理上传时，建议只提交源码和说明文件：

```powershell
git status
git add README.md .gitignore *.jsx *.py *.ps1 *.bat *.spec
git status
git commit -m "Add Illustrator hotkey scripts and documentation"
git push origin main
```

如果以后修改了文件，继续上传就是：

```powershell
git status
git add README.md *.jsx *.py *.ps1 *.bat *.spec
git commit -m "Update Illustrator hotkeys"
git push origin main
```

如果要把 EXE 发给别人用，推荐发布 Release，而不是把 `dist\IllustratorHotkeys.exe` 直接提交进仓库：

```powershell
gh release create v1.0.0 .\dist\IllustratorHotkeys.exe --title "IllustratorHotkeys v1.0.0" --notes "F2 快速合并文本框，F3 释放剪切蒙版。"
```

如果没有安装 GitHub CLI，也可以在 GitHub 网页打开仓库，进入 `Releases`，手动创建版本并上传 `dist\IllustratorHotkeys.exe`。

## 常见问题

### Illustrator 菜单里看不到脚本

重新运行 `.\install.ps1 -ListOnly` 检查识别到的目录。确认复制完成后，需要重启 Illustrator。

### F2 / F3 没反应

先确认 `IllustratorHotkeys.exe` 窗口还开着，并且 Illustrator 是当前前台窗口。如果快捷键被其他软件占用，关闭冲突软件后重新启动热键程序。

### 自动识别不到 Illustrator

用 `-ScriptsDir` 手动指定 Illustrator 的 `Scripts` 或 `脚本` 目录。

### 不想用 EXE

可以只安装 JSX 到 Illustrator 菜单，再用 Illustrator 的动作面板给菜单脚本绑定快捷键。
