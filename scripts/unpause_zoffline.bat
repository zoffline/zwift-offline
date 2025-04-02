<# :

@ECHO OFF
TITLE unpause_zoffline

NET SESSION >nul 2>&1 || ( PowerShell start -verb runas '"%~0"' & EXIT /B )

powershell /nologo /noprofile "iex (${%~f0} | out-string)"

TASKKILL /F /IM ZwiftLauncher.exe >nul 2>&1

ECHO zoffline is unpaused
ECHO.

PAUSE

#>

$hostsPath = "$env:windir\System32\drivers\etc\hosts"
$hosts = get-content $hostsPath
$hosts = $hosts | Foreach {if ($_ -match '^\s*#\s*(.*?\d{1,3}.*?zwift.*)')
                           {$matches[1]} else {$_}}
$hosts | Out-File $hostsPath -enc ascii
