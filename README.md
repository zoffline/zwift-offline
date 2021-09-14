# zoffline server IMG for Raspberry Pi

I made a ready to play zoffline server for the Raspberry Pi.

Following Raspberry Pi should be comaptible: 2b v1.2, 3a+, 3b, 3b+(tested) or 4b.<br>
Passthrough internet on the Pi hotspot is enabled if you connect the Pi over a ethernet cable.

You can play on any Zwift client (Windows, iOS, Android, macOS) over the zoffline wifi hotspot from the Pi.<br> 
iOS needs a temorary jailbreak.

This is a fork of https://github.com/zoffline/zwift-offline

## Server install

Download the zoffline server IMG for Raspberry Pi: 
https://drive.google.com/u/0/uc?id=1WNHDLaHiUb-6NyaCZs1b8IM0pfKUMgDO&export=download

Extract the IMG file to a known location.
Write the image with a program to a SD-Card which is at least 4GB in size (the OS will auto resize at boot and use all remaining space of the SD-Card).

Windows users can use Win32 Disk Imager:
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

</details>

<details><summary>Mac OS X Instructions</summary>

* Install Zwift
  * If your Zwift version is 1.0.80068, you're all set.
  * If Zwift is not installed, install it before installing zoffline.
  * If your Zwift version is newer than 1.0.80068: copy ``~/Library/Application Support/Zwift/ZwiftMac_ver_cur.xml`` to zoffline's ``cdn/gameassets/Zwift_Updates_Root/`` overwriting the existing file.
* On your Mac machine running Zwift, copy the following files in this repo to a known location:
  * ``ssl/cert-zwift-com.p12``
  * ``ssl/cert-zwift-com.pem``
* Open Keychain Access, select "System" under "Keychains", select "Certificates" under "Category"
    * Click "File - Import Items..." and import ``ssl/cert-zwift-com.p12``
    * Right click "\*.zwift.com", select "Get Info" and under "Trust" choose "When using this certificate: Always Trust".
    * If you're prompted for a password, just leave it blank. There is no password.
* In a terminal within the directory ``ssl/cert-zwift-com.pem`` was copied to, run ``cat cert-zwift-com.pem >> ~/Library/Application\ Support/Zwift/data/cacert.pem``
  * Note: Appending the contents of ``ssl/cert-zwift-com.pem`` with a text editor doesn't work ([#62](https://github.com/zoffline/zwift-offline/issues/62))
* Using a text editor (with admin privileges) open ``/Applications/Zwift.app/Contents/Info.plist``
  * Append these keys:
    ```
    <key>NSAppTransportSecurity</key>
   	<dict>
        <key>NSExceptionDomains</key>
        <dict>
            <key>zwift.com</key>
            <dict>
                <key>NSExceptionAllowsInsecureHTTPLoads</key>
                <true/>
                <key>NSIncludesSubdomains</key>
                <true/>
            </dict>
        </dict>
   	</dict>
    ```
* For Big Sur run ``sudo codesign --force --deep --sign - /Applications/Zwift.app`` in terminal. See https://github.com/zoffline/zwift-offline/issues/132 for extra details.
* Using a text editor (with admin privileges) open ``/etc/hosts``
  * Append this line: ``<zoffline ip> us-or-rly101.zwift.com secure.zwift.com cdn.zwift.com launcher.zwift.com``
    <br />(Where ``<zoffline ip>`` is the ip address of the machine running zoffline. If
    it's running on the same machine as Zwift, use ``127.0.0.1`` as the ip.)

Why: We need to redirect Zwift to use zoffline and convince OS X and Zwift to
accept zoffline's self signed certificates for Zwift's domain names. Feel free
to generate your own certificates and do the same.

</details>

<details><summary>Android (non-rooted device)</summary>

* Install required apps:
  * Download and install ``zoffline-obb.apk`` from [here](https://github.com/Argon2000/ZofflineObbAndroid/blob/master/app/release/zoffline-obb.apk)
  * Download "Host Changer VPN - The Game Changer" from Google Play ([link](https://play.google.com/store/apps/details?id=com.hostchanger.gamingvpn.gamechanger))
  * Create a `hosts.txt` file to use with the app (you could use a text editor app or create it online with an online tool such as [this](https://passwordsgenerator.net/text-editor/)). The file must look like this (replace ``<zoffline ip>`` with the IP address of the machine running zoffline):
  ```
  <zoffline ip> us-or-rly101.zwift.com
  <zoffline ip> secure.zwift.com
  <zoffline ip> cdn.zwift.com
  ```
  * Run `Host Changer`, select created `hosts.txt` file and press the button
  * Note: If you know what you're doing and have a capable enough router you can adjust your router to alter these DNS records instead of using the "Host Changer VPN" app.
* Patch after every installation or update:
  * Install/update Zwift from Google play, but do not start it yet.
    * If you have already started it go to `Android Settings > Applications > Zwift` and clear data or uninstall and reinstall the app.
  * Open the `ZofflineObb` app and run it (allow access to storage)
  * Wait for process to finish (5-10min)
  * Run Zwift, hopefully it verifies download and runs
* Play Zwift:
  * Host Changer button must be ON
  * Start Zwift and sign in using any email/password
    * If multiplayer is enabled, access `https://<zoffline ip>/signup/` to sign up and import your files. (You must accept an invalid certificate alert).

Why: We need to redirect Zwift to use zoffline (this is done by the VPN app) and convince Zwift to
accept zoffline's self signed certificates for Zwift's domain names (this is done by the patch tool ZofflineObb).

</details>

<details><summary>Android (rooted device)</summary>

* Install Zwift on the device
* Open Zwift once to complete installation (i.e download all extra files).
* Append the contents of ``ssl/cert-zwift-com.pem`` to ``/data/data/com.zwift.zwiftgame/dataES/cacerts.pem`` on the device
  * Note: this file will only exist after the first run of Zwift since it's downloaded after the initial install
  * Recommended approach for appending the contents (due to [#62](https://github.com/zoffline/zwift-offline/issues/62)):
    * ``adb push ssl/cert-zwift-com.pem /data/data/com.zwift.zwiftgame/dataES/``
    * In ``adb shell``: ``cd /data/data/com.zwift.zwiftgame/dataES/``
    * In ``adb shell``: ``cat cert-zwift-com.pem >> cacert.pem``
    * However you do it, ensure the permissions and ownership of the file remains the same.
* Modify the device's ``/etc/hosts`` file
  * Append this line: ``<zoffline ip> us-or-rly101.zwift.com secure.zwift.com cdn.zwift.com``
    <br />(Where ``<zoffline ip>`` is the IP address of the machine running zoffline.)
  * If no text editor on the device, recommend:
    * ``adb pull /etc/hosts``
    * (modify on PC)
    * ``adb push hosts /etc/hosts``
  * Note: If you know what you're doing and have a capable enough router you can adjust your router to alter these DNS records instead of modifying your ``hosts`` file.
* Start Zwift and sign in using any email/password
  * If multiplayer is enabled, access https://secure.zwift.com/signup/ to sign up and import your files.

Why: We need to redirect Zwift to use zoffline and convince Zwift to
accept zoffline's self signed certificates for Zwift's domain names. Feel free
to generate your own certificates and do the same.

</details>

#### Enabling/Disabling zoffline

To use Zwift online like normal, comment out or remove the line added to the ``hosts``
file before starting Zwift. Then ensure Zwift is fully closed (right click
the Zwift system tray icon and exit) and restart Zwift.


### Step 3 [OPTIONAL]: Obtain current Zwift profile

<details><summary>Expand</summary>

If you don't obtain your current Zwift profile before first starting Zwift with
zoffline enabled, you will be prompted to create a new profile (height, weight,
gender). Your profile can be further customized and changed via the in game
menu (e.g. name, nationality, weight change, etc).

To obtain your current profile:
* Ensure zoffline is disabled.
* Run ``scripts/get_profile.py -u <your_zwift_username>``
  * Or, if using the Windows zoffline.exe version without Python installed you can run ``get_profile.exe`` obtained from https://github.com/zoffline/zwift-offline/releases/tag/zoffline_helper in place of ``scripts/get_profile.py``
* Move the resulting ``profile.bin`` (saved in whatever directory you ran get_profile.py in) into the ``storage`` directory.
  * If using zoffline.exe on Windows, create a ``storage`` directory within the same folder as zoffline.exe if it does not already exist.
  * If multiplayer is enabled, use the upload button in the launcher window to import your file.
  * If using Docker, move ``profile.bin`` into the path you passed to ``-v``

</details>

### Step 4 [OPTIONAL]: Upload activities to Strava

<details><summary>Expand</summary>

* Install dependencies: stravalib
  * e.g., on Linux/Mac: ``pip3 install stravalib``
  * e.g., on Windows in command prompt: ``pip install stravalib``
    * You may need to use ``C:\Users\<username>\AppData\Local\Programs\Python\Python39\Scripts\pip.exe`` instead of just ``pip``
  * Or, if using the Windows zoffline.exe version without Python installed you can run ``strava_auth.exe`` obtained from https://github.com/zoffline/zwift-offline/releases/tag/zoffline_helper in place of ``scripts/strava_auth.py`` below.
* [OPTIONAL] Get CLIENT_ID and CLIENT_SECRET from https://www.strava.com/settings/api
* Run ``scripts/strava_auth.py --client-id CLIENT_ID --client-secret CLIENT_SECRET``
  * Run without arguments to use default values.
* Open http://localhost:8000/ and authorize.
* Move the resulting ``strava_token.txt`` (saved in whatever directory you ran ``strava_auth.py`` in) into the ``storage/<player_id>`` directory.
  * If multiplayer is enabled, use the upload button in the launcher window to import your file.

</details>

### Step 5 [OPTIONAL]: Upload activities to Garmin Connect

<details><summary>Expand</summary>

* Install dependencies: garmin-uploader, cryptography (optional)
  * e.g., on Linux/Mac: ``pip3 install garmin-uploader cryptography``
  * e.g., on Windows in command prompt: ``pip install garmin-uploader cryptography``
    * You may need to use ``C:\Users\<username>\AppData\Local\Programs\Python\Python39\Scripts\pip.exe`` instead of just ``pip``
* Create a file ``garmin_credentials.txt`` in the ``storage/<player_id>`` directory containing your login credentials
  ```
  <username>
  <password>
  ```
  * Note: this is not secure. Only do this if you are comfortable with your login credentials being stored in a clear text file.
  * If multiplayer is enabled, use the upload button in the launcher window to encrypt the credentials file.

</details>

### Step 6 [OPTIONAL]: Enable multiplayer

<details><summary>Expand</summary>

To enable support for multiple users perform the steps below. zoffline's previous multi-profile support has been superceded by full multiplayer support. If you were previously using multiple profiles with zoffline you will need to enable multiplayer to continue supporting multiple users.

* Create a ``multiplayer.txt`` file in the ``storage`` directory.
* If you are not running zoffline on the same PC that Zwift is running: create a ``server-ip.txt`` file in the ``storage`` directory containing the IP address of the PC running zoffline.
  * TCP ports 80, 443, 3023 and UDP port 3022 will need to be open on the PC running zoffline if its running remotely.
* Start Zwift and create an account in the new Zwift launcher and upload your ``profile.bin``, ``strava_token.txt``, and/or ``garmin_credentials.txt`` if you have them.
  * This account will only exist on your zoffline server and has no relation with your actual Zwift account.

</details>

### Extra optional steps
<details><summary>Expand</summary>

* To obtain the official map schedule and update files from Zwift server: create a ``cdn-proxy.txt`` file in the ``storage`` directory. This can only work if you are running zoffline on a different machine than the Zwift client.
* To enable the password reset feature when multiplayer is enabled: create a ``gmail_credentials.txt`` file in the ``storage`` directory containing the login credentials of a Gmail account. You need to enable the "Less secure app access" in the account settings and you may need to access https://accounts.google.com/DisplayUnlockCaptcha to allow the login from the server.
* To enable the Discord bridge bot: ``pip3 install discord`` and create a ``discord.cfg`` file in the ``storage`` directory containing
  ```
  [discord]
  token = 
  webhook = 
  channel = 
  welcome_message = 
  help_message = 
  ```
* If the Zwift client is having issues connecting to the Linux server ("The request was aborted: Could not create SSL/TLS secure channel." or "The underlying connection was closed: An unexpected error occurred on a send. Received an unexpected EOF or 0 bytes from the transport stream."): change MinProtocol in /etc/ssl/openssl.cnf to TLSv1.0
  ```
  [system_default_sect]
  MinProtocol = TLSv1.0
  CipherString = DEFAULT@SECLEVEL=1
  ```
</details>

## Community Discord and zoffline (online) server

Please join the community supported [Discord](https://discord.gg/GMdn8F8) and their enhanced version of zoffline, hosted Online!

Follow the guide in #instructions to create your account and join other Zwifters.

## Dependencies

Docker

-or-

* Python 3 (https://www.python.org/downloads/)
  * On Windows, installing Python via the Microsoft Store is highly recommend! If using a Python installer, ensure that in the first Python installer screen "Add Python 3.x to PATH" is checked.
  * Python 2 remains supported for now, but it is not recommended.
* Flask (http://flask.pocoo.org/)
  * ``pip3 install flask``
* python-protobuf (https://pypi.org/project/protobuf/)
  * ``pip3 install protobuf``
* protobuf3_to_dict (https://github.com/kaporzhu/protobuf-to-dict)
  * ``pip3 install protobuf3_to_dict``
* pyJWT (https://pyjwt.readthedocs.io/)
  * ``pip3 install pyjwt``
* flask-login (https://flask-login.readthedocs.io/en/latest/)
  * ``pip3 install flask-login``
* FlaskSQLAlchemy (https://flask-sqlalchemy.palletsprojects.com/en/2.x/)
  * ``pip3 install flask_sqlalchemy``
* gevent (http://www.gevent.org/)
  * ``pip3 install gevent``
* OPTIONAL: stravalib (https://github.com/hozn/stravalib)
  * ``pip3 install stravalib``
* OPTIONAL: garmin-uploader (https://github.com/La0/garmin-uploader)
  * ``pip3 install garmin-uploader``
* OPTIONAL: cryptography (https://cryptography.io/en/latest/)
  * ``pip3 install cryptography``


## Note

Future Zwift updates may break zoffline until it's updated. While zoffline is
enabled Zwift updates will not be installed. If a zoffline update broke
something, check the ``CHANGELOG`` for possible changes that need to be made.

Don't expose zoffline to the internet, it was not designed with that in mind.

<details><summary>If zoffline is out of date from Zwift's official client</summary>
If zoffline is behind in support of the latest Zwift client it can be updated (if running Linux) to run using the latest Zwift version by running this script from within the zwift-offline repository: https://gist.github.com/zoffline/b874e93e24439f0f4fbd7b55f3876fd2

Note: there is no guarantee that an untested Zwift update will work with zoffline. However, historically, Zwift updates rarely break zoffline.
</details>


## Disclaimer

Zwift is a trademark of Zwift, Inc., which is not affiliated with the maker of
this project and does not endorse this project.

All product and company names are trademarks of their respective holders. Use of
them does not imply any affiliation with or endorsement by them.

