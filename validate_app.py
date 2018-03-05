#!/usr/bin/env python

'''
    Copyright (c) 2016-2017 Wind River Systems, Inc.

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at:
    http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software  distributed
    under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES
    OR CONDITIONS OF ANY KIND, either express or implied.
'''

"""
Simple app that validates the capabilities of the host machine to run an IOT
application.
"""

import errno
import device_cloud
import os
import signal
import sys
from time import sleep

if "VALIDATE_COVERAGE" in os.environ:
    import coverage
    enable_cov = True
else:
    enable_cov = False

if sys.version_info.major == 2:
    input = raw_input

running = True


def sighandler(signum, frame):
    """
    Signal handler for exiting app
    """
    global running
    if signum == signal.SIGINT:
        print("Received SIGINT, stopping application...")
        running = False

def quit_app():
    """
    Quits application (callback)
    """
    global running
    running = False
    return 0

def pass_action(client, params, user_data):
    if params and params["param"] == "value":
        return 0
    else:
        return 18

def fail_action(client, params, user_data):
    return (19, "fail and such")

def file_download(client, params):
    """
    file_download callback
    """
    return client.file_download(params.get("file_name"), os.path.dirname(os.path.abspath(__file__)))

def file_upload(client, params):
    """
    file_upload callback
    """
    return client.file_upload(os.path.abspath(__file__), upload_name=params.get("file_name"))

if __name__ == "__main__":
    signal.signal(signal.SIGINT, sighandler)

    if enable_cov == True:
        cov = coverage.Coverage()
        cov.start()

    client = device_cloud.Client("iot-validate-app")
    client.config.config_file = "validate.cfg"

    client.initialize()

    client.action_register_callback("quit_app", quit_app)
    client.action_register_callback("pass_action", pass_action)
    client.action_register_callback("fail_action", fail_action)
    client.action_register_callback("file_download", file_download)
    client.action_register_callback("file_upload", file_upload)

    if client.connect(timeout=10) != device_cloud.STATUS_SUCCESS:
        print("Failed to connect")
        sys.exit(1)

    client.telemetry_publish("property", 12.34)
    client.attribute_publish("attribute", "text and such")
    client.location_publish(45.351603, -75.918713, heading=12.34, altitude=1.0,
                            speed=2.0, accuracy=3.0, fix_type="crystal ball")
    client.event_publish("logs and such")

    # publish a bunch of these with the republish flag
    client.alarm_publish("test_alarm", 1, "very serious alarm", republish=True)
    client.alarm_publish("test_alarm", 1, "very serious alarm", republish=True)
    client.alarm_publish("test_alarm", 1, "very serious alarm", republish=True)
    client.alarm_publish("test_alarm", 1, "very serious alarm", republish=True)
    client.alarm_publish("test_alarm", 1, "very serious alarm", republish=True)

    client.file_upload(os.path.abspath(__file__), upload_name="validate_upload.txt",
                       blocking=True, timeout=30)

    client.file_download("validate_upload.txt",
                         os.path.abspath("validate_download.txt"),
                         blocking=True, timeout=30)

    input("Hit enter to exit:")

    client.disconnect()

    if os.path.exists(client.config.config_file):
        os.remove(client.config.config_file)

    if enable_cov == True:
        cov.stop()
        cov.save()
        cov.html_report(omit="/usr/local/lib/*")

    sys.exit(0)
