# zoffline

zoffline enables the use of [Zwift](http://zwift.com) offline by acting as a partial implementation
of a Zwift server. Currently it's designed for only a single user and the UDP
game node is not implemented.

## Install

### Step 1: Install zoffline

The easiest way to install zoffline is through
[Docker](https://www.docker.com/). zoffline can either be installed on the same
machine as Zwift or another local machine.

* Install Docker
* Create the docker container with:<br>
  ``docker create --name zwift-offline -p 443:443 -p 80:80 -v </path/to/host/storage>:/usr/local/apache2/htdocs/zwift-offline/storage -e TZ=<timezone> zoffline/zoffline``
  * You can optionally exclude ``-v </path/to/host/storage>:/usr/local/apache2/htdocs/zwift-offline/storage`` if you don't care if zoffline data is persistent across zoffline updates.
  * The path you pass to ``-v`` will likely need to be world readable and writable.
  * A list of valid ``<timezone>`` values (e.g. America/New_York) can be found [here](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).
  * Adding ``--restart unless-stopped`` will make zoffline start on boot if you have Docker v1.9.0 or greater.
* Start zoffline with:
  ``docker start zwift-offline``

If you don't use the Docker container you will need to set up an Apache server (or
write your own nginx/uWSGI configuration and use nginx) and install the
dependencies listed below. The necessary Apache configuration is inside the
``apache`` subdir. You'll also need to run ``make`` inside the ``protobuf``
subdirectory.


### Step 2: Configure Zwift client to use zoffline

<details><summary>Windows 10 Instructions</summary>

* Install Zwift
  * If your Zwift version is newer than 1.0.30362 you may have to uninstall, then reinstall after installing zoffline.
  * If your Zwift version is 1.0.30362, you're all set.
  * If Zwift is not installed install it after installing zoffline (1.0.30362 will be installed instead of the latest).
* On your Windows machine running Zwift, copy the following files in this repo to a known location:
  * ``ssl/cert-us-or.p12``
  * ``ssl/cert-secure-zwift.p12``
  * ``ssl/cert-us-or.pem``
  * ``ssl/cert-secure-zwift.pem``
* Open Command Prompt as an admin, cd to that location and run
  * ``certutil.exe -importpfx Root cert-us-or.p12``
  * ``certutil.exe -importpfx Root cert-secure-zwift.p12``
* Open Notepad as an admin and open ``C:\Program Files (x86)\Zwift\data\cacert.pem``
  * Append the contents of ``ssl/cert-us-or.pem`` to cacert.pem
  * Append the contents of ``ssl/cert-secure-zwift.pem`` to cacert.pem
* Open Notepad as an admin and open ``C:\Windows\System32\Drivers\etc\hosts``
  * Append this line: ``<zoffline ip> us-or-rly101.zwift.com secure.zwift.com cdn.zwift.com``
    <br />(Where ``<zoffline ip>`` is the ip address of the machine running zoffline. If
    it's running on the same machine as Zwift, use ``127.0.0.1`` as the ip.)

Why: We need to redirect Zwift to use zoffline and convince Windows and Zwift to
accept zoffline's self signed certificates for Zwift's domain names. Feel free
to generate your own certificates and do the same.

</details>

<details><summary>Mac OS X Instructions (Thanks @oldnapalm!)</summary>

* Install Zwift
  * If your Zwift version is newer than 1.0.30362 you may have to uninstall, then reinstall after installing zoffline.
  * If your Zwift version is 1.0.30362, you're all set.
  * If Zwift is not installed install it after installing zoffline (1.0.30362 will be installed instead of the latest).
* On your Mac machine running Zwift, copy the following files in this repo to a known location:
  * ``ssl/cert-us-or.p12``
  * ``ssl/cert-secure-zwift.p12``
  * ``ssl/cert-us-or.pem``
  * ``ssl/cert-secure-zwift.pem``
* Open Keychain Access, select "System" under "Keychains", select "Certificates" under "Category"
    * Click "File - Import Items..." and import ``ssl/cert-secure-zwift.p12``
    * Right click "secure.zwift.com", select "Get Info" and under "Trust" choose "When using this certificate: Always Trust".
    * Repeat this procedure with ``ssl/cert-us-or.p12`` ("us-or-rly101.zwift.com").
* Using a text editor open ``~/Library/Application Support/Zwift/data/cacert.pem``
  * Append the contents of ``ssl/cert-us-or.pem`` to cacert.pem
  * Append the contents of ``ssl/cert-secure-zwift.pem`` to cacert.pem
* Using a text editor (with admin privileges) open ``/etc/hosts``
  * Append this line: ``<zoffline ip> us-or-rly101.zwift.com secure.zwift.com cdn.zwift.com``
    <br />(Where ``<zoffline ip>`` is the ip address of the machine running zoffline. If
    it's running on the same machine as Zwift, use ``127.0.0.1`` as the ip.)

Why: We need to redirect Zwift to use zoffline and convince OS X and Zwift to
accept zoffline's self signed certificates for Zwift's domain names. Feel free
to generate your own certificates and do the same.

</details>


#### Enabling/Disabling zoffline

To use Zwift online like normal, comment out or remove the line added to the ``hosts``
file before starting Zwift.


### Step 3 [OPTIONAL]: Obtain current Zwift profile

If you don't obtain your current Zwift profile before first starting Zwift with
zoffline enabled, you will be prompted to create a new profile (name, weight,
height, etc.)

To obtain your current profile:
* Run ``scripts/get_profile.py -u <your_zwift_username>``
* Move the resulting profile.bin (saved in whatever directory you ran get_profile.py in) into the ``storage`` directory.
  * If using Docker, move profile.bin into the path you passed to ``-v``


## Dependencies

Docker

-or-

* protobuf compiler
  * ``apt-get install protobuf-compiler`` (on Debian/Ubuntu)
* GNU Make
  * ``apt-get install make`` (on Debian/Ubuntu)
* python-protobuf
  * ``pip install python-protobuf``
* protobuf_to_dict (https://github.com/benhodgson/protobuf-to-dict)
  * ``pip install protobuf_to_dict``
* OPTIONAL: stravalib (https://github.com/hozn/stravalib)
  * ``pip install stravalib``
  * Add your Strava API token to ``storage/strava_token.txt``


## Known issues

* Segment results always show up as having just occurred.


## Note

Future Zwift updates may break zoffline until it's updated. While zoffline is
enabled Zwift updates will not be installed.

Don't expose zoffline to the internet, it was not designed with that in mind.


## Disclaimer

Zwift is a trademark of Zwift, Inc., which is not affiliated with the maker of
this project and does not endorse this project.

All product and company names are trademarks of their respective holders. Use of
them does not imply any affiliation with or endorsement by them.
