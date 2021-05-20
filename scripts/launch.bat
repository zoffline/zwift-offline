@ECHO OFF

NET SESSION >nul 2>&1 || ( PowerShell start -verb runas '%~0' & EXIT /B )

CD /D "%~dp0"

SET hostspath=%windir%\System32\drivers\etc\hosts
SET tmp_host=%windir%\temp\hosts

ECHO Moving host file to tmp location...

COPY %hostspath% %tmp_host% /y >nul

SET/p ip_address=<%~dp0\ip_address.txt

ECHO.>>%hostspath%
ECHO %ip_address% us-or-rly101.zwift.com secure.zwift.com cdn.zwift.com launcher.zwift.com experimentation.prd-gs.zwift.com >> %hostspath%

SET ZWIFT=zwift_location.txt
IF EXIST %ZWIFT% ( SET /P FOLDER=<%ZWIFT%
) ELSE ( SET FOLDER="%SystemDrive%\Program Files (x86)\Zwift")
SET LAUNCHER=%FOLDER%\ZwiftLauncher.exe
IF EXIST %LAUNCHER% GOTO:FOUND
:NOT_FOUND
SET COMMAND="(new-object -COM 'Shell.Application').BrowseForFolder(0,'Please locate Zwift folder',0,0).self.path"
FOR /F "usebackq delims=" %%I IN (`PowerShell %COMMAND%`) DO SET FOLDER="%%I"
SET LAUNCHER=%FOLDER%\ZwiftLauncher.exe
IF NOT EXIST %LAUNCHER% GOTO:NOT_FOUND
ECHO %FOLDER%>%ZWIFT%
:FOUND
START /d %FOLDER% ZwiftLauncher.exe

PAUSE

ECHO Moving host file back...

COPY %tmp_host% %hostspath% /y >nul
