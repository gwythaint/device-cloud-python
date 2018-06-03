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
Simple app that demonstrates the location APIs in the HDC Python library
"""

import argparse
import errno
import math
import random
import signal
import sys
import os
import psutil
from time import sleep

head, tail = os.path.split(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, head)

import device_cloud as iot

running = True

# Return status once the cloud responds
cloud_response = False

# Second intervals between telemetry
TELEMINTERVAL = 10

def sighandler(signum, frame):
    """
    Signal handler for exiting app
    """
    global running
    if signum == signal.SIGINT:
        print("Received SIGINT, stopping application...")
        running = False

def cpu_time(client, params, user_data, request):
    message = None
    message = psutil.cpu_percent()
    return (iot.STATUS_SUCCESS, message)

def toggle_loc():
    """
    Turns Location on or off (callback)
    """
    global sending_location
    sending_location = not sending_location
    client.info("%s sending location", "Now" if sending_location \
                else "No longer")
    return (iot.STATUS_SUCCESS, "Turned On" if sending_location \
            else "Turned Off")

def quit_me():
    """
    Quits application (callback)
    """
    global running
    running = False
    return (iot.STATUS_SUCCESS, "")

if __name__ == "__main__":
    signal.signal(signal.SIGINT, sighandler)

    # Parse command line arguments for easy customization
    parser = argparse.ArgumentParser(description="Demo app for Python HDC "
                                     "location APIs")
    parser.add_argument("-i", "--app_id", help="Custom app id")
    parser.add_argument("-c", "--config_dir", help="Custom config directory")
    parser.add_argument("-f", "--config_file", help="Custom config file name "
                        "(in config directory)")
    args = parser.parse_args(sys.argv[1:])

    # Initialize client default called 'python-demo-app'
    app_id = "iot-sysmon-py"
    if args.app_id:
        app_id = args.app_id
    client = iot.Client(app_id)

    # Use the demo-connect.cfg file inside the config directory
    # (Default would be python-demo-app-connect.cfg)
    config_file = "demo-iot-sysmon.cfg"
    if args.config_file:
        config_file = args.config_file
    client.config.config_file = config_file

    # Look for device_id and demo-connect.cfg in this directory
    # (This is already default behaviour)
    config_dir = "."
    if args.config_dir:
        config_dir = args.config_dir
    client.config.config_dir = config_dir

    # Finish configuration and initialize client
    client.initialize()

    # Set action callbacks
    # client.action_register_callback("toggle_location", toggle_loc)
    client.action_register_callback("quit", quit_me)
    client.action_register_callback("cpu_time", cpu_time)

    # Telemetry names (properties for numbers, attributes for strings)
    properties = ["property-1"]
    net_io_counters = ["property-2", "property-3", "property-4", "property-5", "property-6", "property-7","property-8", "property-9"]
    disk_usage = ['property-10']

    # Connect to Cloud
    if client.connect(timeout=10) != iot.STATUS_SUCCESS:
        client.error("Failed")
        sys.exit(1)

    counter = 0
    while running and client.is_alive():
        counter += 1
        if counter >= TELEMINTERVAL:
            net_io_values = psutil.net_io_counters()
            net_io_index = 0
            for p in properties:
                value = psutil.cpu_percent()
                status = client.telemetry_publish(p, value, cloud_response)
            for p in net_io_counters:
                value = net_io_values[net_io_index]
                net_io_index += 1
                status = client.telemetry_publish(p, value, cloud_response)
            for p in disk_usage:
                # first partition only for now
                partitions = psutil.disk_partitions()
                for part in partitions:
                    usage = psutil.disk_usage(part.mountpoint)
                    value = usage.percent
                status = client.telemetry_publish(p, value, cloud_response)
            counter = 0

        # Wrap sleep with an exception handler to fix SIGINT handling on Windows
        try:
            sleep(1)
        except IOError as err:
            if err.errno != errno.EINTR:
                raise

    client.disconnect(wait_for_replies=True)

