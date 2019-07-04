#!/usr/bin/env python

import calendar
import datetime
import logging
import os
import random
import sqlite3
import time
from copy import copy
from datetime import timedelta
from io import BytesIO

from flask import Flask, request, jsonify, g, redirect
from google.protobuf.descriptor import FieldDescriptor
from protobuf_to_dict import protobuf_to_dict, TYPE_CALLABLE_MAP

import protobuf.activity_pb2 as activity_pb2
import protobuf.goal_pb2 as goal_pb2
import protobuf.login_response_pb2 as login_response_pb2
import protobuf.per_session_info_pb2 as per_session_info_pb2
import protobuf.periodic_info_pb2 as periodic_info_pb2
import protobuf.profile_pb2 as profile_pb2
import protobuf.segment_result_pb2 as segment_result_pb2
import protobuf.world_pb2 as world_pb2

# Android uses https for cdn
app = Flask(__name__, static_folder='cdn/gameassets', static_url_path='/gameassets')

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
STORAGE_DIR = "%s/storage" % SCRIPT_DIR
DATABASE_PATH = "%s/zwift-offline.db" % STORAGE_DIR
DATABASE_INIT_SQL = "%s/initialize_db.sql" % SCRIPT_DIR
DATABASE_CUR_VER = 0

# For auth server
AUTOLAUNCH_FILE = "%s/storage/auto_launch.txt" % SCRIPT_DIR
NOAUTO_EMBED = "http://cdn.zwift.com/static/web/launcher/embed-noauto.html"
from tokens import *

####
# Set up protobuf_to_dict call map
type_callable_map = copy(TYPE_CALLABLE_MAP)
# Override base64 encoding of byte fields
type_callable_map[FieldDescriptor.TYPE_BYTES] = str
# sqlite doesn't support uint64 so make them strings
type_callable_map[FieldDescriptor.TYPE_UINT64] = str


logger = logging.getLogger('zoffline')
logger.setLevel(logging.WARN)


def insert_protobuf_into_db(table_name, msg):
    cur = g.db.cursor()
    msg_dict = protobuf_to_dict(msg, type_callable_map=type_callable_map)
    columns = ', '.join(msg_dict.keys())
    placeholders = ':'+', :'.join(msg_dict.keys())
    query = 'INSERT INTO %s (%s) VALUES (%s)' % (table_name, columns, placeholders)
    cur.execute(query, msg_dict)
    g.db.commit()


# XXX: can't be used to 'nullify' a column value
def update_protobuf_in_db(table_name, msg, id):
    try:
        # If protobuf has an id field and it's uint64, make it a string
        id_field = msg.DESCRIPTOR.fields_by_name['id']
        if id_field.type == id_field.TYPE_UINT64:
            id = str(id)
    except AttributeError:
        pass
    cur = g.db.cursor()
    msg_dict = protobuf_to_dict(msg, type_callable_map=type_callable_map)
    columns = ', '.join(msg_dict.keys())
    placeholders = ':'+', :'.join(msg_dict.keys())
    setters = ', '.join('{}=:{}'.format(key, key) for key in msg_dict)
    query = 'UPDATE %s SET %s WHERE id=%s' % (table_name, setters, id)
    cur.execute(query, msg_dict)
    g.db.commit()


def row_to_protobuf(row, msg, exclude_fields=[]):
    for key in msg.DESCRIPTOR.fields_by_name.keys():
        if key in exclude_fields:
            continue
        if row[key] is None:
            continue
        field = msg.DESCRIPTOR.fields_by_name[key]
        if field.type == field.TYPE_UINT64:
            setattr(msg, key, int(row[key]))
        else:
            setattr(msg, key, row[key])
    return msg


# FIXME: I should really do this properly...
def get_id(table_name):
    cur = g.db.cursor()
    while True:
        # I think activity id is actually only uint32. On the off chance it's
        # int32, stick with 31 bits.
        ident = int(random.getrandbits(31))
        cur.execute("SELECT id FROM %s WHERE id = ?" % table_name, (str(ident),))
        if not cur.fetchall():
            break
    return ident


def world_time():
    return int(time.time()*64.4131403573055)


@app.route('/api/auth', methods=['GET'])
def api_auth():
    return '{"realm":"zwift","url":"https://secure.zwift.com/auth/"}'


@app.route('/api/users/login', methods=['POST'])
def api_users_login():
    response = login_response_pb2.LoginResponse()
    response.session_id = 'abc'
    return response.SerializeToString(), 200


@app.route('/api/users/logout', methods=['POST'])
def api_users_logout():
    return '', 204


@app.route('/api/analytics/event', methods=['POST'])
def api_analytics_event():
    return '', 200


@app.route('/api/per-session-info', methods=['GET'])
def api_per_session_info():
    info = per_session_info_pb2.PerSessionInfo()
    info.relay_url = "https://us-or-rly101.zwift.com/relay"
    return info.SerializeToString(), 200


@app.route('/api/events/search', methods=['POST'])
def api_events_search():
    return '', 200


# Probably don't need, haven't investigated
@app.route('/api/zfiles/list', methods=['POST'])
def api_zfiles_list():
    return '', 200


# Probably don't need, haven't investigated
@app.route('/api/private_event/feed', methods=['POST'])
def api_private_event_feed():
    return '', 200


@app.route('/api/profiles/me', methods=['GET'])
def api_profiles_me():
    profile_file = '%s/profile.bin' % STORAGE_DIR
    if not os.path.isfile(profile_file):
        profile = profile_pb2.Profile()
        profile.id = 1000
        profile.is_connected_to_strava = True
        return profile.SerializeToString(), 200
    with open(profile_file, 'rb') as fd:
        return fd.read()


# FIXME (not going to fix unless really bored): only supports 1 profile
@app.route('/api/profiles/<int:player_id>', methods=['PUT'])
def api_profiles_id(player_id):
    if not request.stream:
        return '', 400
    if not os.path.exists(STORAGE_DIR):
        os.makedirs(STORAGE_DIR)
    with open('%s/profile.bin' % STORAGE_DIR, 'wb') as f:
        f.write(request.stream.read())
    return '', 204


@app.route('/api/profiles/<int:player_id>/activities/', methods=['GET', 'POST'], strict_slashes=False)
def api_profiles_activities(player_id):
    if request.method == 'POST':
        if not request.stream:
            return '', 400
        activity = activity_pb2.Activity()
        activity.ParseFromString(request.stream.read())
        activity.id = get_id('activity')
        insert_protobuf_into_db('activity', activity)
        return '{"id": %ld}' % activity.id, 200

    # request.method == 'GET'
    activities = activity_pb2.Activities()
    cur = g.db.cursor()
    cur.execute("SELECT * FROM activity WHERE player_id = ?", (str(player_id),))
    for row in cur.fetchall():
        activity = activities.activities.add()
        row_to_protobuf(row, activity, exclude_fields=['fit'])

    return activities.SerializeToString(), 200


# With 64 bit ids Zwift can pass negative numbers due to overflow, which the flask int
# converter does not handle so it's a string argument
@app.route('/api/profiles/<int:player_id>/activities/<string:activity_id>', methods=['PUT'])
def api_profiles_activities_id(player_id, activity_id):
    if not request.stream:
        return '', 400
    activity_id = int(activity_id) & 0xffffffffffffffff
    activity = activity_pb2.Activity()
    activity.ParseFromString(request.stream.read())
    update_protobuf_in_db('activity', activity, activity_id)

    response = '{"id":%s}' % activity_id
    if request.args.get('upload-to-strava') != 'true':
        return response, 200
    try:
        from stravalib.client import Client
    except ImportError:
        logger.warn("stravalib is not installed. Skipping Strava upload attempt.")
        return response, 200
    strava = Client()
    try:
        with open('%s/strava_token.txt' % STORAGE_DIR, 'r') as f:
            strava.access_token = f.read().rstrip('\r\n')
    except:
        logger.warn("Failed to read %s/strava_token.txt. Skipping Strava upload attempt." % STORAGE_DIR)
        return response, 200
    try:
        # See if there's internet to upload to Strava
        strava.upload_activity(BytesIO(activity.fit), data_type='fit', name=activity.name)
        # XXX: assume the upload succeeds on strava's end. not checking on it.
    except:
        logger.warn("Strava upload failed. No internet?")
    return response, 200


@app.route('/api/profiles/<int:player_id>/followees', methods=['GET'])
def api_profiles_followees(player_id):
    return '', 200


def get_week_range(dt):
     d = datetime.datetime(dt.year,1,1)
     if (d.weekday()<= 3):
         d = d - timedelta(d.weekday())
     else:
         d = d + timedelta(7-d.weekday())
     dlt = timedelta(days = (int(dt.strftime('%W'))-1)*7)
     first = d + dlt
     last = d + dlt + timedelta(days=6, hours=23, minutes=59, seconds=59)
     return first, last

def get_month_range(dt):
     num_days = calendar.monthrange(dt.year, dt.month)[1]
     first = datetime.datetime(dt.year, dt.month, 1)
     last = datetime.datetime(dt.year, dt.month, num_days, 23, 59, 59)
     return first, last


def unix_time_millis(dt):
    return int(dt.strftime('%s')) * 1000


def fill_in_goal_progress(goal, player_id):
    cur = g.db.cursor()
    now = datetime.datetime.now()
    if goal.periodicity == 0:  # weekly
        first_dt, last_dt = get_week_range(now)
    else:  # monthly
        first_dt, last_dt = get_month_range(now)
    if goal.type == 0:  # distance
        cur.execute("""SELECT SUM(distance) FROM activity
                       WHERE player_id = ?
                       AND strftime('%s', start_date) >= strftime('%s', ?)
                       AND strftime('%s', start_date) <= strftime('%s', ?)
                       AND end_date IS NOT NULL""",
                       (str(player_id), first_dt, last_dt))
        distance = cur.fetchall()[0][0]
        if distance:
            goal.actual_distance = distance
            goal.actual_duration = distance
        else:
            goal.actual_distance = 0.0
            goal.actual_duration = 0.0

    else:  # duration
        cur.execute("""SELECT SUM(julianday(end_date) - julianday(start_date))
                       FROM activity
                       WHERE player_id = ?
                       AND strftime('%s', start_date) >= strftime('%s', ?)
                       AND strftime('%s', start_date) <= strftime('%s', ?)
                       AND end_date IS NOT NULL""",
                       (str(player_id), first_dt, last_dt))
        duration = cur.fetchall()[0][0]
        if duration:
            goal.actual_duration = duration*1440  # convert from days to minutes
            goal.actual_distance = duration*1440
        else:
            goal.actual_duration = 0.0
            goal.actual_distance = 0.0


def set_goal_end_date(goal, now):
    if goal.periodicity == 0:  # weekly
        goal.period_end_date = unix_time_millis(get_week_range(now)[1])
    else:  # monthly
        goal.period_end_date = unix_time_millis(get_month_range(now)[1])


@app.route('/api/profiles/<int:player_id>/goals', methods=['GET', 'POST'])
def api_profiles_goals(player_id):
    if request.method == 'POST':
        if not request.stream:
            return '', 400
        goal = goal_pb2.Goal()
        goal.ParseFromString(request.stream.read())
        goal.id = get_id('goal')
        now = datetime.datetime.now()
        goal.created_on = unix_time_millis(now)
        set_goal_end_date(goal, now)
        fill_in_goal_progress(goal, player_id)
        insert_protobuf_into_db('goal', goal)

        return goal.SerializeToString(), 200

    # request.method == 'GET'
    goals = goal_pb2.Goals()
    cur = g.db.cursor()
    cur.execute("SELECT * FROM goal WHERE player_id = ?", (str(player_id),))
    rows = cur.fetchall()
    for row in rows:
        goal = goals.goals.add()
        row_to_protobuf(row, goal)
        end_dt = datetime.datetime.fromtimestamp(goal.period_end_date / 1000)
        now = datetime.datetime.now()
        if end_dt < now:
            set_goal_end_date(goal, now)
            update_protobuf_in_db('goal', goal, goal.id)
        fill_in_goal_progress(goal, player_id)

    return goals.SerializeToString(), 200


@app.route('/api/profiles/<int:player_id>/goals/<string:goal_id>', methods=['DELETE'])
def api_profiles_goals_id(player_id, goal_id):
    goal_id = int(goal_id) & 0xffffffffffffffff
    cur = g.db.cursor()
    cur.execute("DELETE FROM goal WHERE id = ?", (str(goal_id),))
    g.db.commit()
    return '', 200


def relay_worlds_generic(world_id=None):
    # Android client also requests a JSON version
    if request.headers['Accept'] == 'application/json':
        world = { 'currentDateTime': int(time.time()),
                  'currentWorldTime': world_time(),
                  'friendsInWorld': [],
                  'mapId': 1,
                  'name': 'Public Watopia',
                  'playerCount': 0,
                  'worldId': 1
                }
        if world_id:
            world['mapId'] = world_id
            return jsonify(world)
        else:
            return jsonify([ world ])
    else:  # protobuf request
        worlds = world_pb2.Worlds()
        world = worlds.worlds.add()
        world.id = 1
        world.name = 'Public Watopia'
        world.f3 = 1
        # Windows client crashes if playerCount is 0
        world.f5 = 1  # playerCount
        world.world_time = world_time()
        world.real_time = int(time.time())
        if world_id:
            world.id = world_id
            return world.SerializeToString()
        else:
            return worlds.SerializeToString()


@app.route('/relay/worlds', methods=['GET'])
@app.route('/relay/dropin', methods=['GET'])
def relay_worlds():
    return relay_worlds_generic()


@app.route('/relay/worlds/<int:world_id>', methods=['GET'])
def relay_worlds_id(world_id):
    return relay_worlds_generic(world_id)


@app.route('/relay/worlds/<int:world_id>/join', methods=['POST'])
def relay_worlds_id_join(world_id):
    return '{"worldTime":%ld}' % world_time()


@app.route('/relay/worlds/<int:world_id>/my-hash-seeds', methods=['GET'])
def relay_worlds_my_hash_seeds(world_id):
    return '[{"expiryDate":196859639979,"seed1":-733221030,"seed2":-2142448243},{"expiryDate":196860425476,"seed1":1528095532,"seed2":-2078218472},{"expiryDate":196862212008,"seed1":1794747796,"seed2":-1901929955},{"expiryDate":196862637148,"seed1":-1411883466,"seed2":1171710140},{"expiryDate":196863874267,"seed1":670195825,"seed2":-317830991}]'


# XXX: relay/worlds/<id>/attributes not implemented. seems okay with a 404


@app.route('/relay/periodic-info', methods=['GET'])
def relay_periodic_info():
    # Use 127.0.0.1 as the game server and ignore log errors
    infos = periodic_info_pb2.PeriodicInfos()
    info = infos.infos.add()
    info.game_server_ip = '127.0.0.1'
    info.f2 = 3022
    info.f3 = 10
    info.f4 = 60
    info.f5 = 30
    info.f6 = 3
    return infos.SerializeToString(), 200


def handle_segment_results(request):
    if request.method == 'POST':
        if not request.stream:
            return '', 400
        result = segment_result_pb2.SegmentResult()
        result.ParseFromString(request.stream.read())
        result.id = get_id('segment_result')
        result.world_time = world_time()
        result.finish_time_str = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        result.f20 = 0
        insert_protobuf_into_db('segment_result', result)
        return '{"id": %ld}' % result.id, 200

    # request.method == GET
#    world_id = int(request.args.get('world_id'))
    player_id = request.args.get('player_id')
#    full = request.args.get('full') == 'true'
    # Require segment_id
    if not request.args.get('segment_id'):
        return '', 422
    segment_id = int(request.args.get('segment_id')) & 0xffffffffffffffff
    only_best = request.args.get('only-best') == 'true'
    from_date = request.args.get('from')
    to_date = request.args.get('to')

    results = segment_result_pb2.SegmentResults()
    results.world_id = 1
    results.segment_id = segment_id

    cur = g.db.cursor()
    where_stmt = "WHERE segment_id = ?"
    where_args = [str(segment_id)]
    if player_id:
        where_stmt += " AND player_id = ?"
        where_args.append(player_id)
    if from_date:
        where_stmt += " AND strftime('%s', finish_time_str) > strftime('%s', ?)"
        where_args.append(from_date)
    if to_date:
        where_stmt += " AND strftime('%s', finish_time_str) < strftime('%s', ?)"
        where_args.append(to_date)
    if only_best:
        where_stmt += " ORDER BY elapsed_ms LIMIT 1"
    cur.execute("SELECT * FROM segment_result %s" % where_stmt, where_args)
    for row in cur.fetchall():
        result = results.segment_results.add()
        row_to_protobuf(row, result, ['f3', 'f4', 'segment_id', 'event_subgroup_id', 'finish_time_str', 'f14', 'f17', 'f18'])

    return results.SerializeToString(), 200


@app.route('/relay/segment-results', methods=['GET'])
def relay_segment_results():
    return handle_segment_results(request)


@app.route('/api/segment-results', methods=['GET', 'POST'])
def api_segment_results():
    return handle_segment_results(request)


@app.route('/relay/worlds/<int:world_id>/leave', methods=['POST'])
def relay_worlds_leave(world_id):
    return '{"worldtime":%ld}' % world_time()


def connect_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.text_factory = str
    conn.row_factory = sqlite3.Row
    return conn


@app.before_request
def before_request():
    g.db = connect_db()


@app.teardown_request
def teardown_request(exception):
    if hasattr(g, 'db'):
        g.db.close()


@app.before_first_request
def init_database():
    # Nothing to do for now
    if not os.path.exists(DATABASE_PATH):
        conn = connect_db()
        cur = conn.cursor()
        # Create a new database
        with open(DATABASE_INIT_SQL, 'r') as f:
            cur.executescript(f.read())
            cur.execute('INSERT INTO version VALUES (?)', (DATABASE_CUR_VER,))
        conn.close()
    # Migrate database if necessary


####################
#
# Auth server (secure.zwift.com) routes below here
#
####################

@app.route('/auth/rb_bf03269xbi', methods=['POST'])
def auth_rb():
    return 'OK(Java)'


@app.route('/launcher', methods=['GET'])
@app.route('/auth/realms/zwift/protocol/openid-connect/auth', methods=['GET'])
@app.route('/auth/realms/zwift/login-actions/request/login', methods=['GET', 'POST'])
@app.route('/auth/realms/zwift/protocol/openid-connect/registrations', methods=['GET'])
@app.route('/auth/realms/zwift/login-actions/startriding', methods=['GET'])  # Unused as it's a direct redirect now from auth/login
@app.route('/auth/realms/zwift/tokens/login', methods=['GET'])  # Called by Mac, but not Windows
@app.route('/auth/realms/zwift/tokens/registrations', methods=['GET'])  # Called by Mac, but not Windows
@app.route('/ride', methods=['GET'])
def launch_zwift():
    if request.path != "/ride" and not os.path.exists(AUTOLAUNCH_FILE):
        return redirect(NOAUTO_EMBED, 302)
    else:
        return redirect("http://zwift/?code=zwift_refresh_token%s" % REFRESH_TOKEN, 302)


@app.route('/auth/realms/zwift/protocol/openid-connect/token', methods=['POST'])
def auth_realms_zwift_protocol_openid_connect_token():
    return FAKE_JWT, 200


# Called by Mac, but not Windows
@app.route('/auth/realms/zwift/tokens/access/codes', methods=['POST'])
def auth_realms_zwift_tokens_access_codes():
    return FAKE_JWT, 200


def run_standalone():
    app.run(ssl_context=('%s/ssl/cert-zwift-com.pem' % SCRIPT_DIR, '%s/ssl/key-zwift-com.pem' % SCRIPT_DIR),
            port=443,
            threaded=True,
            host='0.0.0.0')
#            debug=True, use_reload=False)


if __name__ == "__main__":
    run_standalone()
