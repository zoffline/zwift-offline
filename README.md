# zoffline server IMG for Raspberry Pi

I made a ready to play zoffline server for the Raspberry Pi.

Following Raspberry Pi should be comaptible: 2b v1.2, 3a+, 3b, 3b+(tested) and 4b.<br>
Passthrough internet on the Pi hotspot is enabled if you connect the Pi over a ethernet cable.

You can play on any Zwift client (Windows, iOS, Android, macOS) over the zoffline wifi hotspot from the Pi.<br> 
iOS needs a temorary jailbreak.

This is a fork of https://github.com/zoffline/zwift-offline

## Server install

<details><summary>Instructions</summary>

Download the zoffline server IMG for Raspberry Pi:<br> 
https://drive.google.com/u/0/uc?id=1WNHDLaHiUb-6NyaCZs1b8IM0pfKUMgDO&export=download

Extract the IMG file to a known location.<br>
Write the image with a program to a SD-Card which is at least 4GB in size<br> (the OS will auto resize at boot and use all remaining space of the SD-Card).

Windows users can use Win32 Disk Imager:<br>
https://sourceforge.net/projects/win32diskimager/

</details>

## Client install

<details><summary>Windows Instructions</summary>

* Install Zwift https://www.zwift.com/eu-de/download
* On your Windows machine running Zwift, connect to the zoffline hotspot; ``password zoffline``
  * Open a browser and go to http://192.168.50.10/certs
  * Download the files ``cacert.pem`` and ``import-into-win-macos.p12``
* Open Command Prompt as an admin, cd to that location and run
  * ``certutil.exe -importpfx Root import-into-win-macos.p12``
  * If you're prompted for a password, just leave it blank. There is no password.
* Copy the file ``cacert.pem`` to the folder ``C:\Program Files (x86)\Zwift\data`` and overwrite the old file

</details>

## Disclaimer

Zwift is a trademark of Zwift, Inc., which is not affiliated with the maker of
this project and does not endorse this project.

All product and company names are trademarks of their respective holders. Use of
them does not imply any affiliation with or endorsement by them.