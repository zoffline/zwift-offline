<# :

@ECHO OFF
TITLE pause_zoffline

NET SESSION >nul 2>&1 || ( PowerShell start -verb runas '"%~0"' & EXIT /B )

powershell /nologo /noprofile "iex (${%~f0} | out-string)"

TASKKILL /F /IM ZwiftLauncher.exe >nul 2>&1

ECHO zoffline is paused
ECHO.

PAUSE

#>

$hostsPath = "$env:windir\System32\drivers\etc\hosts"
$hosts = get-content $hostsPath
$hosts | Foreach {if ($_ -match '^\s*([^#].*?\d{1,3}.*?zwift.*)')
                  {"# " + $matches[1]} else {$_}} |
         Out-File $hostsPath -enc ascii
