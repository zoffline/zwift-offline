#!/usr/bin/python
import os
import sys
import logging
logging.basicConfig(stream=sys.stderr)
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from zwift_offline import app as application
application.debug = True
