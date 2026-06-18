param(
    [string]$Key = "F3",
    [string]$IllustratorExe = "E:\Adode\Adobe Illustrator 2021\Support Files\Contents\Windows\Illustrator.exe",
    [string]$ScriptPath = "",
    [switch]$Test
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $IllustratorExe)) {
    throw "Illustrator.exe not found: $IllustratorExe"
}

$localScript = Join-Path $PSScriptRoot "ReleaseClippingMask.jsx"
if ([string]::IsNullOrWhiteSpace($ScriptPath)) {
    $ScriptPath = $localScript
}

if (-not (Test-Path -LiteralPath $ScriptPath)) {
    throw "ReleaseClippingMask.jsx not found: $ScriptPath"
}

Add-Type -AssemblyName System.Windows.Forms
$formsAssembly = [System.Windows.Forms.Application].Assembly.Location

Add-Type -ReferencedAssemblies $formsAssembly -TypeDefinition @"
using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;

public static class AiReleaseClippingMaskHook
{
    private const int WH_KEYBOARD_LL = 13;
    private const int WM_KEYDOWN = 0x0100;
    private const int WM_SYSKEYDOWN = 0x0104;
    private const int GA_ROOT = 2;
    private const int SW_MAXIMIZE = 3;

    private static IntPtr hookId = IntPtr.Zero;
    private static readonly LowLevelKeyboardProc proc = HookCallback;
    private static readonly object maximizeLock = new object();
    private static DateTime lastMaximizeRepair = DateTime.MinValue;

    public static int TargetVkCode = (int)Keys.F3;
    public static string IllustratorExe = "";
    public static string ScriptPath = "";

    public static void Start()
    {
        hookId = SetHook(proc);
        Application.ApplicationExit += delegate { Stop(); };
        Application.Run();
    }

    public static void Stop()
    {
        if (hookId != IntPtr.Zero)
        {
            UnhookWindowsHookEx(hookId);
            hookId = IntPtr.Zero;
        }
    }

    private static IntPtr SetHook(LowLevelKeyboardProc callback)
    {
        using (Process currentProcess = Process.GetCurrentProcess())
        using (ProcessModule currentModule = currentProcess.MainModule)
        {
            return SetWindowsHookEx(WH_KEYBOARD_LL, callback, GetModuleHandle(currentModule.ModuleName), 0);
        }
    }

    private static IntPtr HookCallback(int nCode, IntPtr wParam, IntPtr lParam)
    {
        if (nCode >= 0 && (wParam == (IntPtr)WM_KEYDOWN || wParam == (IntPtr)WM_SYSKEYDOWN))
        {
            int vkCode = Marshal.ReadInt32(lParam);
            IntPtr illustratorWindow = GetIllustratorForegroundWindow();
            if (vkCode == TargetVkCode && illustratorWindow != IntPtr.Zero)
            {
                bool wasMaximized = IsZoomed(illustratorWindow);
                RunIllustratorScript(illustratorWindow, wasMaximized);
                return (IntPtr)1;
            }
        }

        return CallNextHookEx(hookId, nCode, wParam, lParam);
    }

    private static IntPtr GetIllustratorForegroundWindow()
    {
        IntPtr hwnd = GetForegroundWindow();
        if (hwnd == IntPtr.Zero) return IntPtr.Zero;

        hwnd = GetAncestor(hwnd, GA_ROOT);
        if (hwnd == IntPtr.Zero) return IntPtr.Zero;

        int processId;
        GetWindowThreadProcessId(hwnd, out processId);
        if (processId == 0) return IntPtr.Zero;

        try
        {
            Process process = Process.GetProcessById(processId);
            if (string.Equals(process.ProcessName, "Illustrator", StringComparison.OrdinalIgnoreCase))
            {
                return hwnd;
            }
        }
        catch
        {
        }

        return IntPtr.Zero;
    }

    private static void RunIllustratorScript(IntPtr illustratorWindow, bool restoreMaximized)
    {
        if (!File.Exists(IllustratorExe) || !File.Exists(ScriptPath)) return;

        ProcessStartInfo psi = new ProcessStartInfo();
        psi.FileName = IllustratorExe;
        psi.Arguments = "\"" + ScriptPath + "\"";
        psi.UseShellExecute = false;
        psi.CreateNoWindow = true;
        Process.Start(psi);

        if (restoreMaximized)
        {
            RestoreMaximizedWindow(illustratorWindow);
        }
    }

    private static void RestoreMaximizedWindow(IntPtr illustratorWindow)
    {
        Task.Run(delegate {
            int[] delays = new int[] { 50, 120, 250, 500, 1000, 1800, 3000 };
            foreach (int delay in delays)
            {
                Thread.Sleep(delay);
                RepairMaximizedIllustratorWindows(illustratorWindow);
            }
        });
    }

    private static void RepairMaximizedIllustratorWindows(IntPtr originalWindow)
    {
        lock (maximizeLock)
        {
            if ((DateTime.UtcNow - lastMaximizeRepair).TotalMilliseconds < 35) return;
            lastMaximizeRepair = DateTime.UtcNow;
        }

        if (IsWindow(originalWindow) && !IsZoomed(originalWindow))
        {
            ShowWindow(originalWindow, SW_MAXIMIZE);
        }

        EnumWindows(delegate (IntPtr hwnd, IntPtr lParam) {
            if (hwnd == IntPtr.Zero || hwnd == originalWindow || !IsWindowVisible(hwnd)) return true;

            int processId;
            GetWindowThreadProcessId(hwnd, out processId);
            if (processId == 0) return true;

            try
            {
                Process process = Process.GetProcessById(processId);
                if (string.Equals(process.ProcessName, "Illustrator", StringComparison.OrdinalIgnoreCase) && !IsZoomed(hwnd))
                {
                    ShowWindow(hwnd, SW_MAXIMIZE);
                }
            }
            catch
            {
            }

            return true;
        }, IntPtr.Zero);
    }

    private delegate IntPtr LowLevelKeyboardProc(int nCode, IntPtr wParam, IntPtr lParam);
    private delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    [DllImport("user32.dll", CharSet = CharSet.Auto, SetLastError = true)]
    private static extern IntPtr SetWindowsHookEx(int idHook, LowLevelKeyboardProc lpfn, IntPtr hMod, uint dwThreadId);

    [DllImport("user32.dll", CharSet = CharSet.Auto, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool UnhookWindowsHookEx(IntPtr hhk);

    [DllImport("user32.dll", CharSet = CharSet.Auto, SetLastError = true)]
    private static extern IntPtr CallNextHookEx(IntPtr hhk, int nCode, IntPtr wParam, IntPtr lParam);

    [DllImport("kernel32.dll", CharSet = CharSet.Auto, SetLastError = true)]
    private static extern IntPtr GetModuleHandle(string lpModuleName);

    [DllImport("user32.dll")]
    private static extern IntPtr GetForegroundWindow();

    [DllImport("user32.dll")]
    private static extern IntPtr GetAncestor(IntPtr hwnd, uint gaFlags);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool IsZoomed(IntPtr hWnd);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool IsWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool IsWindowVisible(IntPtr hWnd);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);

    [DllImport("user32.dll", SetLastError = true)]
    private static extern uint GetWindowThreadProcessId(IntPtr hWnd, out int lpdwProcessId);
}
"@

$keyValue = [System.Enum]::Parse([System.Windows.Forms.Keys], $Key, $true)
[AiReleaseClippingMaskHook]::TargetVkCode = [int]$keyValue
[AiReleaseClippingMaskHook]::IllustratorExe = (Get-Item -LiteralPath $IllustratorExe).FullName
[AiReleaseClippingMaskHook]::ScriptPath = (Get-Item -LiteralPath $ScriptPath).FullName

if ($Test) {
    Write-Host "Hotkey helper compiled."
    Write-Host "Key: $Key"
    Write-Host "Illustrator: $([AiReleaseClippingMaskHook]::IllustratorExe)"
    Write-Host "Script: $([AiReleaseClippingMaskHook]::ScriptPath)"
    exit 0
}

Write-Host "ReleaseClippingMask hotkey is running."
Write-Host "Key: $Key"
Write-Host "Only works when Adobe Illustrator is the foreground app."
Write-Host "Close this PowerShell window to stop the hotkey."

[AiReleaseClippingMaskHook]::Start()
