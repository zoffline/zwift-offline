#!/usr/bin/env python

import os
import time
from flask import Flask, request, jsonify, redirect

app = Flask(__name__)

FAKE_TOKEN = '{"access_token":"abc","expires_in":10800,"refresh_expires_in":2592000,"refresh_token":"abc","token_type":"bearer","id_token":"abc","not-before-policy":1408458483,"session-state":"a-b-c"}'


@app.route('/auth/rb_bf03269xbi', methods=['POST'])
def api_auth():
    return 'OK(Java)'


@app.route('/auth/realms/zwift/protocol/openid-connect/auth', methods=['GET'])
def auth_realms_zwift_protocol_openid_connect_auth():
    return redirect("http://zwift/?code=abc", 302)


@app.route('/auth/realms/zwift/login-actions/request/login', methods=['GET', 'POST'])
def auth_realms_zwift_login_actions_request_login():
    return redirect("http://zwift/?code=abc", 302)


@app.route('/auth/realms/zwift/protocol/openid-connect/registrations', methods=['GET'])
def auth_realms_zwift_protocol_openid_connect_registrations():
    return redirect("http://zwift/?code=abc", 302)


#@app.route('/auth/realms/zwift/protocol/openid-connect/logout', methods=['GET'])
#def auth_realms_zwift_protocol_openid_connect_logout():
#    return redirect("https://secure.zwift.com/auth/realms/zwift/protocol/openid-connect/auth?client_id=Game_Launcher&response_type=code&redirect_uri=http://zwift/", code=302)


# Unused as it's a direct redirect now from auth/login
@app.route('/auth/realms/zwift/login-actions/startriding', methods=['GET'])
def auth_realms_zwift_login_actions_startriding():
    return redirect("http://zwift/?code=abc", 302)

@app.route('/auth/realms/zwift/protocol/openid-connect/token', methods=['POST'])
def auth_realms_zwift_protocol_openid_connect_token():
    return FAKE_TOKEN, 200

# Called by Mac, but not Windows
@app.route('/auth/realms/zwift/tokens/login', methods=['GET'])
def auth_realms_zwift_tokens_login():
    return redirect("http://zwift/?code=abc", 302)

# Called by Mac, but not Windows
@app.route('/launcher', methods=['GET'])
def launcher():
    return redirect("http://zwift/?code=abc", 302)

# Called by Mac, but not Windows
@app.route('/auth/realms/zwift/tokens/access/codes', methods=['POST'])
def auth_realms_zwift_tokens_access_codes():
    return FAKE_TOKEN, 200

if __name__ == "__main__":
    app.run(ssl_context=('ssl/cert-secure-zwift.pem', 'ssl/key-secure-zwift.pem'),
            port=9000,
            host='0.0.0.0',
            debug=True)
