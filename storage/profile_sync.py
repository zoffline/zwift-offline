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

def sync_par_max(profile_zo, changed_zo, profile_ext, changed_ext, par):
    zo_val = jsf(profile_zo, par)
    ext_val = jsf(profile_ext, par)
    if (zo_val == ext_val):
        print ('SyncMax %s: eq %s' % (par, zo_val))
    else:
        if (zo_val > ext_val):
            print ('SyncMax %s: zo=%s > ext=%s' % (par, zo_val, ext_val))
            setattr(profile_ext, par, zo_val)
            changed_ext = True
        else:
            print ('SyncMax %s: zo=%s < ext=%s' % (par, zo_val, ext_val))
            setattr(profile_zo, par, ext_val)
            changed_zo = True
    return (changed_zo, changed_ext)

def sync_par_acc(profile_base, profile_zo, changed_zo, profile_ext, changed_ext, par):
    base_val = jsf(profile_base, par)
    zo_val = jsf(profile_zo, par)
    ext_val = jsf(profile_ext, par)
    if (zo_val == ext_val):
        print ('SyncAcc %s: eq %s' % (par, zo_val))
    else:
        dzo = zo_val - base_val
        dext = ext_val - base_val
        result = base_val + dzo + dext
        print ('SyncAcc %s: zo=%s dzo=%s ext=%s dext=%s result=%s' % (par, zo_val, dzo, ext_val, dext, result))
        if (result > ext_val):
            setattr(profile_ext, par, result)
            changed_ext = True
        if (result > zo_val):
            setattr(profile_zo, par, result)
            changed_zo = True
    return (changed_zo, changed_ext)

def do_sync(profile_base, profile_zo, profile_ext):
    changed_zo = False
    changed_ext = False
    for par in ('ftp','height_in_millimeters','max_heart_rate'):
        changed_zo, changed_ext = sync_par_max(profile_zo, changed_zo, profile_ext, changed_ext, par)
    for par in ('total_distance_in_meters','achievement_level','elevation_gain_in_meters','time_ridden_in_minutes','total_in_kom_jersey','total_in_sprinters_jersey','total_in_orange_jersey', 'total_watt_hours', 'total_xp','total_gold_drops'):
        changed_zo, changed_ext = sync_par_acc(profile_base, profile_zo, changed_zo, profile_ext, changed_ext, par)
    #todo:
    #optional bytes challenge_info = 33;
    return (changed_zo, changed_ext)

def sync(zo_uid, ext_uid, user, password):
    print("login: %s uids=%s/%s compare" % (user, zo_uid, ext_uid))
    session = requests.session()
    access_token, refresh_token = login(session, user, password)

    profile_zo = profile_pb2.PlayerProfile()
    profile_zo_file = '%s/profile.bin' % zo_uid
    with open(profile_zo_file, 'rb') as f:
        profile_zo.ParseFromString(f.read())

    profile_base = profile_pb2.PlayerProfile()
    profile_base_file = '../../zoffline-helper/%s/last_synced.bin' % ext_uid
    with open(profile_base_file, 'rb') as f:
        profile_base.ParseFromString(f.read())

    profile_ext = profile_pb2.PlayerProfile()
    profile_ext_bin = query_player_profile(session, access_token)
    with open('../../zoffline-helper/%s/rx-%s.bin' % (ext_uid, uuid.uuid4().hex), 'wb') as f:
        f.write(profile_ext_bin)
    profile_ext.ParseFromString(profile_ext_bin)

    changed_zo, changed_ext = do_sync(profile_base, profile_zo, profile_ext)

    if(changed_zo):
        with open(profile_zo_file, 'wb') as f:
            f.write(profile_zo.SerializeToString())

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
