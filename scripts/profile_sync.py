#!/usr/bin/env python
import json
import os
import requests
import sys
sys.path.append('../')
import protobuf.profile_pb2 as profile_pb2
import uuid

def post_credentials(session, username, password):
    # Credentials POSTing and tokens retrieval
    # POST https://secure.zwift.com/auth/realms/zwift/tokens/access/codes

    try:
        response = session.post(
            url="https://secure.zwift.com/auth/realms/zwift/protocol/openid-connect/token",
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
            verify=True,
        )

        if response.status_code != 200:
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
        exit(-1)

def query_player_profile(session, access_token):
    # Query Player Profile
    # GET https://us-or-rly101.zwift.com/api/profiles/<player_id>
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
            verify=True,
        )

        if response.status_code != 200:
            print('Response HTTP Status Code: {status_code}'.format(
                status_code=response.status_code))

        return response.content

    except requests.exceptions.RequestException as e:
        print('HTTP Request failed: %s' % e)

def put_player_profile(session, access_token, f, player_id):
    # put Player Profile
    # PUT https://us-or-rly101.zwift.com/api/profiles/<player_id>
    try:
        response = session.put(
            data=f,
            url="https://us-or-rly101.zwift.com/api/profiles/%s" % player_id,
            headers={
                "Accept-Encoding": "gzip",
                "Accept": "*/*",
                "Connection": "keep-alive",
                "Host": "us-or-rly101.zwift.com",
                "User-Agent": "CNL/3.15.0 (Windows 10; Windows 10.0.19042) zwift/1.0.100278 curl/7.78.0-DEV",
                "Authorization": "Bearer %s" % access_token,
                "Content-type": "application/x-protobuf-lite",
                'Source': 'Game Client',
                'Platform': 'PC',
                'X-Machine-Id': '1-e9315b63-55cf-4097-bc57-fe8a4c44f93f', 
                'X-Zwift-Session-Id': '4cc84f11-d391-4ba3-b3ee-c90a88684637',
                'X-Request-Id': '18244', 
            },
            verify=True,
        )

        #print(response.__dict__)
        return response.content

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
            verify=True,
        )
        if response.status_code != 204:
            print('Response HTTP Status Code: {status_code}'.format(
                status_code=response.status_code))
            print('Response HTTP Response Body: {content}'.format(
                content=response.content))
    except requests.exceptions.RequestException as e:
        print('HTTP Request failed: %s' % e)

def login(session, user, password):
    access_token, refresh_token, expired_in = post_credentials(session, user, password)
    return access_token, refresh_token

def jsf(obj, field, deflt = 0):
    if(obj.HasField(field)):
        return getattr(obj, field)
    return deflt

def sync_par(profile_zo, changed_zo, profile_ext, changed_ext, par):
    print('Syncing %s:' % par)
    zo_val = jsf(profile_zo, par)
    ext_val = jsf(profile_ext, par)
    if (zo_val == ext_val):
        #print (' eq %s\n' % zo_val)
        pass
    else:
        if (zo_val > ext_val):
            print ('zo=%s > ext=%s\n' % (zo_val, ext_val))
            setattr(profile_ext, par, zo_val)
            changed_ext = True
        else:
            print ('zo=%s < ext=%s\n' % (zo_val, ext_val))
            setattr(profile_zo, par, ext_val)
            changed_zo = True
    return (changed_zo, changed_ext)

def do_sync(profile_zo, profile_ext):
    changed_zo = False
    changed_ext = False
    for par in ('ftp','total_distance_in_meters','elevation_gain_in_meters','time_ridden_in_minutes','total_in_kom_jersey','total_in_sprinters_jersey','total_in_orange_jersey', 'total_watt_hours', 'height_in_millimeters', 'max_heart_rate', 'total_xp','total_gold_drops','achievement_level'):
        changed_zo, changed_ext = sync_par(profile_zo, changed_zo, profile_ext, changed_ext, par)
    #todo:
    #optional bytes challenge_info = 33;
    return (changed_zo, changed_ext)

def sync(zo_uid, ext_uid, user, password):
    print("login: %s uids=%s/%s compare" % (user, zo_uid, ext_uid))
    session = requests.session()
    access_token, refresh_token = login(session, user, password)

    profile_zo = profile_pb2.Profile()
    profile_zo_file = '%s/profile.bin' % zo_uid
    with open(profile_zo_file, 'rb') as fd:
        profile_zo.ParseFromString(fd.read())

    profile_ext = profile_pb2.Profile()
    profile_ext_bin = query_player_profile(session, access_token)
    with open('../../zoffline-helper/%s/rx-%s.bin' % (ext_uid, uuid.uuid4().hex), 'wb') as f:
        f.write(profile_ext_bin)
    profile_ext.ParseFromString(profile_ext_bin)

    changed_zo, changed_ext = do_sync(profile_zo, profile_ext)

    if(changed_zo):
        with open(profile_zo_file, 'wb') as f:
            f.write(profile_zo)
    profile_ext_file = '../../zoffline-helper/%s/tx-%s.bin' % (ext_uid, uuid.uuid4().hex)
    with open(profile_ext_file, 'wb') as f:
        f.write(profile_ext.SerializeToString())
    if(changed_ext):
        with open(profile_ext_file, 'rb') as f:
            put_player_profile(session, access_token, f, ext_uid)
    logout(session, refresh_token)

def main(argv):
    with open('sync_creds.json', 'r') as f:
        sync_creds = json.load(f)
        for sync_cred in sync_creds:
            sync(sync_cred['zo_uid'], sync_cred['ext_uid'], sync_cred['user'], sync_cred['password'])

if __name__ == '__main__':
    try:
        main(sys.argv)
    except KeyboardInterrupt:
        pass
    except SystemExit as se:
        print("ERROR:", se)
