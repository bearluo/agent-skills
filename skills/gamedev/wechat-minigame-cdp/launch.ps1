# 用 CDP 调试端口重启微信开发者工具。
# 核心思路:argv 照抄当前正在跑的那个实例,只追加 --remote-debugging-port,
# 免得漏参数(漏 --custom-devtools-frontend 会让内置调试器面板看不到日志)。
param(
  [int]$Port = 9222,
  [switch]$Off       # 关掉调试端口,恢复原样启动
)
$ErrorActionPreference = 'Stop'

function Get-MainProc {
  Get-CimInstance Win32_Process -Filter "Name='wechatdevtools.exe'" |
    Where-Object { $_.CommandLine -notmatch '--type=' } | Select-Object -First 1
}

# ---- 1. 组装 exe + 参数串 ----
$main = Get-MainProc
if ($main) {
  $cl = $main.CommandLine
  if ($cl -match '^\s*"([^"]+)"\s*(.*)$') { $exe = $Matches[1]; $argStr = $Matches[2] }
  elseif ($cl -match '^\s*(\S+)\s+(.*)$')  { $exe = $Matches[1]; $argStr = $Matches[2] }
  else { throw "解析不了命令行: $cl" }
  Write-Host "[launch] 抄当前实例的 argv (PID $($main.ProcessId))"

  if (-not $Off -and $argStr -match "--remote-debugging-port=$Port(\s|$)") {
    Write-Host "[launch] 端口 $Port 已经开着,不用重启"
    return
  }
} else {
  # 没在跑 -> 自己拼。装目录:环境变量优先,否则试常见位置
  $cands = @($env:WECHAT_DEVTOOLS,
             'D:\Program Files (x86)\Tencent\微信web开发者工具',
             "${env:ProgramFiles(x86)}\Tencent\微信web开发者工具",
             "$env:ProgramFiles\Tencent\微信web开发者工具") | Where-Object { $_ }
  $d = $cands | Where-Object { Test-Path (Join-Path $_ 'wechatdevtools.exe') } | Select-Object -First 1
  if (-not $d) { throw "找不到微信开发者工具装目录,设 `$env:WECHAT_DEVTOOLS 指过去" }

  # profile:%LOCALAPPDATA%\微信开发者工具\User Data\<32位hash>,取最近改动的那个
  $udRoot = Join-Path $env:LOCALAPPDATA '微信开发者工具\User Data'
  $ud = Get-ChildItem $udRoot -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^[0-9a-f]{32}$' } |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if (-not $ud) { throw "找不到已登录 profile: $udRoot" }
  $ud = $ud.FullName

  # --custom-devtools-frontend 是 file:// URL,中文段要 percent-encode
  $fe = 'file://' + (($ud -replace '\\', '/') -replace '微信开发者工具', [Uri]::EscapeDataString('微信开发者工具')) + '/WeappPlugin/inspector'

  $exe = Join-Path $d 'wechatdevtools.exe'
  $argStr = '"{0}\code\package.nw" "-load-extension={1}\WeappPlugin" "--custom-devtools-frontend={2}" "--user-data-dir={1}" "--package-dir={0}\code\package.nw"' -f $d, $ud, $fe
  Write-Host "[launch] 未在运行,按检测结果重建 argv"
  Write-Host "[launch]   装目录 = $d"
  Write-Host "[launch]   profile = $ud"
}

# ---- 2. 换端口参数 ----
$argStr = ($argStr -replace '\s*--remote-debugging-port=\d+', '') -replace '\s*--app-session-id=\S+', ''
if (-not $Off) { $argStr = "$argStr --remote-debugging-port=$Port" }

# ---- 3. 关掉旧实例 ----
if ($main) {
  $cli = Join-Path (Split-Path $exe) 'cli.bat'
  if (Test-Path $cli) { & $cli quit 2>$null | Out-Null }
  Start-Sleep -Seconds 3
  Get-CimInstance Win32_Process -Filter "Name='wechatdevtools.exe'" -ErrorAction SilentlyContinue |
    ForEach-Object { taskkill /PID $_.ProcessId /T /F 2>&1 | Out-Null }
  Start-Sleep -Seconds 2
}

# ---- 4. 起 ----
# ⚠️ PS5.1 的 -ArgumentList 传【数组】不会自动加引号,含空格路径会被切断,必须传拼好的【单字符串】
Write-Host "[launch] 启动中..."
Start-Process -FilePath $exe -ArgumentList $argStr
if ($Off) { Write-Host "[launch] 已按原样启动(无调试端口)"; return }

# ---- 5. 等端口 ----
for ($i = 0; $i -lt 40; $i++) {
  Start-Sleep -Seconds 2
  if (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) {
    Write-Host "[launch] CDP 端口 $Port 已监听"
    Write-Host "[launch] 下一步: node `"$PSScriptRoot\cdp.js`" --targets"
    return
  }
}
Write-Host "[launch] 超时:端口 $Port 没起来,检查参数串是否被空格切断"
