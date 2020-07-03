@ECHO OFF
TITLE configure_client
ECHO Configuring Zwift client to use zoffline server
ECHO.

NET SESSION >nul 2>&1 || ( PowerShell start -verb runas '%~0' & EXIT /B )

CD /D "%~dp0"

SET HOSTS="%WINDIR%\system32\drivers\etc\hosts"
>nul 2>&1 FIND /C /I "zwift.com" %HOSTS%
IF %ERRORLEVEL% NEQ 0 (
    ECHO Adding servers to hosts file
    ECHO.>>%HOSTS%
    ECHO 127.0.0.1 us-or-rly101.zwift.com secure.zwift.com cdn.zwift.com launcher.zwift.com>>%HOSTS%
) ELSE ( ECHO Servers found in hosts file, no changes will be made )

ECHO.

FOR /F "tokens=4-5 delims=. " %%I IN ('ver') DO SET VERSION=%%I
certutil.exe -store Root | FIND /C /I "zwift.com" >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    ECHO Importing certificate
    IF %VERSION% == 10 ( ECHO.|certutil.exe -importpfx Root ..\ssl\cert-zwift-com.p12
    ) ELSE ( ECHO.|certutil.exe -importpfx ..\ssl\cert-zwift-com.p12)
) ELSE ( ECHO Certificate found in root store, no changes will be made )

ECHO.

SET ZWIFT=zwift_location.txt
IF EXIST %ZWIFT% ( SET /P FOLDER=<%ZWIFT%
) ELSE ( SET FOLDER="%SystemDrive%\Program Files (x86)\Zwift")
SET CACERT=%FOLDER%\data\cacert.pem
IF EXIST %CACERT% GOTO:FOUND
:NOT_FOUND
SET COMMAND="(new-object -COM 'Shell.Application').BrowseForFolder(0,'Please locate Zwift folder',0,0).self.path"
FOR /F "usebackq delims=" %%I IN (`PowerShell %COMMAND%`) DO SET FOLDER="%%I"
SET CACERT=%FOLDER%\data\cacert.pem
IF NOT EXIST %CACERT% GOTO:NOT_FOUND
ECHO %FOLDER%>%ZWIFT%
:FOUND
>nul 2>&1 FIND /C "MIIEowIBAAKCAQEAuPBKWMw8+OtDjAsZuXUpc89SDWSi5iyS1kfddC6UK6UC5Tsy" %CACERT%
IF %ERRORLEVEL% NEQ 0 (
    ECHO Adding certificate to cacert.pem
    ECHO.>>%CACERT%
    TYPE ..\ssl\cert-zwift-com.pem>>%CACERT%
) ELSE ( ECHO Certificate found in cacert.pem, no changes will be made )

ECHO.

PAUSE
