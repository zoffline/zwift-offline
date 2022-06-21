#!/usr/bin/env python

#
# Adapted from https://github.com/jlemon/zlogger/blob/master/get_riders.py
#
# The MIT License (MIT)
#
# Copyright (c) 2016 Jonathan Lemon
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NON INFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import argparse
import getpass
import json
import os
import requests
import sys
sys.path.append(os.path.join(sys.path[0], 'protobuf')) # otherwise import in .proto does not work
import activity_pb2
import profile_pb2

try:
    input = raw_input
except NameError:
    pass

global args


def post_credentials(session, username, password):
    # Credentials POSTing and tokens retrieval
    # POST https://secure.zwift.com/auth/realms/zwift/tokens/access/codes

    try:
        response = session.post(
            url="https://secure.zwift.com/auth/realms/zwift/tokens/access/codes",
            headers={
                "Accept": "*/*",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Content-Type": "application/x-www-form-urlencoded",
                "Host": "secure.zwift.com",
                "User-Agent": "Zwift/1.5 (iPhone; iOS 9.0.2; Scale/2.00)",
                "Accept-Language": "en-US;q=1",
            },
            data={
                "client_id": "Zwift_Mobile_Link",
                "username": username,
                "password": password,
                "grant_type": "password",
            },
            allow_redirects=False,
            verify=args.verifyCert,
        )

        if args.verbose:
            print('Response HTTP Status Code: {status_code}'.format(
                status_code=response.status_code))
            print('Response HTTP Response Body: {content}'.format(
                content=response.content))

        json_dict = json.loads(response.content)

        return (json_dict["access_token"], json_dict["refresh_token"], json_dict["expires_in"])

    except requests.exceptions.RequestException as e:
        print('HTTP Request failed: %s' % e)

    except KeyError as e:
        print('Invalid uname and/or password')
        sys.exit()


def upload_activity(session, access_token, activity):
    try:
        response = session.put(
            url="https://us-or-rly101.zwift.com/api/profiles/%s/activities/%s" % (activity.player_id, activity.id),
            headers={
                "Content-Type": "application/x-protobuf-lite",
                "Accept": "application/json",
                "Connection": "keep-alive",
                "Host": "us-or-rly101.zwift.com",
                "User-Agent": "Zwift/115 CFNetwork/758.0.2 Darwin/15.0.0",
                "Authorization": "Bearer %s" % access_token,
                "Accept-Language": "en-us",
            },
            data=activity.SerializeToString(),
            verify=args.verifyCert,
        )

        if args.verbose:
            print('Response HTTP Status Code: {status_code}'.format(
                status_code=response.status_code))

        return response.content

    except requests.exceptions.RequestException as e:
        print('HTTP Request failed: %s' % e)


def get_player_id(session, access_token):
    try:
        response = session.get(
            url="https://us-or-rly101.zwift.com/api/profiles/me",
            headers={
                "Accept-Encoding": "gzip, deflate",
                "Accept": "application/x-protobuf-lite",
                "Connection": "keep-alive",
                "Host": "us-or-rly101.zwift.com",
                "User-Agent": "Zwift/115 CFNetwork/758.0.2 Darwin/15.0.0",
                "Authorization": "Bearer %s" % access_token,
                "Accept-Language": "en-us",
            },
            verify=args.verifyCert,
        )

        if args.verbose:
            print('Response HTTP Status Code: {status_code}'.format(
                status_code=response.status_code))

        profile = profile_pb2.PlayerProfile()
        profile.ParseFromString(response.content)
        return profile.id

    except requests.exceptions.RequestException as e:
        print('HTTP Request failed: %s' % e)


def logout(session, refresh_token):
    # Logout
    # POST https://secure.zwift.com/auth/realms/zwift/tokens/logout
    try:
        response = session.post(
            url="https://secure.zwift.com/auth/realms/zwift/tokens/logout",
            headers={
                "Accept": "*/*",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Content-Type": "application/x-www-form-urlencoded",
                "Host": "secure.zwift.com",
                "User-Agent": "Zwift/1.5 (iPhone; iOS 9.0.2; Scale/2.00)",
                "Accept-Language": "en-US;q=1",
            },
            data={
                "client_id": "Zwift_Mobile_Link",
                "refresh_token": refresh_token,
            },
            verify=args.verifyCert,
        )
        if args.verbose:
            print('Response HTTP Status Code: {status_code}'.format(
                status_code=response.status_code))
            print('Response HTTP Response Body: {content}'.format(
                content=response.content))
    except requests.exceptions.RequestException as e:
        print('HTTP Request failed: %s' % e)


def login(session, user, password):
    access_token, refresh_token, expired_in = post_credentials(session, user, password)
    return access_token, refresh_token


def main(argv):
    global args

    access_token = None
    cookies = None

    print('WARNING: remove zoffline IP from hosts file before running this script')

    parser = argparse.ArgumentParser(description='Zwift activity uploader')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Verbose output')
    parser.add_argument('--dont-check-certificates', action='store_false',
                        dest='verifyCert', default=True)
    parser.add_argument('-u', '--user', help='Zwift user name')
    parser.add_argument('-a', '--activity', help='Activity file')
    args = parser.parse_args()

    activity = activity_pb2.Activity()
    if args.activity:
        activity_file = args.activity
    else:
        activity_file = input("Enter activity file: ")
    if not os.path.isfile(activity_file):
        print('Activity file not found')
        sys.exit()
    with open(activity_file, 'rb') as fd:
        try:
            activity.ParseFromString(fd.read())
        except:
            print('Could not parse activity file')
            sys.exit()

    if args.user:
        username = args.user
    else:
        username = input("Enter Zwift login (e-mail): ")

    if not sys.stdin.isatty():  # This terminal cannot support input without displaying text
        print('*WARNING* The current shell (%s) cannot support hidden text entry.' % os.name)
        print('Your password entry WILL BE VISIBLE.')
        print('If you are running a bash shell under windows, try executing this program via winpty:')
        print('>winpty python %s' % argv[0])
        password = input("Enter password (will be shown):")
    else:
        password = getpass.getpass("Enter password: ")

    session = requests.session()
    access_token, refresh_token = login(session, username, password)
    activity.player_id = get_player_id(session, access_token)
    ret = upload_activity(session, access_token, activity)
    print(ret)
    logout(session, refresh_token)


if __name__ == '__main__':
    try:
        main(sys.argv)
    except KeyboardInterrupt:
        pass
