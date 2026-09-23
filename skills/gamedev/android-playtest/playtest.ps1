<#
playtest.ps1 — 一键开一场「有界面·玩家辅助」Android playtest 会话

和 headless 自动化(android-driver 子agent)互补:这个是**有窗口**的,弹出真模拟器窗口,
你用鼠标/键盘**亲手玩**;agent(主会话)在旁辅助:按需截图、盯 logcat、帮你刷重复操作、记报告。

做的事:windowed 起模拟器(-gpu host 有画面) -> 等 boot -> 装/更新 APK -> 启动游戏
        -> 后台把 logcat 持续写到文件(脚本同目录),供 agent tail。

参数都不写死,优先级:命令行参数 > 环境变量 > 默认值
  -Apk     $env:PLAYTEST_APK       无默认;不给就不装
  -Package $env:PLAYTEST_PACKAGE   无默认;不给就从 APK 里读(aapt2 dump packagename),都没有就报错
  -Avd     $env:PLAYTEST_AVD       默认 playtest_avd
  -Port    $env:PLAYTEST_PORT      默认 5556(避开 headless 常用的 5554);设备序列号 = emulator-<Port>
SDK 走 $env:ANDROID_SDK_ROOT;logcat 文件写在脚本同目录($PSScriptRoot)。

用法(脚本在 skill 目录内,cd 到脚本目录或写全路径跑):
  powershell -File "<skill目录>\playtest.ps1" -Apk <路径>                 # 干净冷启 + 装 APK + 启动
  powershell -File "<skill目录>\playtest.ps1" -Package <包名> -NoInstall  # 已装在设备上,只启动
  powershell -File "<skill目录>\playtest.ps1" -KeepState                  # 保留上次快照(续上次进度)
#>
param(
    [string]$Apk     = $env:PLAYTEST_APK,
    [string]$Package = $env:PLAYTEST_PACKAGE,
    [string]$Avd     = $(if ($env:PLAYTEST_AVD)  { $env:PLAYTEST_AVD }       else { "playtest_avd" }),
    [int]   $Port    = $(if ($env:PLAYTEST_PORT) { [int]$env:PLAYTEST_PORT } else { 5556 }),
    [switch]$KeepState,   # 默认干净冷启(-no-snapshot);带上则保留快照
    [switch]$NoInstall    # 跳过装 APK
)
$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

$SDK = if ($env:ANDROID_SDK_ROOT) { $env:ANDROID_SDK_ROOT } else { "$env:LOCALAPPDATA\Android\Sdk" }
$EMU = Join-Path $SDK "emulator\emulator.exe"
$ADB = Join-Path $SDK "platform-tools\adb.exe"
$SER = "emulator-$Port"
$Log = Join-Path $PSScriptRoot "playtest-logcat.txt"   # 脚本同目录,相对定位

if (-not (Test-Path $EMU)) { throw "找不到 emulator:$EMU (检查 `$env:ANDROID_SDK_ROOT)" }

# 包名没给就从 APK 读;在起模拟器之前做,缺信息早失败
if (-not $Package -and $Apk -and (Test-Path $Apk)) {
    $aapt2 = Get-ChildItem (Join-Path $SDK "build-tools") -Directory -ErrorAction SilentlyContinue |
             Sort-Object { [version]($_.Name -replace '-.*$','') } | Select-Object -Last 1 |
             ForEach-Object { Join-Path $_.FullName "aapt2.exe" }
    if ($aapt2 -and (Test-Path $aapt2)) { $Package = (& $aapt2 dump packagename $Apk).Trim() }
}
if (-not $Package) { throw "不知道要启动哪个包:传 -Package 或 -Apk(需要 SDK build-tools 里的 aapt2),或设 `$env:PLAYTEST_PACKAGE" }

# 1. 起「有界面」模拟器(注意:没有 -no-window,所以会弹窗)
$running = ((& $ADB devices) | Select-String -SimpleMatch $SER) -ne $null
if (-not $running) {
    $emuArgs = @("-avd",$Avd,"-gpu","host","-port",$Port,"-no-audio","-no-metrics")
    if (-not $KeepState) { $emuArgs += "-no-snapshot" }
    Write-Host "[1/4] 弹出有界面模拟器 $SER (-gpu host)..."
    Start-Process -FilePath $EMU -ArgumentList $emuArgs   # 分离启动,窗口独立存活
} else {
    Write-Host "[1/4] $SER 已在运行,复用其窗口"
}

# 2. 等 boot
Write-Host "[2/4] 等待 boot_completed ..."
& $ADB -s $SER wait-for-device
do { Start-Sleep -Seconds 3; $bc = (& $ADB -s $SER shell getprop sys.boot_completed 2>$null) -replace "\s","" } until ($bc -eq "1")
Write-Host "      已 boot"

# 3. 装 APK + 启动
if (-not $NoInstall) {
    if ($Apk -and (Test-Path $Apk)) { Write-Host "[3/4] 安装 $Apk"; & $ADB -s $SER install -r $Apk | Select-Object -Last 1 }
    else { Write-Host "[3/4] 跳过安装(没给 -Apk 或找不到:$Apk)" }
} else { Write-Host "[3/4] -NoInstall,跳过安装" }
& $ADB -s $SER shell monkey -p $Package -c android.intent.category.LAUNCHER 1 | Out-Null

# 4. 后台持续记 logcat 到文件(供 agent tail;旧的先清)
& $ADB -s $SER logcat -c
if (Test-Path $Log) { Remove-Item $Log -Force -ErrorAction SilentlyContinue }
Start-Process -FilePath $ADB -ArgumentList "-s",$SER,"logcat","-v","time" -RedirectStandardOutput $Log -WindowStyle Hidden
Write-Host "[4/4] logcat 持续写入 -> $Log"

Write-Host ""
Write-Host "== playtest 就绪:模拟器窗口里可直接玩 =="
Write-Host "  设备   : $SER   包: $Package"
Write-Host "  日志   : $Log  (agent 可 tail 盯错)"
Write-Host "  SDK    : $SDK"
Write-Host "  让 agent 辅助示例:「看一下现在」「盯日志有报错叫我」「自动刷刮卡200次」「记一下这轮」"
Write-Host "  收工   : `"$ADB`" -s $SER emu kill"
