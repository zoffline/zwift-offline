# zoffline

zoffline enables the use of [Zwift](http://zwift.com) offline by acting as a partial implementation
of a Zwift server. Currently it's designed for only a single user at a time and the UDP
game node is minimally implemented.

zoffline also offers riding against ghosts (your previous rides). Enable this feature by checking "Enable ghosts" in zoffline's launcher. See https://github.com/zoffline/zwift-offline/issues/56 for extra details.

Additionally, zoffline's launcher allows selecting a specific map to ride on without mucking about with config files.

## Install

Setting up zoffline requires two primary steps. First, zoffline must be installed and run on a system before running Zwift (either on the system running Zwift or on another locally networked system).  Second, Zwift must be configured to use zoffline instead of the official Zwift server.

### Step 1: Install zoffline
There are three ways with which to install and run zoffline depending on your platform:

<details><summary>Simplest (Windows only)</summary>
To install zoffline on Windows:

* Download the latest zoffline release from https://github.com/zoffline/zwift-offline/releases
* Run the downloaded zoffline.exe
  * Once run, zoffline will create a ``storage`` directory in the same folder it's in to store your Zwift progress.
* Start Zwift with zoffline.exe running (__after completing step 2__ or running __configure_client__ script from https://github.com/zoffline/zwift-offline/releases/tag/zoffline_helper)
  * It takes zoffline a few seconds to start. Wait until text appears in the command prompt before opening Zwift.
* When done with Zwift, press Ctrl+C in the command line to close zoffline.
</details>

<details><summary>Linux, Windows, or Mac OS X (from source)</summary>
To install zoffline on Linux, Windows, or Mac OS X:

* Install Python 2 or 3 (https://www.python.org/downloads/) if not already installed
* Install dependencies: flask, flask_sqlalchemy, python-protobuf, protobuf3_to_dict, stravalib (optional)
  * e.g., on Linux/Mac: ``pip install flask flask_sqlalchemy flask-login pyjwt protobuf protobuf3_to_dict stravalib``
  * e.g., on Windows in command prompt: ``C:\Python27\Scripts\pip.exe install flask flask_sqlalchemy flask-login pyjwt protobuf protobuf3_to_dict stravalib``
    * Python 3 is installed by default in ``C:\Users\<username>\AppData\Local\Programs\Python\Python38-32`` instead of ``C:\Python27``
* Clone or download this repo
* If you are not running zoffline on the same PC that Zwift is running: create a ``server-ip.txt`` file in the ``storage`` directory containing the IP address of the PC running zoffline.
* Run standalone.py before starting Zwift
  * e.g., on Linux/Mac: ``sudo ./standalone.py``
    * sudo is needed because we're binding to the privileged ports 80 and 443.
    * If using Python 3, but Python 3 is not your system default run ``sudo python3 standalone.py``
  * e.g., on Windows in command prompt: ``C:\Python27\python.exe standalone.py``
    * For Python 3 the command will likely be ``C:\Users\<username>\AppData\Local\Programs\Python\Python38-32\python.exe standalone.py``
* Start Zwift with standalone.py running (__after completing step 2__)
* Note: When upgrading zoffline, be sure to retain the ``storage`` directory. It contains your Zwift progress state.

zoffline can be installed on the same machine as Zwift or another local machine.
</details>


<details><summary>Using Docker</summary>
 
* Install Docker
* Create the docker container with:<br>
  ``docker create --name zwift-offline -p 443:443 -p 80:80 -p 3022:3022/udp -p 3023:3023 -v </path/to/host/storage>:/usr/src/app/zwift-offline/storage -e TZ=<timezone> zoffline/zoffline``
  * You can optionally exclude ``-v </path/to/host/storage>:/usr/src/app/zwift-offline/storage`` if you don't care if your Zwift progress state is retained across zoffline updates (unlikely).
  * The path you pass to ``-v`` will likely need to be world readable and writable.
  * A list of valid ``<timezone>`` values (e.g. America/New_York) can be found [here](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).
  * Adding ``--restart unless-stopped`` will make zoffline start on boot if you have Docker v1.9.0 or greater.
* If you are not running zoffline on the same PC that Zwift is running: create a ``server-ip.txt`` file in the ``</path/to/host/storage>`` directory containing the IP address of the PC running zoffline.
* Start zoffline with:
  ``docker start zwift-offline``
</details>


### Step 2: Configure Zwift client to use zoffline

<details><summary>Windows Instructions</summary>

* Install Zwift
  * If your Zwift version is 1.0.58982, you're all set.
  * If Zwift is not installed, install it before installing zoffline.
  * If your Zwift version is newer than 1.0.58982 and zoffline is running from source: copy ``C:\Program Files (x86)\Zwift\Zwift_ver_cur.xml`` to zoffline's ``cdn/gameassets/Zwift_Updates_Root/`` overwriting the existing file.
  * If your Zwift version is newer than 1.0.58982 and zoffline is not running from source: wait for zoffline to be updated.
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

Why: We need to redirect Zwift to use zoffline and convince Windows and Zwift to
accept zoffline's self signed certificates for Zwift's domain names. Feel free
to generate your own certificates and do the same.

</details>

<details><summary>Mac OS X Instructions (Thanks @oldnapalm!)</summary>

* Install Zwift
  * If your Zwift version is 1.0.58982, you're all set.
  * If Zwift is not installed, install it before installing zoffline.
  * If your Zwift version is newer than 1.0.58982: copy ``~/Library/Application Support/Zwift/ZwiftMac_ver_cur.xml`` to zoffline's ``cdn/gameassets/Zwift_Updates_Root/`` overwriting the existing file.
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
* Using a text editor (with admin privileges) open ``/etc/hosts``
  * Append this line: ``<zoffline ip> us-or-rly101.zwift.com secure.zwift.com cdn.zwift.com launcher.zwift.com``
    <br />(Where ``<zoffline ip>`` is the ip address of the machine running zoffline. If
    it's running on the same machine as Zwift, use ``127.0.0.1`` as the ip.)

Why: We need to redirect Zwift to use zoffline and convince OS X and Zwift to
accept zoffline's self signed certificates for Zwift's domain names. Feel free
to generate your own certificates and do the same.

</details>

<details><summary>Android (requires a rooted device)</summary>

* Install Zwift on the device
* Open Zwift once to complete installation (i.e download all extra files).
* Append the contents of ``ssl/cert-zwift-com.pem`` to ``/data/data/com.zwift.zwiftgame/dataES/cacerts.pem`` on the device
  * Note: this file will only exist after the first run of Zwift since it's downloaded after the initial install
  * Recommended approach for appending the contents (due to [#62](https://github.com/zoffline/zwift-offline/issues/62)):
    * ``adb push ssl/cert-zwift-com.pem /data/data/com.zwift.zwiftgame/dataES/``
    * In ``adb shell``: ``cd /data/data/com.zwift.zwiftgame/dataES/``
    * In ``adb shell``: ``cat cert-zwift-com.pem >> cacert.pem``
    * However you do it, ensure the permissions and ownership of the file remains the same.
* Modify the device's /etc/hosts file
  * Append this line: ``<zoffline ip> us-or-rly101.zwift.com secure.zwift.com cdn.zwift.com``
    <br />(Where ``<zoffline ip>`` is the ip address of the machine running zoffline.)
  * If no text editor on the device, recommend:
    * ``adb pull /etc/hosts``
    * (modify on PC)
    * ``adb push hosts /etc/hosts``
* Start Zwift and sign in using any email/password
  * To change profile, sign in using ``player_id`` (numeric, default is 1000) and any password (Thanks @kienkhuat!)

Why: We need to redirect Zwift to use zoffline and convince Zwift to
accept zoffline's self signed certificates for Zwift's domain names. Feel free
to generate your own certificates and do the same.

</details>

#### Enabling/Disabling zoffline

To use Zwift online like normal, comment out or remove the line added to the ``hosts``
file before starting Zwift. Then ensure Zwift is fully closed (right click
the Zwift system tray icon and exit) and restart Zwift.


### Step 3 [OPTIONAL]: Obtain current Zwift profile

If you don't obtain your current Zwift profile before first starting Zwift with
zoffline enabled, you will be prompted to create a new profile (height, weight,
gender). Your profile can be further customized and changed via the in game
menu (e.g. name, nationality, weight change, etc).

To obtain your current profile:
* Ensure zoffline is disabled.
* Run ``scripts/get_profile.py -u <your_zwift_username>``
  * Or, if using the Windows zoffline.exe version without Python installed you can run get_profile.exe obtained from https://github.com/zoffline/zwift-offline/releases/tag/zoffline_helper in place of ``scripts/get_profile.py``
* Move the resulting profile.bin (saved in whatever directory you ran get_profile.py in) into the ``storage`` directory.
  * If using zoffline.exe on Windows, create the ``storage`` directory within the same folder as zoffline.exe if it does not already exist.
  * If using Docker, move profile.bin into the path you passed to ``-v``


### Step 4 [OPTIONAL]: Obtain Strava API token

* Install dependencies: stravalib
  * e.g., on Linux/Mac: ``pip install stravalib``
  * e.g., on Windows in command prompt: ``C:\Python27\Scripts\pip.exe install stravalib``
  * Or, if using the Windows zoffline.exe version without Python installed you can run strava_auth.exe obtained from https://github.com/zoffline/zwift-offline/releases/tag/zoffline_helper in place of ``scripts/strava_auth.py`` below.
* Get CLIENT_ID and CLIENT_SECRET from https://www.strava.com/settings/api
* Run ``scripts/strava_auth.py --client-id CLIENT_ID --client-secret CLIENT_SECRET``
* Open http://localhost:8000/ and authorize.
* Move the resulting strava_token.txt (saved in whatever directory you ran strava_auth.py in) into the ``storage/<player_id>`` directory.


### Step 5 [OPTIONAL]: Upload activities to Garmin Connect

* Install dependencies: garmin-uploader
  * e.g., on Linux/Mac: ``pip install garmin-uploader``
  * e.g., on Windows in command prompt: ``C:\Python27\Scripts\pip.exe install garmin-uploader``
* Create a file garmin_credentials.txt in the ``storage/<player_id>`` directory containing your login credentials
  ```
  <username>
  <password>
  ```
  * Note: this is not secure. Only do this if you are comfortable with your login credentials being stored in a clear text file.

## Discord and zoffline (online) server

Please join the [Discord](https://discord.gg/GMdn8F8) and our enhanced version of zoffline, hosted Online!

Follow the guide in #instructions to create your account and join other Zwifters.

## Dependencies

Docker

-or-

* Python 2 or 3 (https://www.python.org/downloads/)
* Flask (http://flask.pocoo.org/)
  * ``pip install flask``
* python-protobuf (https://pypi.org/project/protobuf/)
  * ``pip install protobuf``
* protobuf3_to_dict (https://github.com/kaporzhu/protobuf-to-dict)
  * ``pip install protobuf3_to_dict``
* pyJWT (https://pyjwt.readthedocs.io/)
  * ``pip install pyjwt``
* flask-login (https://flask-login.readthedocs.io/en/latest/)
  * ``pip install flask-login``
* FlaskSQLAlchemy (https://flask-sqlalchemy.palletsprojects.com/en/2.x/)
  * ``pip install flask_sqlalchemy``
* OPTIONAL: stravalib (https://github.com/hozn/stravalib)
  * ``pip install stravalib``
* OPTIONAL: garmin-uploader (https://github.com/La0/garmin-uploader)
  * ``pip install garmin-uploader``


## Note

Future Zwift updates may break zoffline until it's updated. While zoffline is
enabled Zwift updates will not be installed.

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

