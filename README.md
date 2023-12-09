# zoffline

zoffline enables the use of [Zwift](http://zwift.com) offline by acting as a partial implementation of a Zwift server. By default zoffline is only for a single player. See [Step 6: Enable Multiplayer](#step-6-optional-enable-multiplayer) for how to enable support for multiple users/profiles.

zoffline also offers riding against ghosts (your previous rides). Enable this feature by checking "Enable ghosts" in zoffline's launcher. See [ghosts and bots](https://github.com/zoffline/zwift-offline/wiki/Ghosts-and-bots) for extra details.

Additionally, zoffline's launcher allows selecting a specific map to ride on without mucking about with config files.

## Install

Setting up zoffline requires two primary steps. First, zoffline must be installed and run on a system before running Zwift (either on the system running Zwift or on another locally networked system).  Second, Zwift must be configured to use zoffline instead of the official Zwift server.

### Step 1: Install zoffline
There are three ways with which to install and run zoffline depending on your platform:

<details><summary>Simplest (Windows only)</summary>
To install zoffline on Windows:

* Download the latest zoffline release from https://github.com/zoffline/zwift-offline/releases/latest
  * If you want the pace partners, download the source code package and extract the ``pace_partners`` directory to the same folder zoffline is in.
* If you are not running zoffline on the same PC that Zwift is running: create a ``server-ip.txt`` file in the ``storage`` directory containing the IP address of the PC running zoffline.
* Run the downloaded zoffline.exe
  * Once run, zoffline will create a ``storage`` directory in the same folder it's in to store your Zwift progress.
* Start Zwift with zoffline.exe running (__after completing step 2__ or running __configure_client__ script from https://github.com/zoffline/zwift-offline/releases/tag/zoffline_helper)
  * It takes zoffline a few seconds to start. Wait until text appears in the command prompt before opening Zwift.
* When done with Zwift, press Ctrl+C in the command line to close zoffline.
</details>

<details><summary>Linux, Windows, or macOS (from source)</summary>
To install zoffline on Linux, Windows, or macOS:

* Install Python 3 (https://www.python.org/downloads/) if not already installed
  * On Windows, installing Python via the Microsoft Store is highly recommend! If using a Python installer, ensure that in the first Python installer screen "Add Python 3.x to PATH" is checked.
* Clone or download this repo
* Install dependencies
  * e.g., on Linux/Mac: ``pip3 install -r requirements.txt``
  * e.g., on Windows in command prompt: ``pip install -r requirements.txt``
    * You may need to use ``C:\Users\<username>\AppData\Local\Programs\Python\Python<version>\Scripts\pip.exe`` instead of just ``pip``
* If you are not running zoffline on the same PC that Zwift is running: create a ``server-ip.txt`` file in the ``storage`` directory containing the IP address of the PC running zoffline.
* Run standalone.py before starting Zwift
  * e.g., on Linux/Mac: ``sudo ./standalone.py``
    * sudo is needed because we're binding to the privileged ports 80 and 443.
    * If Python 3 is not your system default run ``sudo python3 standalone.py``
  * e.g., on Windows in command prompt: ``python standalone.py``
    * You may need to use ``C:\Users\<username>\AppData\Local\Programs\Python\Python<version>\python.exe`` instead of just ``python``
* Start Zwift with standalone.py running (__after completing step 2__)
* Note: When upgrading zoffline, be sure to retain the ``storage`` directory. It contains your Zwift progress state.

zoffline can be installed on the same machine as Zwift or another local machine.
</details>


<details><summary>Using Docker</summary>
 
* Install Docker
* Create the docker container with:<br>
  ``docker create --name zwift-offline -p 443:443 -p 80:80 -p 3024:3024/udp -p 3025:3025 -p 53:53/udp -v </path/to/host/storage>:/usr/src/app/zwift-offline/storage -e TZ=<timezone> zoffline/zoffline``
  * You can optionally exclude ``-v </path/to/host/storage>:/usr/src/app/zwift-offline/storage`` if you don't care if your Zwift progress state is retained across zoffline updates (unlikely).
  * The path you pass to ``-v`` will likely need to be world readable and writable.
  * A list of valid ``<timezone>`` values (e.g. America/New_York) can be found [here](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).
  * Adding ``--restart unless-stopped`` will make zoffline start on boot if you have Docker v1.9.0 or greater.
* If you are not running zoffline on the same PC that Zwift is running: create a ``server-ip.txt`` file in the ``</path/to/host/storage>`` directory containing the IP address of the PC running zoffline.
* Start zoffline with:
  ``docker start zwift-offline``
</details>


<details><summary>Using Docker Compose</summary>
 
* Install docker-compose
* Either use the ``docker-compose.yml`` file in this repo which will build from the Dockerfile, or use this example compose file:
   ```
  version: "3.3"
  services:
      zoffline:
           image: zoffline/zoffline:latest
           container_name: zoffline
           environment:
              - TZ=Europe/London
           volumes:
              - ./storage/:/usr/src/app/zwift-offline/storage
           ports:
              - 80:80
              - 443:443
              - 3024:3024/udp
              - 3025:3025
           restart: unless-stopped    
   ```
* If you are not running zoffline on the same PC that Zwift is running: create a ``server-ip.txt`` file in the ``storage`` directory containing the IP address of the PC running zoffline.
* Start zoffline with:
  ``docker-compose up -d ``
</details>

### Step 2: Configure Zwift client to use zoffline

<details><summary>Windows Instructions</summary>

* Install Zwift
  * If your Zwift version is 1.0.122968, you're all set.
  * If Zwift is not installed, install it before installing zoffline.
  * If your Zwift version is newer than 1.0.122968 and zoffline is running from source: copy ``C:\Program Files (x86)\Zwift\Zwift_ver_cur.xml`` to zoffline's ``cdn/gameassets/Zwift_Updates_Root/`` overwriting the existing file.
  * If your Zwift version is newer than 1.0.122968 and zoffline is not running from source: wait for zoffline to be updated.
* __NOTE:__ instead of performing the steps below you can instead just run the __configure_client__ script from https://github.com/zoffline/zwift-offline/releases/tag/zoffline_helper
* On your Windows machine running Zwift, copy the following files in this repo to a known location:
  * [ssl/cert-zwift-com.p12](https://github.com/zoffline/zwift-offline/raw/master/ssl/cert-zwift-com.p12)
  * [ssl/cert-zwift-com.pem](https://github.com/zoffline/zwift-offline/raw/master/ssl/cert-zwift-com.pem)
* Open Command Prompt as an admin, cd to that location and run
  * ``certutil.exe -importpfx Root cert-zwift-com.p12``
  * If you're prompted for a password, just leave it blank. There is no password.
* Open Notepad as an admin and open ``C:\Program Files (x86)\Zwift\data\cacert.pem``
  * Append the contents of ``ssl/cert-zwift-com.pem`` to cacert.pem
* Open Notepad as an admin and open ``C:\Windows\System32\Drivers\etc\hosts``
  * Append this line: ``<zoffline ip> us-or-rly101.zwift.com secure.zwift.com cdn.zwift.com launcher.zwift.com``
    <br />(Where ``<zoffline ip>`` is the ip address of the machine running zoffline. If
    it's running on the same machine as Zwift, use ``127.0.0.1`` as the ip.)
* If you wish to leave the ``hosts`` file unchanged except for when specifically using zoffline, you may optionally use the __launch.bat__ script within the ``scripts`` directory to launch zoffline instead of using the normal Zwift Launcher. See [#121](https://github.com/zoffline/zwift-offline/issues/121) for details.

Why: We need to redirect Zwift to use zoffline and convince Windows and Zwift to
accept zoffline's self signed certificates for Zwift's domain names. Feel free
to generate your own certificates and do the same.

</details>

<details><summary>macOS Instructions</summary>

* Install Zwift
  * If your Zwift version is 1.0.122968, you're all set.
  * If Zwift is not installed, install it before installing zoffline.
  * If your Zwift version is newer than 1.0.122968: copy ``~/Library/Application Support/Zwift/ZwiftMac_ver_cur.xml`` to zoffline's ``cdn/gameassets/Zwift_Updates_Root/`` overwriting the existing file.
* On your Mac machine running Zwift, copy the following files in this repo to a known location:
  * [ssl/cert-zwift-com.p12](https://github.com/zoffline/zwift-offline/raw/master/ssl/cert-zwift-com.p12)
  * [ssl/cert-zwift-com.pem](https://github.com/zoffline/zwift-offline/raw/master/ssl/cert-zwift-com.pem)
* Open Keychain Access, select "System" under "Keychains", select "Certificates" under "Category"
    * Click "File - Import Items..." and import ``ssl/cert-zwift-com.p12``
    * Right click "\*.zwift.com", select "Get Info" and under "Trust" choose "When using this certificate: Always Trust".
    * If you're prompted for a password, just leave it blank. There is no password.
* Using a text editor open ``~/Library/Application Support/Zwift/data/cacert.pem``
  * Append the contents of the SSL certificate ``ssl/cert-zwift-com.pem`` to cacert.pem (only the certificate and not the included private key)
* Using a text editor (with admin privileges) open ``/Applications/Zwift.app/Contents/Info.plist``
  * Insert in the main dict:
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
* Run ``sudo codesign --force --deep --sign - /Applications/Zwift.app`` in terminal. See https://github.com/zoffline/zwift-offline/issues/132 for extra details.
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
  * Download and install ``ZofflineObb.apk`` from [here](https://github.com/Argon2000/ZofflineObbAndroid/releases/latest)
  * Download and install ``app-Github-release.apk`` from [here](https://github.com/x-falcon/Virtual-Hosts/releases/latest)
  * Create a `hosts.txt` file to use with the app (you could use a text editor app or create it online with an online tool such as [this](https://passwordsgenerator.net/text-editor/)). The file must look like this (replace ``<zoffline ip>`` with the IP address of the machine running zoffline):
  ```
  <zoffline ip> us-or-rly101.zwift.com
  <zoffline ip> secure.zwift.com
  <zoffline ip> cdn.zwift.com
  ```
  * Run "Virtual Hosts", select the created `hosts.txt` file, fully close (touch the "overview" button and swipe up) the app and run it again
  * Optionally, instead of using the "Virtual Hosts" app, you can create a ``fake-dns.txt`` file in the ``storage`` directory and set the "DNS 1" of your phone Wi-Fi connection to the IP address of the PC running zoffline
  * Note: If you know what you're doing and have a capable enough router you can adjust your router to alter these DNS records instead of using the "Virtual Hosts" app or changing your phone DNS.
* Patch after every installation or update:
  * Install/update Zwift from Google play, but do not start it yet.
    * If you have already started it go to `Android Settings > Applications > Zwift` and clear data or uninstall and reinstall the app.
  * Open the `ZofflineObb` app and run it (allow access to storage)
  * Wait for process to finish (5-10min)
  * Run Zwift, hopefully it verifies download and runs
* Play Zwift:
  * Virtual Hosts button must be ON
  * Start Zwift and sign in using any email/password
    * If multiplayer is enabled, access `https://<zoffline ip>/signup/` to sign up and import your files. (You must accept an invalid certificate alert).

Why: We need to redirect Zwift to use zoffline (this is done by the Virtual Hosts app) and convince Zwift to
accept zoffline's self signed certificates for Zwift's domain names (this is done by the patch tool ZofflineObb).

</details>

<details><summary>Android (rooted device)</summary>

* Install Zwift on the device
* Open Zwift once to complete installation (i.e download all extra files).
* Append the contents of ``ssl/cert-zwift-com.pem`` to ``/data/data/com.zwift.zwiftgame/dataES/cacert.pem`` on the device
  * Note: this file will only exist after the first run of Zwift since it's downloaded after the initial install
  * Simple approach to achieve this if your device doesn't have a text editor:
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
  * If multiplayer is enabled, access `https://<zoffline ip>/signup/` to sign up and import your files.

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
* __NOTE:__ instead of performing the steps below you can instead use the "Settings - Zwift" button in the launcher window (Windows and macOS only).
* Ensure zoffline is disabled.
* Run ``scripts/get_profile.py -u <your_zwift_username>``
  * Or, if using the Windows zoffline.exe version without Python installed you can run ``get_profile.exe`` obtained from https://github.com/zoffline/zwift-offline/releases/tag/zoffline_helper in place of ``scripts/get_profile.py``
* Move the resulting ``profile.bin`` and ``achievements.bin`` (saved in whatever directory you ran get_profile.py in) into the ``storage/1`` directory.
  * If using zoffline.exe on Windows, create a ``storage/1`` directory within the same folder as zoffline.exe if it does not already exist.
  * If using Docker, the directory ``1`` should be in the path you passed to ``-v``

</details>

### Step 4 [OPTIONAL]: Upload activities to Strava

<details><summary>Expand</summary>

* __NOTE:__ instead of performing the steps below you can instead use the "Settings - Strava" button in the launcher window to authorize (Windows and macOS only).
* [OPTIONAL] Get CLIENT_ID and CLIENT_SECRET from https://www.strava.com/settings/api
* Run ``scripts/strava_auth.py --client-id CLIENT_ID --client-secret CLIENT_SECRET``
  * Or, if using the Windows zoffline.exe version without Python installed you can run ``strava_auth.exe`` obtained from https://github.com/zoffline/zwift-offline/releases/tag/zoffline_helper in place of ``scripts/strava_auth.py``
  * Run without arguments to use default values.
* Open http://localhost:8000/ and authorize.
* Move the resulting ``strava_token.txt`` (saved in whatever directory you ran ``strava_auth.py`` in) into the ``storage/1`` directory.
* If testing, ride at least 300 meters, shorter activities won't be uploaded.

</details>

### Step 5 [OPTIONAL]: Upload activities to Garmin Connect

<details><summary>Expand</summary>

* If running from source, install garth: ``pip install garth``
* __NOTE:__ instead of performing the step below you can instead use the "Settings - Garmin" button in the launcher window to enter your credentials (Windows and macOS only).
* Create a file ``garmin_credentials.txt`` in the ``storage/1`` directory containing your login credentials
  ```
  <username>
  <password>
  ```
  * Note: this is not secure. Only do this if you are comfortable with your login credentials being stored in a clear text file.

</details>

### Step 6 [OPTIONAL]: Enable multiplayer

<details><summary>Expand</summary>

To enable support for multiple users perform the steps below:

* Create a ``multiplayer.txt`` file in the ``storage`` directory.
* If you are not running zoffline on the same PC that Zwift is running: create a ``server-ip.txt`` file in the ``storage`` directory containing the IP address of the PC running zoffline.
  * TCP ports 80, 443, 3025 and UDP port 3024 will need to be open on the PC running zoffline if its running remotely.
* Start Zwift and create an account in the launcher (desktop solution only, for Android go to `https://<zoffline ip>/signup/`).
  * This account will only exist on your zoffline server and has no relation with your actual Zwift account.

</details>

### Step 7 [OPTIONAL]: Install Zwift Companion App

Create a ``server-ip.txt`` file in the ``storage`` directory containing the IP address of the PC running zoffline.

<details><summary>Android (non-rooted device)</summary>

* Install apk-mitm (https://github.com/shroudedcode/apk-mitm)
* Copy the file [ssl/cert-zwift-com.pem](https://github.com/zoffline/zwift-offline/raw/master/ssl/cert-zwift-com.pem) in this repo and the Zwift Companion apk (e.g. ``zca.apk``) to a known location
* Open Command Prompt, cd to that location and run
  * ``apk-mitm --certificate cert-zwift-com.pem zca.apk``
* Copy ``zca-patched.apk`` to your phone and install it
* Download and install ``app-Github-release.apk`` from [here](https://github.com/x-falcon/Virtual-Hosts/releases/latest)
* Create a ``hosts.txt`` file to use with the app (you could use a text editor app or create it online with an online tool such as [this](https://passwordsgenerator.net/text-editor/)). The file must look like this (replace ``<zoffline ip>`` with the IP address of the machine running zoffline):
```
<zoffline ip> us-or-rly101.zwift.com
<zoffline ip> secure.zwift.com
```
* Run "Virtual Hosts", select the created ``hosts.txt`` file, fully close (touch the "overview" button and swipe up) the app and run it again
* Optionally, instead of using the "Virtual Hosts" app, you can create a ``fake-dns.txt`` file in the ``storage`` directory and set the "DNS 1" of your phone Wi-Fi connection to the IP address of the PC running zoffline
* Note: If you know what you're doing and have a capable enough router you can adjust your router to alter these DNS records instead of using the "Virtual Hosts" app or changing your phone DNS.

</details>

### Extra optional steps

<details><summary>Expand</summary>

* To obtain the official map schedule and update files from Zwift server: create a ``cdn-proxy.txt`` file in the ``storage`` directory. This can only work if you are running zoffline on a different machine than the Zwift client.
* To enable the password reset feature when multiplayer is enabled: create a ``gmail_credentials.txt`` file in the ``storage`` directory containing the login credentials of a Gmail account. You need to access https://security.google.com/settings/security/apppasswords and create an app password to allow the login from the server.
* To enable the Discord bridge bot: ``pip3 install discord.py`` and create a ``discord.cfg`` file in the ``storage`` directory containing
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

## Community Discord server and Strava club

Please join the community supported [Discord](https://discord.gg/GMdn8F8) server and [Strava](https://www.strava.com/clubs/zoffline) club.

## Dependencies

Docker

-or-

* Python 3 (https://www.python.org/downloads/)
* Flask (https://flask.palletsprojects.com/)
* python-protobuf (https://pypi.org/project/protobuf/)
* pyJWT (https://pyjwt.readthedocs.io/)
* Flask-Login (https://flask-login.readthedocs.io/)
* Flask-SQLAlchemy (https://flask-sqlalchemy.palletsprojects.com/)
* gevent (http://www.gevent.org/)
* pycryptodome (https://pypi.org/project/pycryptodome/)
* dnspython (https://www.dnspython.org/)
* fitdecode (https://pypi.org/project/fitdecode/)
* stravalib (https://github.com/hozn/stravalib)
* OPTIONAL: garth (https://pypi.org/project/garth/)
* OPTIONAL: discord.py (https://discordpy.readthedocs.io/)


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

