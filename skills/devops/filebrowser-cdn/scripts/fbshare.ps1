# Manage public shares on an existing File Browser service.
# Configuration comes from parameters or FILEBROWSER_* environment variables.
[CmdletBinding(DefaultParameterSetName = 'Create')]
param(
  [Parameter(ParameterSetName = 'Create', Mandatory = $true)]
  [string]$Project,

  [Parameter(ParameterSetName = 'Create')]
  [string]$Sub = '',

  [Parameter(ParameterSetName = 'List', Mandatory = $true)]
  [switch]$List,

  [Parameter(ParameterSetName = 'Remove', Mandatory = $true)]
  [Alias('Rm')]
  [string]$Remove,

  [string]$Server = $env:FILEBROWSER_URL,
  [string]$User = $env:FILEBROWSER_USER,
  [string]$Password = $env:FILEBROWSER_PASSWORD
)

$ErrorActionPreference = 'Stop'

if (-not $Server) { throw 'Missing FILEBROWSER_URL or -Server.' }
if (-not $User) { throw 'Missing FILEBROWSER_USER or -User.' }
if (-not $Password) { throw 'Missing FILEBROWSER_PASSWORD or -Password.' }

$Server = $Server.TrimEnd('/')
if ($Server -notmatch '^https?://') { throw "Invalid File Browser URL: $Server" }

$loginBody = @{
  username = $User
  password = $Password
  recaptcha = ''
} | ConvertTo-Json

try {
  $token = Invoke-RestMethod -Method Post -Uri "$Server/api/login" -Body $loginBody -ContentType 'application/json'
} catch {
  throw "File Browser login failed at $Server. $($_.Exception.Message)"
}

$auth = @{ 'X-Auth' = [string]$token }

function Get-Shares {
  Invoke-RestMethod -Uri "$Server/api/shares" -Headers $auth
}

function Get-PublicBaseUrl([string]$Hash) {
  "$Server/api/public/dl/$Hash/"
}

if ($List) {
  $shares = Get-Shares
  if (-not $shares) {
    Write-Output 'No public shares found.'
    return
  }

  foreach ($share in $shares) {
    Write-Output ('{0,-16} {1,-48} {2}' -f $share.hash, $share.path, (Get-PublicBaseUrl $share.hash))
  }
  return
}

if ($Remove) {
  Invoke-RestMethod -Method Delete -Uri "$Server/api/share/$Remove" -Headers $auth | Out-Null
  Write-Output "Removed share: $Remove"
  return
}

if ($Project -notmatch '^[a-z0-9][a-z0-9._-]*$') {
  throw "Invalid project slug: $Project"
}

$normalizedSub = $Sub.Replace('\', '/').Trim('/')
if ($normalizedSub -and $normalizedSub -notmatch '^[a-z0-9][a-z0-9._-]*(/[a-z0-9][a-z0-9._-]*)*$') {
  throw "Invalid relative subpath: $Sub"
}

$virtualPath = "/$Project"
if ($normalizedSub) { $virtualPath += "/$normalizedSub" }

$segments = $virtualPath.Trim('/').Split('/')
for ($index = 1; $index -le $segments.Count; $index++) {
  $directory = $segments[0..($index - 1)] -join '/'
  Invoke-RestMethod -Method Post -Uri "$Server/api/resources/$directory/" -Headers $auth | Out-Null
}

$shares = Get-Shares
$hash = $null
foreach ($share in $shares) {
  if ($share.path -eq $virtualPath) {
    $hash = $share.hash
    break
  }
}

if ($hash) {
  Write-Output "Reused share: $virtualPath"
} else {
  $created = Invoke-RestMethod -Method Post -Uri "$Server/api/share$virtualPath" -Headers $auth -Body '{}' -ContentType 'application/json'
  $hash = $created.hash
  Write-Output "Created share: $virtualPath"
}

Write-Output ''
Write-Output "Path:       $virtualPath"
Write-Output "Hash:       $hash"
Write-Output "Download:   $(Get-PublicBaseUrl $hash)"
Write-Output "Browse:     $Server/share/$hash"
Write-Output ''
Write-Output 'Record this mapping in FILEBROWSER_REGISTRY when configured.'
