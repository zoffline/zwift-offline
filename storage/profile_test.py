import sys
from typing import AbstractSet
sys.path.append('../')
sys.path.append('../protobuf')

import protobuf.profile_pb2 as profile_pb2
from flask import Flask, jsonify
from google.protobuf.json_format import MessageToDict

app = Flask(__name__)
profile = profile_pb2.Profile()
#profile_file = '../../zoffline-helper/profile.bin-sul'
#profile_file = '../../zoffline-helper/profile.bin'
#profile_file = '../storage/2/profile.bin'
#profile_file = '../storage/profile4357549.bin'
profile_file = '../storage/profile4485018.bin'
with open(profile_file, 'rb') as fd:
    profile.ParseFromString(fd.read())

def jsf(obj, field, deflt = None):
    if(obj.HasField(field)):
        return getattr(obj, field)
    return deflt

def jsb0(obj, field):
    return jsf(obj, field, False)

def jsb1(obj, field):
    return jsf(obj, field, True)

def jsv0(obj, field):
    return jsf(obj, field, 0)

def jses(obj, field):
    return str(jsf(obj, field))

def copyAttributes(jprofile, jprofileFull, src):
    dict = jprofileFull.get(src)
    if dict is None:
        return
    dest = {}
    for di in dict:
        for v in ['numberValue', 'floatValue', 'stringValue']:
            if v in di:
                dest[di['id']] = di[v]
    jprofile[src] = dest

def powerSourceModelToStr(val):
    if (val == 1):
        return "Power Meter"
    else:
        return "zPower"

def bikeFrameToStr(val):
    if (val == 0x7d8c357d):
        return "Zwift Carbon"
    else:
        if (val == -722210337):
            return "Zwift TT"
    return "---"

def privacy(profile):
    privacy_bits = jsf(profile, 'privacy_bits', 0)
    return {"approvalRequired": bool(privacy_bits & 1), "displayWeight": bool(privacy_bits & 4), "minor": bool(privacy_bits & 2), "privateMessaging": bool(privacy_bits & 8), "defaultFitnessDataPrivacy": bool(privacy_bits & 16), 
"suppressFollowerNotification": bool(privacy_bits & 32), "displayAge": not bool(privacy_bits & 64), "defaultActivityPrivacy": profile_pb2.Profile.ActivityPrivacyType.Name(jsv0(profile, 'default_activity_privacy'))}

jprofileFull = MessageToDict(profile)
if True:
    jprofile = {"id": profile.id, "firstName": jsf(profile, 'first_name'), "lastName": jsf(profile, 'last_name'), "preferredLanguage": jsf(profile, 'preferred_language'), "bodyType":jsv0(profile, 'body_type'), "male": jsb1(profile, 'is_male'), 
"imageSrc": "https://us-or-rly101.zwift.com/download/%s/avatarLarge.jpg" % profile.id, "imageSrcLarge": "https://us-or-rly101.zwift.com/download/%s/avatarLarge.jpg" % profile.id, "playerType": profile_pb2.Profile.PlayerType.Name(jsf(profile, 'player_type', 1)), "playerTypeId": jsf(profile, 'player_type', 1), "playerSubTypeId": None, 
"emailAddress": jsf(profile, 'email'), "countryCode": jsf(profile, 'country_code'), "dob": jsf(profile, 'dob'), "countryAlpha3": "rus", "useMetric": jsb1(profile, 'use_metric'), "privacy": privacy(profile), "age": jsv0(profile, 'age'), "ftp": jsf(profile, 'ftp'), "b": False, "weight": jsf(profile, 'weight_in_grams'), "connectedToStrava": jsb0(profile, 'connected_to_strava'), "connectedToTrainingPeaks": jsb0(profile, 'connected_to_training_peaks'),
"connectedToTodaysPlan": jsb0(profile, 'connected_to_todays_plan'), "connectedToUnderArmour": jsb0(profile, 'connected_to_under_armour'), "connectedToFitbit": jsb0(profile, 'connected_to_fitbit'), "connectedToGarmin": jsb0(profile, 'connected_to_garmin'), "height": jsf(profile, 'height_in_millimeters'), "location": "", 
"socialFacts": jprofileFull.get('socialFacts'), "totalExperiencePoints": jsv0(profile, 'total_xp'), "worldId": jsf(profile, 'world_id'), "totalDistance": jsv0(profile, 'total_distance_in_meters'), "totalDistanceClimbed": jsv0(profile, 'elevation_gain_in_meters'), "totalTimeInMinutes": jsv0(profile, 'time_ridden_in_minutes'), 
"achievementLevel": jsv0(profile, 'achievement_level'), "totalWattHours": jsv0(profile, 'total_watt_hours'), "runTime1miInSeconds": jsv0(profile, 'run_time_1mi_in_seconds'), "runTime5kmInSeconds": jsv0(profile, 'run_time_5km_in_seconds'), "runTime10kmInSeconds": jsv0(profile, 'run_time_10km_in_seconds'), 
"runTimeHalfMarathonInSeconds": jsv0(profile, 'run_time_half_marathon_in_seconds'), "runTimeFullMarathonInSeconds": jsv0(profile, 'run_time_full_marathon_in_seconds'), "totalInKomJersey": jsv0(profile, 'total_in_kom_jersey'), "totalInSprintersJersey": jsv0(profile, 'total_in_sprinters_jersey'), 
"totalInOrangeJersey": jsv0(profile, 'total_in_orange_jersey'), "currentActivityId": jsf(profile, 'current_activity_id'), "enrolledZwiftAcademy": jsv0(profile, 'enrolled_program') == profile.EnrolledProgram.ZWIFT_ACADEMY, "runAchievementLevel": jsv0(profile, 'run_achievement_level'), 
"totalRunDistance": jsv0(profile, 'total_run_distance'), "totalRunTimeInMinutes": jsv0(profile, 'total_run_time_in_minutes'), "totalRunExperiencePoints": jsv0(profile, 'total_run_experience_points'), "totalRunCalories": jsv0(profile, 'total_run_calories'), "totalGold": jsv0(profile, 'total_gold_drops'), 
"profilePropertyChanges": jprofileFull.get('propertyChanges'), "cyclingOrganization": jsf(profile, 'cycling_organization'), "userAgent": "CNL/3.13.0 (Android 11) zwift/1.0.85684 curl/7.78.0-DEV", "stravaPremium": jsb0(profile, 'strava_premium'), "profileChanges": False, "launchedGameClient": "09/19/2021 13:24:19 +0000", 
"createdOn":"2021-09-19T13:24:17.783+0000", "likelyInGame": False, "address": None, "bt":"f97803d3-efac-4510-a17a-ef44e65d3071", "numberOfFolloweesInCommon": 0, "fundraiserId": None, "source": "Android", "origin": None, "licenseNumber": None, "bigCommerceId": None, "marketingConsent": None, "affiliate": None, 
"avantlinkId": None, "virtualBikeModel": bikeFrameToStr(profile.bike_frame), "connectedToWithings": jsb0(profile, 'connected_to_withings'), "connectedToRuntastic": jsb0(profile, 'connected_to_runtastic'), "connectedToZwiftPower": False, "powerSourceType": "Power Source", "powerSourceModel": powerSourceModelToStr(profile.power_source_model), "riding": False, "location": "", "publicId": "5a72e9b1-239f-435e-8757-af9467336b40", 
"mixpanelDistinctId": "21304417-af2d-4c9b-8543-8ba7c0500e84"}

copyAttributes(jprofile, jprofileFull, 'publicAttributes')
copyAttributes(jprofile, jprofileFull, 'privateAttributes')

with app.app_context():
    print (jsonify(jprofile).data.decode("utf-8"))