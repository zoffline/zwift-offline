# zoffline server IMG for Raspberry Pi

I made a ready to play zoffline server for the Raspberry Pi.

Following Raspberry Pi should be comaptible: 2b v1.2, 3a+, 3b, 3b+(tested) or 4b.<br>
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


## Client install

<details><summary>Windows Instructions</summary>

* Install Zwift
  * If your Zwift version is 1.0.80068, you're all set.
  * If Zwift is not installed, install it before installing zoffline.
  * If your Zwift version is newer than 1.0.80068 and zoffline is running from source: copy ``C:\Program Files (x86)\Zwift\Zwift_ver_cur.xml`` to zoffline's ``cdn/gameassets/Zwift_Updates_Root/`` overwriting the existing file.
  * If your Zwift version is newer than 1.0.80068 and zoffline is not running from source: wait for zoffline to be updated.
* __NOTE:__ instead of performing the steps below you can instead just run the __configure_client__ script from https://github.com/zoffline/zwift-offline/releases/tag/zoffline_helper
* On your Windows machine running Zwift, copy the following files in this repo to a known location:
  * ``ssl/cert-zwift-com.p12``
  * ``ssl/cert-zwift-com.pem``
* Open Command Prompt as an admin, cd to that location and run
  * ``certutil.exe -importpfx Root cert-zwift-com.p12``
    * For Windows 7: run ``certutil.exe -importpfx cert-zwift-com.p12`` instead
  * If you're prompted for a password, just leave it blank. There is no password.
* In the same command prompt run ``type cert-zwift-com.pem >> "C:\Program Files (x86)\Zwift\data\cacert.pem"``
  * Note: Appending cert-zwift-com.pem via Notepad will not work ([#62](https://github.com/zoffline/zwift-offline/issues/62))
* Open Notepad as an admin and open ``C:\Windows\System32\Drivers\etc\hosts``
  * Append this line: ``<zoffline ip> us-or-rly101.zwift.com secure.zwift.com cdn.zwift.com launcher.zwift.com``
    <br />(Where ``<zoffline ip>`` is the ip address of the machine running zoffline. If
    it's running on the same machine as Zwift, use ``127.0.0.1`` as the ip.)
* If you wish to leave the ``hosts`` file unchanged except for when specifically using zoffline, you may optionally use the __launch.bat__ script within the ``scripts`` directory to launch zoffline instead of using the normal Zwift Launcher. See [#121](https://github.com/zoffline/zwift-offline/issues/121) for details.

Why: We need to redirect Zwift to use zoffline and convince Windows and Zwift to
accept zoffline's self signed certificates for Zwift's domain names. Feel free
to generate your own certificates and do the same.

## Disclaimer

Zwift is a trademark of Zwift, Inc., which is not affiliated with the maker of
this project and does not endorse this project.

All product and company names are trademarks of their respective holders. Use of
them does not imply any affiliation with or endorsement by them.