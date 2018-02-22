#!/usr/bin/env python

'''
    Copyright (c) 2018 Wind River Systems, Inc.
    
    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at:
    http://www.apache.org/licenses/LICENSE-2.0
    
    Unless required by applicable law or agreed to in writing, software  distributed
    under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES
    OR CONDITIONS OF ANY KIND, either express or implied.
'''

"""
Offline OTA handler.  The use case for this script is to support
instances where the OTA package is available locally and a technician
is sitting infront of the device and manually triggering the software
update process.  The requirements are:
  * No network access.
  * The ota package exists in the default location.
  * This utility script is run with the typical parameters plus an
  offline=True parameter.
  * The ota_handler.py will be instantiated and all packages
  installed.
  * A log file will be created with the debug stdout/err details.
  * Must be run from the directory containing the iot-connect.cfg file.
"""
import os, sys, argparse, json

from device_cloud import ota_handler
import device_cloud as iot

parser = argparse.ArgumentParser(description="Offline OTA Utility")
parser.add_argument("-r", "--runtime_dir", help="Runtime directory with download/<package name>")
parser.add_argument("-p", "--package_name", help="Name of the OTA package")
args = parser.parse_args(sys.argv[1:])

def gen_fake_config(file_name):
    config = {"cloud":{}}
    config["cloud"]["host"] = "fake.net"
    config["cloud"]["port"] = 8888
    config["cloud"]["token"] = "1234567890abcdef"
    config["qos_level"] = 1
    config["validate_cloud_cert"] = True
    with open(file_name, "w+b") as config_file:
        config_file.write(json.dumps(config, indent=2, sort_keys=True).encode())

if args.runtime_dir and os.path.isdir(args.runtime_dir):
    if args.package_name and os.path.isfile(os.path.join(args.runtime_dir,"download", args.package_name)):
        app_name = "offline_ota_handler"
        file_name = app_name + ".cfg"
        gen_fake_config(file_name)

        # action args
        params = {}
        params['ota_timeout'] = 0
        params['package'] = args.package_name
        user_data = [args.runtime_dir,]
        request = iot._core.defs.ActionRequest(request_id='unused', name='offline_updater', params=params)

        # client object
        client = iot.Client(app_name, offline=True)
        client.config.config_file = file_name
        client.initialize()
        client.log_level("DEBUG")

        ota = ota_handler.OTAHandler(offline=True)
        ota._runtime_dir = args.runtime_dir
        ota._offline = True
        ret = ota.update_callback(client, params, user_data, request)
        print("Status of update: {}".format(ret))
        try:
            os.remove(file_name)
        except:
            print("Unable to remove config file")
    else:
        print("package_name {} does not exist".format(args.package_name))
else:
    print("runtime_dir {} does not exist".format(args.runtime_dir))
