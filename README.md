# zoffline server for Raspberry Pi

This is a ready to play autostart zoffline server for the Raspberry Pi.

Following Raspberry Pi should be comaptible: 2b v1.2, 3a+, 3b, 3b+(tested) and 4b.<br>
Passthrough internet on the Pi hotspot is enabled if you connect the Pi over a ethernet cable.

You can play on any Zwift client (Windows, iOS, Android, macOS) over the zoffline wifi hotspot from the Pi.<br> 
``The iOS Zwift client needs a temporary jailbroken device.``

This is a fork of https://github.com/zoffline/zwift-offline

## Server install

<details><summary>Instructions</summary>

* Download the zoffline server IMG file:<br> 
  * https://drive.google.com/u/0/uc?id=1WNHDLaHiUb-6NyaCZs1b8IM0pfKUMgDO&export=download

* Extract the ZIP file to a known location.<br>
* Write the IMG file with a program to a SD-Card which is at least 4GB in size. 
* Windows users can use Win32 Disk Imager:<br>
  * https://sourceforge.net/projects/win32diskimager/
* The OS will auto resize at boot and use all remaining space of the SD-Card.

</details>

## Client install

<details><summary>Windows instructions</summary>

* Install Zwift https://www.zwift.com/eu-de/download
* On your Windows machine running Zwift, connect to the zoffline hotspot; ``password zoffline``
  * Open a browser and go to http://192.168.50.10/certs
  * Download the files ``cacert.pem`` and ``import-into-win-macos.p12``
* Open Command Prompt as an admin, cd to that location and run
  * ``certutil.exe -importpfx Root import-into-win-macos.p12``
  * If you're prompted for a password, just leave it blank. There is no password.
* Copy the file ``cacert.pem`` to the folder ``C:\Program Files (x86)\Zwift\data`` and overwrite the old file
* You are done, have fun.

</details>

<details><summary>iOS instructions</summary>

* You need a temporary jailbroken iOS device. 
  * After the replacement of the``cacert.pem`` in the Zwift folder we do not need the jailbreak anymore.
  * At the end of the procedure you can reboot your iOS device and the jailbreak is not active anymore.
  * Zwift will still work with zoffline and should be updateable without going through the procedure again (untested).<br>
* Check if your device is compatible with the checkra1n jailbreak, other jailbreaks may work but are not tested. 
  * https://taig9.com/apps/checkra1n-downloader/
* If yes follow this tutorial, other tutorials may work but are not tested.
  * https://www.techacrobat.com/checkra1n-jailbreak-for-windows/
* If you did everything right you should now have a new App called Checkra1n on your iOS device.
  * Install Cydia App through the Checkra1n App on the iPad.
  * Install Filza file browser App through Cydia App.<br>
* Install the Zwift App through the official App store if you did not already.<br>
* Connect to the zoffline hotspot; ``password zoffline``.<br>
* Now we do the certificate file installation for iOS and Zwift.
  * Open in Safari http://192.168.50.10/certs
    * Short touch press on ``import-into-ios.pem``. 
    * Follow this tutorial now:
	* https://support.securly.com/hc/en-us/articles/206978437-How-do-I-deploy-Securly-SSL-certificate-to-iOS-
  * Go back to Safari and open again http://192.168.50.10/certs
    * Long touch press on ``cacert.pem`` touch press on ``download linked file``.<br>
  * Open Filza file browser App. 
    * Go to the path ``/private/var/mobile/Library/Mobile Documents/com~apple~CloudDocs/Downloads``.
	* Long press on ``cacert.pem`` choose move.
	* Go to the path ``/var/containers/Bundle/Application/Zwift/Zwift.app/dataES``.
    * Press the pinboard icon on the bottom left hand side and then the left icon arrow ``paste``.
    * If you did it right you will be asked if you want to replace the file ``cacert.pem`` press ``replace``.<br>
* Check if you you are still connected to the zoffline AP, if not connect to it.<br>
* Launch the Zwift App.
  * Press on add existing user and not on create new user.
  * Login with random credentials with any mail or username and password (check next two steps before you do it).
    * You can use the Zwift App on the same iOS device with zoffline server and offical server.
    * If you wan't that, then do not use your Zwift online E-Mail username to create your zoffline user.
  * Official online use: Connect to your usual internet AP and open Zwift (close Zwift if it is open in background).
  * zoffline use: Connect to the zoffline AP and open Zwift (close Zwift if it is open in background).
    * If you are using a zoffline and a offical online profile you have two profiles in the Zwift App.
* If you wan't to deactivate the jailbreak, reboot your device.
* You are done, have fun.

</details>

<details><summary>macOS instructions</summary>

* TBA

</details>

<details><summary>Android instructions</summary>

* TBA

</details>

### [OPTIONAL]: Upload activities, activate Multiplayer profiles, etc.

<details><summary>Expand</summary>

* Connect with a SSH program like Putty or WinSCP to the Pi ``(User: pi Password: raspberry)``.
  * Uploading activities.
    * The Pi needs to be connected to a ethernet cable with internet access.
    * Modify the necessary files (garmin, strava).
  * Enable Multiplayer profiles.
    * Modify the necessary files.

* Which files you need to modify you can look here:<br>
  * https://github.com/zoffline/zwift-offline/blob/master/README.md	

</details>

### [OPTIONAL]: Documentation of how to create iOS >13 compatible certificate.

<details><summary>Expand</summary>

* TBA

</details>

## Disclaimer

Zwift is a trademark of Zwift, Inc., which is not affiliated with the maker of
this project and does not endorse this project.

All product and company names are trademarks of their respective holders. Use of
them does not imply any affiliation with or endorsement by them.