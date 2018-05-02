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
A script that executes an application which publishes known values to the Cloud
with the purpose of validating the abilities of the host to run the device_cloud agent.
In the Cloud there must be a thing definition with:
  - method "pass_action" with one string parameter "param"
  - method "fail_action" with no parameters
  - property "property"
  - attribute "attribute"
  - alarm "alarm" with a possible state of 1
There must also be an associated application with "validat" in the name so the
token can be discovered.
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

app_file = "validate_app.py"
cloud = ""
validate_app = None
default_thing_def = "hdc_validate_def"
default_app_name = "hdc_validate_app"
pycommand = "python"

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


def get_alarms(session_id, thing_key, alarm_name, ts):
    """
    Retrieve the last value of a sent alarm
    """

    data_params = {"thingKey":thing_key,"key":alarm_name,"start":ts}
    data = {"cmd":{"command":"alarm.history","params":data_params}}
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

def stop_app(proc):
    """
    Stop application by sending a newline to stdin
    """

    if proc:
        proc.kill()


def error_quit(*args):
    """
    Print error messages, stop application, and exit with error code 1
    """

    for arg in args:
        if arg.__class__.__name__ == "str":
            print(arg)
        elif arg.__class__.__name__ == "Popen":
            stop_app(arg)
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

def rest_exec_upload(session_id, thing_key):
    """
    Test REST calls by uploading a file
    """
    loop_done = False
    tries = 10
    upload_stat = method_exec(session_id, thing_key, "file_upload",
                              {"file_name":"validate_exec.txt"})
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
                    if file["fileName"]  == "validate_exec.txt":
                        print("[VS] -->File uploaded with method_exec: validate_exec.txt - OK")
                        loop_done = True

            # check for the file
            upload_stat = method_exec(session_id, thing_key, "file_upload",
                                      {"file_name":"validate_exec.txt"})
    if tries == 0:
        print("[VS] method_exec failied for upload - FAIL")
        fails.append("method_exec upload")

def rest_exec_download(session_id, thing_key):
    """
    Test REST calls by downloading a file
    """
    download_stat = method_exec(session_id, thing_key, "file_download",
                                {"file_name":"validate_exec.txt"})
    if download_stat.get("success") is True:
        print("[VS] upload success: True - OK")
    else:
        print("[VS] upload failed to complete successfully - FAIL")

    # Check that a file was successfully downloaded from the Cloud
    tries = 10
    while tries > 0:
        tries -= 1
        time.sleep(0.5)
        # Check for success status for method_exec command
        if download_stat.get("success") == True:
            loop_done = False
            if os.path.isfile(os.path.abspath("validate_exec.txt")):
                print("[VS] File downloaded with method_exec: validate_exec.txt - OK")
                os.remove(os.path.abspath("validate_exec.txt"))
                loop_done = True
                break
            else:
                # Try again
                download_stat = method_exec(session_id, thing_key, "file_download",
                                            {"file_name":"validate_exec.txt"})
                if tries == 0:
                    print("[VS] method_exec was successful, but file not found - FAIL")
                    fails.append("Finding file on device (method_exec)")
                    break
            if loop_done == True:
                break
        else:
            download_stat = method_exec(session_id, thing_key, "file_download",
                                        {"file_name":"validate_exec.txt"})
            if tries == 0:
                print("[VS] method_exec failied for download - FAIL")
                fails.append("method_exec download")

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

def main():
    """
    Main function to validate abilites of host
    """

    global cloud
    start_time = datetime.utcnow()
    global fails
    fails = []

    # pregenerate the device ID and clean up at the end.
    default_device_id = str(uuid.uuid4())

    if not os.path.isfile(app_file):
        error_quit("Could not find app file {}.".format(app_file))

    cloud = os.environ.get("HDCADDRESS")
    username = os.environ.get("HDCUSERNAME")
    password = os.environ.get("HDCPASSWORD")
    token = os.environ.get("HDCAPPTOKEN")
    org = os.environ.get("HDCORG")

    # Get Cloud credentials
    if not cloud:
        cloud = input("Cloud Address: ")
    if not username:
        username = input("Username: ")
    if not password:
        password = getpass.getpass("Password: ")
    if not token:
        token = input("App Token:")
    #if not org:
        #org = input("Org Key(Optional): ")

    # Ensure Cloud address is formatted correctly for later use
    cloud = cloud.split("://")[-1]
    cloud = cloud.split("/")[0]
    print("[VS] Cloud: {}".format(cloud))

    # Start a session with the Cloud
    session_id = ""
    session_info = get_session(username, password)
    if session_info.get("success") is True:
        session_id = session_info["params"].get("sessionId")
    if session_id:
        print("[VS] Session ID: {} - OK".format(session_id))
    else:
        error_quit("Failed to get session id.")

    # now handle a switch org if needed
    if org:
        print("[VS] Org ID before switch=%s" % get_org_id(session_id, username))
        if change_session_org(session_id, org) == False:
            error_quit("Failed to switch org.")
        else:
            print("[VS] Org ID after switch=%s" % get_org_id(session_id, username))

    # Generate config for app with retrieved token
    generate = subprocess.Popen(pycommand+" generate_config.py -f validate.cfg "
                                "-c "+cloud+" -p 8883 "
                                "-t "+token, shell=True,
                                stdout=subprocess.PIPE, stdin=subprocess.PIPE)
    ret = generate.wait()
    if ret != 0:
        error_quit("Failed to generate connection config for validation app.")

    # Remove the downloaded file if it exists from a previous validation
    if os.path.isfile(os.path.abspath("validate_download.txt")):
        os.remove(os.path.abspath("validate_download.txt"))

    # delete the thing in the cloud so that we don't have 100s of new
    # instances of test apps.  Write the device_id here and then check
    # the cloud.  Subsequent code will use the device_id.  This test
    # would normally be run in a docker instance with a new device_id each time.
    if os.path.isfile("device_id"):
        print("[VS] file device_id exists, using it")
        with open("device_id", "r") as did_file:
            device_id = did_file.read().strip()
        thing_key = device_id + "-iot-validate-app"
    else:
        with open("device_id", "w") as did_file:
            did_file.write( default_device_id )
        device_id = default_device_id
        thing_key = device_id + "-iot-validate-app"


    # get the time stamp to pass in to the alarm request
    ts = datetime.utcnow()
    time_stamp = ts.strftime(constants.TIME_FORMAT)
    time.sleep(2)

    # Start app
    validate_app = subprocess.Popen([pycommand, app_file],
                                    stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE)

    # Check to make sure thing is connected in Cloud
    # when the app is ready it will download a file
    # "validate_download.txt". Check for that file and know that we
    # are connected
    tries = 50
    while tries > 0:
        tries -= 1
        time.sleep(0.5)
        if os.path.exists("validate_download.txt"):
            print("[VS] File uploaded: validate_upload.txt - OK")
            break
        if tries < 0:
            tries = 0
            break

    if tries == 0:
        print("[VS] App not connected, unable to find validate_download.txt file- FAIL")
        error_quit("Thing not connected - FAIL", validate_app)

    # Check that the expected property value was published to the Cloud
    prop = None
    for i in range(10):
        prop_info = get_property(session_id, thing_key, "property")
        #print(json.dumps(prop_info, indent=2, sort_keys=True))
        if prop_info.get("success") is True:
           prop = prop_info.get("params")
           if prop:
               if (strtotime(prop["ts"]) > start_time and
                   strtotime(prop["ts"]) < datetime.utcnow()):
                   if prop["value"] == 12.34:
                       print("[VS] Property: {} - OK".format(prop["value"]))
                       break
                   else:
                       print("[VS] Wrong property value: {} != 12.34 "
                        "- FAIL".format(prop["value"]))
                       fails.append("Property value")
               else:
                   print("[VS] Property timestamp out of range of application - FAIL")
                   fails.append("Property time")
           else:
               print("[VS] Property not found in Cloud - FAIL")
               fails.append("Property retrieval")

    # Check that the expected attribute value was published to the Cloud
    attr = None
    for i in range(10):
        attr_info = get_attribute(session_id, thing_key, "attribute")
        print(json.dumps(attr_info, indent=2, sort_keys=True))
        if attr_info.get("success") is True:
            attr = attr_info.get("params")
        if attr:
            if (strtotime(attr["ts"]) > start_time and
                    strtotime(attr["ts"]) < datetime.utcnow()):
                if attr["value"] == "text and such":
                    print("[VS] Attribute: \"{}\" - OK".format(attr["value"]))
                    break
                else:
                    print("[VS] Wrong attribute value: {} != \"text and such\" - FAIL".format(attr["value"]))
                    fails.append("Attribute value")
            else:
                print("[VS] Attribute timestamp out of range of application - FAIL")
                fails.append("Attribute time")
        else:
            print("[VS] Attribute not found in Cloud - FAIL")
            fails.append("Attribute retrieval")
        time.sleep(2)

    # ---------------------------------------------------------------
    # Process the alarms:
    # the validate_app publishes 5 alarms, make sure they all come
    # back
    # ---------------------------------------------------------------
    count = 0
    count_exp = 5
    done = False
    for i in range(10):
        alarm_info = get_alarms(session_id, thing_key, "test_alarm", time_stamp)
        #print(json.dumps(alarm_info, indent=2, sort_keys=True))
        if alarm_info.get("success") is True:
            if alarm_info and alarm_info['params']['values'] is not None:
                for item in alarm_info['params']['values']:
                    msg = item.get("msg")
                    state = item.get("state")
                    print ("alarm details = name test_alarm, state {}, msg {}".format(msg, state))
                    count += 1
                if count == count_exp:
                    print("[VS] Retrieved all alarms {}".format(count))
                    break
                else:
                    print ("Not all alarms retrieved, trying again {}".format(count))
                    count = 0
        else:
            print("[VS] Alarms not found in Cloud - FAIL")
            fails.append("Alarms retrieval")
        time.sleep(2)
    if count != count_exp:
        print("[VS] Alarm count not correct")
        fails.append("Alarms retrieval")

    # Check that the expected location was published to the Cloud
    loc = None
    for i in range(10):
        loc_info = get_location(session_id, thing_key)
        #print(json.dumps(loc_info, indent=2, sort_keys=True))
        if loc_info.get("success") is True:
            loc = loc_info.get("params")
        if loc:
            errors = []
            if loc["lat"] != 45.351603:
                errors.append("lat: {} != 45.351603".format(loc["lat"]))
            if loc["lng"] != -75.918713:
                errors.append("lng: {} != ".format(loc["lng"]))
            if loc["heading"] != 12.34:
                errors.append("heading: {} != 12.34".format(loc["heading"]))
            if loc["altitude"] != 1.0:
                errors.append("altitude: {} != 1.0".format(loc["altitude"]))
            if loc["speed"] != 2.0:
                errors.append("speed: {} != 2.0".format(loc["speed"]))
            if loc["fixAcc"] != 3.0:
                errors.append("fixAcc: {} != 3.0".format(loc["fixAcc"]))
            if loc["fixType"] != "crystal ball":
                errors.append("fix_type: {} != \"crystal ball\"".format(loc["fixType"]))
            if errors:
                print("[VS] Wrong location: {} - FAIL".format(", ".join(errors)))
                fails.append("Location")
            else:
                print("[VS] Location: lat:{}, lng:{}, etc... - OK".format(loc["lat"], loc["lng"]))
                break
        else:
            print("[VS] Location not found in Cloud - FAIL")
            fails.append("Location retrieval")

    # Check that the expected log was published to the Cloud. 
    # load the json obj and walk it to make sure
    # recheck for logs if at first it fails
    logs = None
    found = False
    for i in range(10):
        logs_info = get_logs(session_id, thing_key, start=timetostr(start_time))
        found = check_for_match(logs_info['params']['result'], "logs and such")
        if found == True:
            break
        time.sleep(1)

    if found == False:
        print("[VS] No logs for this thing in the specified time frame - FAIL")
        fails.append("Log retrieval")

    # Check that the pass action executes and returns successfully
    pass_act_info = method_exec(session_id, thing_key, "pass_action",
                                {"param":"value"})
    #print(json.dumps(pass_act_info, indent=2, sort_keys=True))
    if pass_act_info.get("success") is True:
        print("[VS] Pass action success: True - OK")
    else:
        print("[VS] Pass action failed to complete successfully - FAIL")
        fails.append("Action successful execution")

    # Check that the fail action executes and returns a failure successfully
    fail_act_info = method_exec(session_id, thing_key, "fail_action")
    #print(json.dumps(fail_act_info, indent=2, sort_keys=True))
    if fail_act_info.get("success") is False:
        errmsgs = fail_act_info.get("errorMessages")
        if len(errmsgs) == 1 and errmsgs[0] == "fail and such":
            print("[VS] Fail action error message: \"fail and such\" - OK")
        else:
            print("[VS] Fail action error message: \"{}\" != \"fail and such\" - "
                  "FAIL".format(errmsgs[0]))
            fails.append("Action error message")
    else:
        print("[VS] Fail action did not return failure - FAIL")
        fails.append("Action failure")

    # Check that a file was successfully uploaded to the Cloud
    tries = 50
    while tries > 0:
        tries -= 1
        time.sleep(0.5)
        files_info = get_files(session_id, thing_key)
        loop_done = False
        if files_info.get("success") is True:
            # there may be more than one file returned
            file_results = files_info["params"]["result"]
            for file in file_results:
                if file["fileName"]  == "validate_upload.txt":
                    print("[VS] File uploaded: validate_upload.txt - OK")
                    loop_done = True
                    break
            if loop_done == True:
                break
        else:
            if tries == 0:
                print("[VS] File list could not be retrieved - FAIL")
                fails.append("File list retrieval")

    # Check that a file was successfully downloaded from the Cloud
    tries = 50
    while tries > 0:
        tries -= 1
        time.sleep(0.5)
        if os.path.isfile(os.path.abspath("validate_download.txt")):
            print("[VS] File downloaded: validate_download.txt - OK")
            os.remove(os.path.abspath("validate_download.txt"))
            break
        else:
            if tries == 0:
                print("[VS] Could not find downloaded file - FAIL")
                fails.append("Download file")

    rest_exec_upload(session_id, thing_key)
    rest_exec_download(session_id, thing_key)

    stop_app(validate_app)

    print("[VS] Deleting thing key {} for this test".format(thing_key))
    thing_info = delete_thing(session_id, thing_key)
    #print(json.dumps(thing_info, indent=2, sort_keys=True))

    return fails

if __name__ == "__main__":
    fails = []
    try:
        fails = main()
    except Exception as error:
        stop_app(validate_app)
        raise(error)
    if not fails:
        print("[VS] \n\nAll passed! Success.")
        sys.exit(0)
    else:
        print("[VS] \n\nFailed on the following:")
        for fail in fails:
            print(fail)
        sys.exit(1)
