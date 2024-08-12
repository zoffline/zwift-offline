@ECHO OFF
TITLE disable_zoffline

NET SESSION >nul 2>&1 || ( PowerShell start -verb runas '%~0' & EXIT /B )

SET HOSTS="%WINDIR%\system32\drivers\etc\hosts"
COPY %HOSTS% %HOSTS%.bak >nul
ECHO Removing servers from hosts file
TYPE %HOSTS%.bak | FINDSTR /V /I zwift > %HOSTS%

ECHO.

TASKKILL /F /IM ZwiftLauncher.exe >nul 2>&1

PAUSE
