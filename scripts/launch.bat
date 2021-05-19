SET hostspath=%windir%\System32\drivers\etc\hosts
SET tmp_host=%windir%\temp\hosts

@ECHO Moving host file to tmp location...

COPY %hostspath% %tmp_host% /y >nul

SET/p ip_address=<%~dp0\ip_address.txt

ECHO .>>%hostspath%
ECHO %ip_address% us-or-rly101.zwift.com secure.zwift.com cdn.zwift.com launcher.zwift.com >> %hostspath%

START /d "C:\Program Files (x86)\Zwift" ZwiftLauncher.exe

PAUSE

@ECHO Moving host file back...

COPY %tmp_host% %hostspath% /y >nul

