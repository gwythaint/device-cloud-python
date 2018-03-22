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
A script that executes an device manager default actions and
validates:
  * attributes
  * default actions that are possible:
    * file_download
    * file_upload
    * ping
    * quit
    * software update

"""

import getpass
import json
import os
import requests
import subprocess
import sys
import time
import platform
import uuid

from datetime import datetime

from device_cloud._core import constants
if sys.version_info.major == 2:
    input = raw_input

app_file = "device_manager.py"
client_id = "device_manager_py"
cloud = ""
validate_app = None
pycommand = "python"
debug = None

if sys.version_info.major == 3 and sys.platform.startswith("linux"):
    pycommand = "python3"

def _send(data, session_id=None):
    headers = None
    if session_id:
        headers = {"sessionId":session_id}
    datastr = json.dumps(data)
    r = requests.post("https://"+cloud+"/api", headers=headers, data=datastr)
    if r.status_code == 200:
        try:
            rjson = r.json()
            if "auth" in rjson:
                ret = rjson["auth"]
            elif "cmd" in rjson:
                ret = rjson["cmd"]
            return ret
        except Exception as error:
            print(error)
    return {"success":False, "content":r.content,"status_code":r.status_code}


def get_alarms(session_id, thing_key, alarm_name):
    """
    Retrieve the last value of a sent alarm
    """

    data_params = {"thingKey":thing_key,"key":alarm_name}
    data = {"cmd":{"command":"alarm.current","params":data_params}}
    return _send(data, session_id)

def get_attribute(session_id, thing_key, attr_name):
    """
    Retrieve the last value of a sent attribute
    """

    data_params = {"thingKey":thing_key,"key":attr_name}
    data = {"cmd":{"command":"attribute.current","params":data_params}}
    return _send(data, session_id)


def get_files(session_id, thing_key):
    """
    Retrieve a list of a specified thing's files
    """

    data_params = {"thingKey":thing_key}
    data = {"cmd":{"command":"file.list","params":data_params}}
    return _send(data, session_id)


def get_location(session_id, thing_key):
    """
    Retrieve last location of a specified thing
    """

    data_params = {"thingKey":thing_key}
    data = {"cmd":{"command":"location.current","params":data_params}}
    return _send(data, session_id)


def get_logs(session_id, thing_key, start=None):
    """
    Retrive logs from the Cloud
    """

    data_params = {"thingKey":thing_key}
    if start:
        data_params.update({"start":start})
    data = {"cmd":{"command":"log.list","params":data_params}}
    return _send(data, session_id)


def get_property(session_id, thing_key, prop_name):
    """
    Retrieve the last value of a sent property
    """

    data_params = {"thingKey":thing_key,"key":prop_name}
    data = {"cmd":{"command":"property.current","params":data_params}}
    return _send(data, session_id)


def get_session(username, password):
    """
    Get session for future communications with Cloud
    """

    data_params = {"username":username,"password":password}
    data = {"auth":{"command":"api.authenticate","params":data_params}}
    return _send(data)

def get_thing(session_id, thing_key):
    """
    Get information about a specific thing
    """

    data_params = {"key":thing_key}
    data = {"cmd":{"command":"thing.find","params":data_params}}
    return _send(data, session_id)

def delete_thing(session_id, thing_key):
    """
    delete the test thing
    """

    data_params = {"key":thing_key}
    data = {"cmd":{"command":"thing.delete","params":data_params}}
    return _send(data, session_id)

def method_exec(session_id, thing_key, method_name, params=None):
    """
    Execute Method
    """

    data_params = {"thingKey":thing_key,"method":method_name,"ackTimeout":30}
    if params:
        data_params["params"] = params
    data = {"cmd":{"command":"method.exec","params":data_params}}
    return _send(data, session_id)

def stop_app():
    """
    Stop application by sending a newline to stdin
    """
    print("[VS] Stopping device_manager")
    os.system("ps aux|grep python\ device_manager |grep -v grep|gawk {'print $2'} | xargs kill -9")



def error_quit(args):
    """
    Print error messages, stop application, and exit with error code 1
    """

    print(args)
    stop_app()
    sys.exit(1)


def strtotime(string):
    """
    Convert string to a datetime object
    """

    return datetime.strptime(string, "%Y-%m-%dT%H:%M:%S.%fZ")


def timetostr(dtime):
    """
    Convert datetime into a string
    """

    return dtime.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

def check_for_match(haystack, needle):
    found = False
    for x in range(len(haystack)):
        if needle in haystack[x]['msg']:
            print("[VS] Log: \"{}\" - OK".format(haystack[x]['msg']))
            found = True
    return found

def rest_exec_upload(session_id, thing_key, up_file, cloud_name):
    """
    Test REST calls by uploading a file
    """
    loop_done = False
    tries = 10
    upload_stat = method_exec(session_id, thing_key, "file_upload",
                              {"file_path":up_file, "file_name":cloud_name})
    #print(json.dumps(upload_stat, indent=2, sort_keys=True))
    if upload_stat.get("success") is True:
        print("[VS] upload success: True - OK")
    else:
        print("[VS] upload failed to complete successfully - FAIL")

    # Check that a file was successfully uploaded to the Cloud
    while tries > 0 and loop_done == False:
        tries -= 1
        time.sleep(0.5)

        # Check for success status for method_exec command
        if upload_stat.get("success") == True:
            files_info = get_files(session_id, thing_key)

            # Check that the file was actually uploaded
            if files_info.get("success") is True:

                # there may be more than one file returned
                for file in files_info["params"]["result"]:
                    if file["fileName"]  == cloud_name:
                        print("[VS] -->File uploaded with method_exec: {}- OK".format(cloud_name))
                        loop_done = True
    if tries == 0:
        print("[VS] method_exec failied for upload - FAIL")
        fails.append("method_exec upload")
    #return False

def rest_exec_download(session_id, thing_key, down_file, cloud_name):
    download_stat = method_exec(session_id, thing_key, "file_download",
                                {"file_path":down_file, "file_name":cloud_name})
    #print(json.dumps(download_stat, indent=2, sort_keys=True))
    if download_stat.get("success") is True:
        print("[VS] download success: True - OK")
    else:
        print("[VS] download failed to complete successfully - FAIL")

    # Check that a file was successfully downloaded from the Cloud
    tries = 10
    while tries > 0:
        tries -= 1
        time.sleep(2)
        # Check for success status for method_exec command
        if download_stat.get("success") == True:
            if os.path.isfile(down_file):
                print("[VS] File downloaded with method_exec: {} - OK".format(down_file))
                os.remove(os.path.abspath(down_file))
                break
        if tries == 0:
            print("[VS] method_exec was successful, but file not found - FAIL")
            fails.append("Finding file on device (method_exec)")
            break

def get_org_id(session_id, username):
    """
    Get org id
    """
    ret = False
    data_params = {"username":username}
    data = {"cmd":{"command":"user.find","params":data_params}}
    result = _send(data, session_id)
    #print(json.dumps(result, indent=2, sort_keys=True))

    # now get the user ID from this
    if result.get("success") is True:
        user_id = result['params']['id']
        org_id = result['params']['defaultOrgId']
    return org_id

def change_session_org(session_id, org):
    """
    Change org
    """
    ret = False
    print("[VS] Changing org to %s" % org)
    data_params = {"key":org}
    data = {"cmd":{"command":"session.org.switch","params":data_params}}
    result = _send(data, session_id)
    if result.get("success") == True:
        ret = True
    return ret

def get_attributes_from_cloud(session_id, thing_key, attr_list):
    num = len(attr_list)
    count = 0
    ret = False
    for attr in attr_list:
        print("[VS] checking for attr {}".format(attr))
        for i in range(10):
            attr_rec = None
            attr_info = get_attribute(session_id, thing_key, attr)
            # print(json.dumps(attr_info, indent=2, sort_keys=True))
            if attr_info.get("success") is True:
                attr_rec = attr_info.get("params")
            if attr_rec:
                if attr_rec == "hdc_version":
                    if not "Unknown" in attr_rec["value"]:
                        print("[VS] -> Attribute: {} {} - OK".format(attr, attr_rec["value"]))
                        count += 1
                        break
                else:
                    print("[VS] -> Attribute: {} {} - OK".format(attr, attr_rec["value"]))
                    count += 1
                    break
            time.sleep(2)
    if num == count:
        ret = True
    return ret

def wait_for_ota_done(session_id, thing_key, alarm_name):
    global fails

    state = None
    state_exp = 5
    for i in range(10):
        alarm_info = get_alarms(session_id, thing_key, alarm_name)
        #print(json.dumps(alarm_info, indent=2, sort_keys=True))
        if alarm_info.get("success") is True:
            item = alarm_info['params']
            state = item.get("state")
            #print ("[VS] -> alarm details = name {}, state {}".format(alarm_name, state))
        if state == state_exp:
           break
        else:
            time.sleep(1)

    if not state:
        print("[VS] Alarm not found in cloud")
        fails.append("Alarms retrieval")

def main():
    """
    Main function to validate abilites of host
    """

    global cloud, fails
    fails = []

    default_device_id = str(uuid.uuid4())

    if not os.path.isfile(app_file):
        error_quit("Could not find app file {}.".format(app_file))

    cloud = os.environ.get("HDCADDRESS")
    username = os.environ.get("HDCUSERNAME")
    password = os.environ.get("HDCPASSWORD")
    token = os.environ.get("HDCDMTOKEN")
    org = os.environ.get("HDCORG")
    debug = os.environ.get("HDCDEBUG")

    # ---------------------------------------------------------
    # Get Cloud credentials
    # ---------------------------------------------------------
    if not cloud:
        cloud = input("Cloud Address: ")
    if not username:
        username = input("Username: ")
    if not password:
        password = getpass.getpass("Password: ")
    if not token:
        token = input("App Token:")
    if not org:
        org = input("Org Key(Optional): ")

    # ---------------------------------------------------------
    # Ensure Cloud address is formatted correctly for later use
    # ---------------------------------------------------------
    cloud = cloud.split("://")[-1]
    cloud = cloud.split("/")[0]
    print("[VS] Cloud: {}".format(cloud))
    print("[VS] User: {}".format(username))

    # ---------------------------------------------------------
    # Start a session with the Cloud
    # ---------------------------------------------------------
    session_id = ""
    session_info = get_session(username, password)
    if session_info.get("success") is True:
        session_id = session_info["params"].get("sessionId")
    if session_id:
        print("[VS] Session ID: {} - OK".format(session_id))
    else:
        error_quit("Failed to get session id.")

    # ---------------------------------------------------------
    # now handle a switch org if needed
    # ---------------------------------------------------------
    if org:
        print("[VS] Org ID before switch=%s" % get_org_id(session_id, username))
        if change_session_org(session_id, org) == False:
            error_quit("Failed to switch org.")
        else:
            print("[VS] Org ID after switch=%s" % get_org_id(session_id, username))

    # ---------------------------------------------------------
    # Generate config for app with retrieved token
    # ---------------------------------------------------------
    generate = subprocess.Popen(pycommand+" generate_config.py -f iot-connect.cfg "
                                "-c "+cloud+" -p 8883 "
                                "-t "+token, shell=True,
                                stdout=subprocess.PIPE, stdin=subprocess.PIPE)
    ret = generate.wait()
    if ret != 0:
        error_quit("Failed to generate connection config for validation app.")
    else:
        print("[VS] Successfully generated connection config file")

    # ---------------------------------------------------------
    # Remove the downloaded file if it exists from a previous
    # validation
    # ---------------------------------------------------------
    if os.path.isfile(os.path.abspath("validate_download.txt")):
        os.remove(os.path.abspath("validate_download.txt"))

    # ------------------------------
    # check for device_id and use it
    # ------------------------------
    if os.path.isfile("device_id"):
        print("[VS] file device_id exists, using it")
        with open("device_id", "r") as did_file:
            device_id = did_file.read().strip()
        thing_key = device_id + "-" + client_id
    else:
        with open("device_id", "w") as did_file:
            did_file.write( default_device_id )
        device_id = default_device_id
        thing_key = device_id + "-" + client_id

    # ------------------------------------
    # set up the command to start the app
    # ------------------------------------
    if debug:
        output = "validate.log"
    else:
        output = "/dev/null"
    cmd = "{} {} > {} 2>&1 &".format(pycommand, app_file, output)
    print("[VS] running command {}".format(cmd))
    os.system(cmd)

    # ----------------------------------------------------------------
    # Poll loop: check in the cloud for each expected attribute.  If
    # all are found, the device manager is up.
    # Validate that the expected attribute value was published to the Cloud
    # ----------------------------------------------------------------
    attr_list = ["hdc_version", "hostname", "kernel", "mac_address", "os_name", "os_version", "remote_access_support"]
    if not get_attributes_from_cloud(session_id, thing_key, attr_list):
        print("[VS] Error: failed to retrieve attributes")
        fails.append("Alarms retrieval")
    else:
        print("[VS] attributes retrieved successfully")

    # ----------------------------------------------------------------
    # Check that the pass action executes and returns successfully
    # ----------------------------------------------------------------
    act = "ping"
    act_info = method_exec(session_id, thing_key, act)
    if debug:
        print(json.dumps(act_info, indent=2, sort_keys=True))

    if act_info.get("success") is True:
        params = act_info.get("params")
        print("[VS] {} action success: True - OK".format(act))
        print("[VS] -> response {}, time_stamp {}".format(params.get("response"), params.get("time_stamp")))
    else:
        print("[VS] {} action failed to complete successfully - FAIL".format(act))
        fails.append("Action {} execution".format(act))

    # ---------------------------
    # Check file upload/download
    # ---------------------------
    up_file = os.path.abspath("test_upload.txt")
    cloud_name = "validate_up.txt"
    with open(up_file, 'w') as fh:
        fh.write("test upload")
    fh.close()

    cloud_name = "validate_up.txt"
    rest_exec_upload(session_id, thing_key, up_file, cloud_name)

    down_file = os.path.abspath("validate_down.txt")
    rest_exec_download(session_id, thing_key, down_file, cloud_name)

    # ---------------------------------------------------------------
    # OTA test, use the share/example-ota-packages/simple-ota-package
    # invoke the software update action
    # ---------------------------------------------------------------
    os.system("cd share/example-ota-packages/simple-ota-package; tar czf ../../../ota.tar.gz *.sh *.json")
    up_file = os.path.abspath("ota.tar.gz")
    rest_exec_upload(session_id, thing_key, up_file, "test-ota.tar.gz")

    act = "software_update"
    act_info = method_exec(session_id, thing_key, act, {"package":"test-ota.tar.gz"})
    if debug:
        print(json.dumps(act_info, indent=2, sort_keys=True))

    if act_info.get("success") is True:
        print("[VS] {} action success: True - OK".format(act))
    else:
        print("[VS] {} action failed to complete successfully - FAIL".format(act))
        fails.append("Action {} execution".format(act))

    wait_for_ota_done(session_id, thing_key, "software_update")
    
    if debug:
        with open("validate.log", "r") as log:
            print (log.read().strip())

    print("[VS] Deleting thing key {} for this test".format(thing_key))
    thing_info = delete_thing(session_id, thing_key)
    if debug:
        print(json.dumps(thing_info, indent=2, sort_keys=True))

    return fails

if __name__ == "__main__":
    fails = []
    try:
        fails = main()
    except Exception as error:
        stop_app()
    if not fails:
        print("[VS] \n\nAll passed! Success.")
        sys.exit(0)
    else:
        print("[VS] \n\nFailed on the following:")
        for fail in fails:
            print(fail)
        sys.exit(1)
