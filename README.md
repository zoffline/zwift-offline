# zoffline

zoffline enables the use of [Zwift](http://zwift.com) offline by acting as a partial implementation of a Zwift server. By default zoffline is only for a single player. See [Step 6: Enable Multiplayer](#step-6-optional-enable-multiplayer) for how to enable support for multiple users/profiles.

zoffline also offers riding against ghosts (your previous rides). Enable this feature by checking "Enable ghosts" in zoffline's launcher. See [Extra features](#extra-features) for more details.

Additionally, zoffline's launcher allows selecting a specific map to ride on without mucking about with config files.

## Install

Setting up zoffline requires two primary steps. First, zoffline must be installed and run on a system before running Zwift (either on the system running Zwift or on another locally networked system).  Second, Zwift must be configured to use zoffline instead of the official Zwift server.

### Step 1: Install zoffline
There are four ways with which to install and run zoffline depending on your platform:

<details><summary>Simplest (Windows only)</summary>
To install zoffline on Windows:

* Download the latest zoffline release from https://github.com/zoffline/zwift-offline/releases/latest
* If you are not running zoffline on the same PC that Zwift is running: create a ``server-ip.txt`` file in the ``storage`` directory containing the IP address of the PC running zoffline.
* Run the downloaded zoffline.exe
  * Once run, zoffline will create a ``storage`` directory in the same folder it's in to store your Zwift progress.
* Start Zwift with zoffline.exe running (__after completing step 2__ or running __configure_client__ script from https://github.com/oldnapalm/zoffline-helper/releases/latest)
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
  ``` yaml
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
  * In the ``volumes`` tag replace ``./storage/`` before the ``:`` with the directory path you want to use as your local zoffline data store.
* If you are not running zoffline on the same PC that Zwift is running: create a ``server-ip.txt`` file in the ``storage`` directory containing the IP address of the PC running zoffline.
* Start zoffline with: ``docker-compose up -d``
</details>

### Step 2: Configure Zwift client to use zoffline

<details><summary>Windows Instructions</summary>

* Install Zwift if not already installed
* __NOTE:__ instead of performing the steps below you can instead just run the __configure_client__ script from https://github.com/oldnapalm/zoffline-helper/releases/latest
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

* Install Zwift if not already installed
* On your Mac machine running Zwift, copy the file [ssl/cert-zwift-com.pem](https://github.com/zoffline/zwift-offline/raw/master/ssl/cert-zwift-com.pem) in this repo to a known location.
* Open Keychain Access, select "System" under "Keychains", select "Certificates" under "Category"
    * Click "File - Import Items..." and import cert-zwift-com.pem
    * Right click "\*.zwift.com", select "Get Info" and under "Trust" choose "When using this certificate: Always Trust".
* From the cert-zwift-com.pem location, run ``sed -n '29,53p' cert-zwift-com.pem >> ~/Library/Application\ Support/Zwift/data/cacert.pem``
* Using a text editor (with admin privileges) open ``/etc/hosts``
  * Append this line: ``<zoffline ip> us-or-rly101.zwift.com secure.zwift.com cdn.zwift.com launcher.zwift.com``
    <br />(Where ``<zoffline ip>`` is the ip address of the machine running zoffline. If
    it's running on the same machine as Zwift, use ``127.0.0.1`` as the ip.)

Why: We need to redirect Zwift to use zoffline and convince macOS and Zwift to
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
  * Turn off "Private DNS" in Android settings
  * Run "Virtual Hosts" and select the created `hosts.txt` file
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
  * Start Zwift and sign in using any email/password or create a new user if multiplayer is enabled.

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
* Start Zwift and sign in using any email/password or create a new user if multiplayer is enabled.

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
* __NOTE:__ instead of performing the steps below you can instead use the "Settings - Zwift" button in the launcher window (if using Android, access ``https://<zoffline_ip>/profile/zoffline/``).
* Ensure zoffline is disabled.
* Run ``scripts/get_profile.py -u <your_zwift_username>``
  * Or, if using the Windows zoffline.exe version without Python installed you can run ``get_profile.exe`` obtained from https://github.com/oldnapalm/zoffline-helper/releases/latest in place of ``scripts/get_profile.py``
* Move the resulting ``profile.bin``, ``achievements.bin`` and ``economy_config.txt`` (saved in whatever directory you ran get_profile.py in) into the ``storage/1`` directory.
  * If using zoffline.exe on Windows, create a ``storage/1`` directory within the same folder as zoffline.exe if it does not already exist.
  * If using Docker, the directory ``1`` should be in the path you passed to ``-v``

</details>

### Step 4 [OPTIONAL]: Upload activities

<details><summary>Strava</summary>

* Get CLIENT_ID and CLIENT_SECRET from https://www.strava.com/settings/api
* __NOTE:__ instead of performing the steps below you can instead set the authorization callback domain of your API application to ``launcher.zwift.com`` and use the "Settings - Strava" button in the launcher window (Windows and macOS only).
* Run ``scripts/strava_auth.py --client-id CLIENT_ID --client-secret CLIENT_SECRET``
  * Or, if using the Windows zoffline.exe version without Python installed you can run ``strava_auth.exe`` obtained from https://github.com/oldnapalm/zoffline-helper/releases/latest in place of ``scripts/strava_auth.py``
* Open http://localhost:8000/ and authorize.
* Move the resulting ``strava_token.txt`` (saved in whatever directory you ran ``strava_auth.py`` in) into the ``storage/1`` directory.
* Automatic screenshots upload is not possible, see [#28](https://github.com/zoffline/zwift-offline/issues/28) for details.

</details>

<details><summary>Garmin Connect</summary>

* If running from source, install garth: ``pip install garth``
* If needed, create a file ``garmin_domain.txt`` in the ``storage`` directory containing the domain
  * For China use ``garmin.cn``
* Use the "Settings - Garmin" button in the launcher window to enter your credentials (if using Android, access ``https://<zoffline_ip>/garmin/zoffline/``).
* If your account has multi-factor authentication, run the script ``garmin_auth.py`` and move the resulting ``garth`` folder (saved in whatever directory you ran ``garmin_auth.py`` in) into the ``storage/1`` directory.
  * Or, if using the Windows zoffline.exe version without Python installed you can run ``garmin_auth.exe`` obtained from https://github.com/oldnapalm/zoffline-helper/releases/latest instead.

</details>

<details><summary>Intervals.icu</summary>

* Use the "Settings - Intervals" button in the launcher window to enter your credentials (if using Android, access ``https://<zoffline_ip>/intervals/zoffline/``).
* Copy "Athlete ID" and "API Key" from https://intervals.icu/settings under "Developer Settings".

</details>

### Step 5 [OPTIONAL]: Install Zwift Companion App

<details><summary>Android (non-rooted device)</summary>

* Install apk-mitm (https://github.com/shroudedcode/apk-mitm)
* Open ``apk-mitm/dist/tools/apktool.js`` (run ``npm root -g`` to find its location) and edit it like this:
  ``` js
      decode(inputPath, outputPath) {
          return this.run([
              'decode',
              '-resm', // add this
              'dummy', // add this
              inputPath,
              '--output',
              outputPath,
              '--frame-path',
              this.options.frameworkPath,
          ], 'decoding');
      }
  ```
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
  * Important: don't add ``cdn.zwift.com`` to ``hosts.txt``, Companion needs to download images from the official server
* Turn off "Private DNS" in Android settings
* Run "Virtual Hosts" and select the created ``hosts.txt`` file
* Optionally, instead of using the "Virtual Hosts" app, you can create a ``fake-dns.txt`` file in the ``storage`` directory and set the "DNS 1" of your phone Wi-Fi connection to the IP address of the PC running zoffline
* Note: If you know what you're doing and have a capable enough router you can adjust your router to alter these DNS records instead of using the "Virtual Hosts" app or changing your phone DNS.

</details>

### Step 6 [OPTIONAL]: Enable multiplayer

<details><summary>Expand</summary>

To enable support for multiple users perform the steps below:

* Create a ``multiplayer.txt`` file in the ``storage`` directory.
* If you are not running zoffline on the same PC that Zwift is running: create a ``server-ip.txt`` file in the ``storage`` directory containing the IP address of the PC running zoffline.
  * TCP ports 80, 443, 3025 and UDP port 3024 will need to be open on the PC running zoffline if it's running remotely.
* Start Zwift and create an account.
  * This account will only exist on your zoffline server and has no relation with your actual Zwift account.
* To enable the password reset feature: create a ``gmail_credentials.txt`` file in the ``storage`` directory containing the login credentials of a Gmail account.
  * You need to access https://security.google.com/settings/security/apppasswords and create an app password to allow the login from the server.
  * Optionally, the third line can contain the host for the recovery URL (server IP will be used by default).

</details>

### Extra features

<details><summary>Ghosts</summary>

* Enable this feature by checking "Enable ghosts" in zoffline's launcher (if using Android, access ``https://<zoffline_ip>/user/zoffline/``, check "Enable ghosts" and click "Start Zwift" to save the option).
* When you save an activity, the ghost will be saved in ``storage/<player_id>/ghosts/<world>/<route>``. Next time you ride the same route, the ghost will be loaded.
* Type ``.regroup`` in chat to regroup the ghosts.
* Equipment can be customized by creating a file ``ghost_profile.txt`` inside the ``storage`` folder. The script ``find_equip.py`` can be used to populate this file.
</details>

<details><summary>Bots</summary>

* Create a file ``enable_bots.txt`` inside the ``storage`` folder to load ghosts as bots, they will keep riding around regardless of the route you are riding.
* Optionally, ``enable_bots.txt`` can contain a multiplier value (be careful, if the resulting number of bots is too high, it may cause performance issues or not work at all).
* Names, nationalities and equipment can be customized by creating a file ``bot.txt`` inside the ``storage`` folder. The script ``get_pro_names.py`` can be used to populate this file.
* If you want some random bots, check [this repository](https://github.com/oldnapalm/zoffline-bots).
</details>

<details><summary>RoboPacers</summary>

* RoboPacers are ghosts saved using a power simulator, you can find some in [this repository](https://github.com/oldnapalm/zoffline-bots).
* The ghost must be recorded using update frequency of 1 second (default is 3 seconds).
* The activity must start and finish at the same position and speed, otherwise the bot won't loop smoothly.
* The profile must contain a unique player ID and the route ID, so that when you join the bot you take the same turns at intersections.
* The script ``bot_editor.py`` can be used to modify ``profile.bin`` (set name, player ID and route ID) and ``route.bin`` (cut the exceeding points to make a perfect loop).
* If you want to create a dynamic RoboPacer (increase power on climbs and decrease on descents) you can use [standalone_power.py](https://github.com/oldnapalm/zwift-offline/blob/master/standalone_power.py) (requires 2 ANT sticks, [python-ant](https://github.com/mch/python-ant) and [PowerMeterTx.py](https://github.com/oldnapalm/zwift-offline/blob/master/PowerMeterTx.py)).
</details>

<details><summary>Bookmarks</summary>

* When you finish an activity, your last position will be saved as a bookmark.
* Bookmarks can also be saved using the command ``.bookmark <name>`` in the chat.
* You can start a new activity from a bookmark by selecting it in "Join a Zwifter" on the home screen.
* You can teleport to a bookmark using the teleport icon on the action bar.
</details>

<details><summary>All-time leaderboards</summary>

* To enable all-time leaderboards (override 60 minutes live results and 90 days personal records), create a file ``all_time_leaderboards.txt`` in the ``storage`` directory.
* Jerseys are still valid for 60 minutes but will be granted only when a new all-time record is set.
</details>

<details><summary>Entitlements</summary>

* To unlock entitlements (special equipment), create a file ``unlock_entitlements.txt`` in the ``storage`` directory.
* To unlock all equipment, create a file ``unlock_all_equipment.txt`` instead.
</details>

<details><summary>CDN proxy</summary>

* To obtain the official map schedule and update files from Zwift server: create a ``cdn-proxy.txt`` file in the ``storage`` directory. This can only work if you are running zoffline on a different machine than the Zwift client.
* By default, zoffline will try to proxy using Google public DNS to resolve Zwift host names, this should work even if zoffline is running on the same machine as the Zwift client. To avoid it, create a ``disable_proxy.txt`` file in the ``storage`` directory.
* If you want to serve update files from zoffline, run the script ``get_gameassets.py`` to download the game files.
</details>

<details><summary>Discord bridge</summary>

* The Discord bridge is only available if zoffline is running from source.
* Install discord.py: ``pip3 install discord.py``
* Create a ``discord.cfg`` file in the ``storage`` directory containing
  ```
  [discord]
  token = 
  webhook = 
  channel = 
  welcome_message = 
  help_message = 
  announce_players = 
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
* stravalib (https://stravalib.readthedocs.io/)
* OPTIONAL: garth (https://pypi.org/project/garth/)
* OPTIONAL: discord.py (https://discordpy.readthedocs.io/)


## Note

Future Zwift updates may break zoffline until it's updated. While zoffline is
enabled Zwift updates will not be installed. If a zoffline update broke
something, check the ``CHANGELOG`` for possible changes that need to be made.

Don't expose zoffline to the internet, it was not designed with that in mind.

<details><summary>If zoffline is out of date from Zwift's official client</summary>
If zoffline is behind in support of the latest Zwift client it can be updated to run using the latest Zwift version.

* Windows: copy ``C:\Program Files (x86)\Zwift\Zwift_ver_cur.xml`` to zoffline's ``cdn/gameassets/Zwift_Updates_Root/`` overwriting the existing file.
* macOS: copy ``~/Library/Application Support/Zwift/ZwiftMac_ver_cur.xml`` to zoffline's ``cdn/gameassets/Zwift_Updates_Root/`` overwriting the existing file.
* Linux: run [this script](https://gist.github.com/zoffline/b874e93e24439f0f4fbd7b55f3876fd2) from within the zwift-offline repository.

Note: there is no guarantee that an untested Zwift update will work with zoffline. However, historically, Zwift updates rarely break zoffline.

Alternatively, [this script](https://gist.github.com/oldnapalm/556c58448a6ee09438b39e1c1c9ce3d0) can be used to downgrade Zwift to the version supported by zoffline.
</details>

<details><summary>Zwift phased updates</summary>

If you install Zwift during a phased update period, when you enable zoffline it's possible that Zwift attempts to update again and fails.
To workaround this situation, rename the file ``Zwift_ver_cur.<version>.xml`` in Zwift directory to ``Zwift_ver_cur.xml`` and edit the file ``Zwift_ver_cur_filename.txt`` accordingly.
</details>


## Disclaimer

Zwift is a trademark of Zwift, Inc., which is not affiliated with the maker of
this project and does not endorse this project.

All product and company names are trademarks of their respective holders. Use of
them does not imply any affiliation with or endorsement by them.

