#!/usr/bin/env python3

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
Simple app that demonstrates the action APIs in the HDC Python library
"""

import argparse
import errno
import math
import os
from os.path import abspath
import signal
import sys
from time import sleep

import hdcazure

head, tail = os.path.split(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, head)

import device_cloud as iot
from device_cloud import osal

## Use this only for Azure AD service-to-service authentication
#from azure.common.credentials import ServicePrincipalCredentials

## Use this only for Azure AD end-user authentication
from azure.common.credentials import UserPassCredentials

## Use this only for Azure AD multi-factor authentication
from msrestazure.azure_active_directory import AADTokenCredentials

## Required for Azure Data Lake Store account management
from azure.mgmt.datalake.store import DataLakeStoreAccountManagementClient
from azure.mgmt.datalake.store.models import DataLakeStoreAccount

## Required for Azure Data Lake Store filesystem management
from azure.datalake.store import core, lib, multithread

# Common Azure imports
from azure.mgmt.resource.resources import ResourceManagementClient
from azure.mgmt.resource.resources.models import ResourceGroup

import adal, uuid, time

## Use these as needed for your application
import logging, getpass, pprint, uuid, time


#adl://nta.azuredatalakestore.net
#https://nta.azuredatalakestore.net

# Tenant ID for your Azure Subscription
TENANT_ID = 'a4b883aa-078f-4426-8933-e23cf50b0c4c'

# Your Service Principal App ID
CLIENT_ID = '4a140eb2-b459-4595-983d-fc140ae1f628'
CLIENT_SECRET = 'MSMBPpMh768MetQPsVme8J4kI/+dMi9jBHcSdfCsMsY='

# Your Service Principal Password
KEY = 'password'

#adlCreds = ServicePrincipalCredentials(
#    client_id = CLIENT_ID,
#    secret = KEY,
#    tenant = TENANT_ID
#)

## Declare variables
subscriptionId = '90b9aabf-b01b-4f89-8482-38e7ea808794'
adlsAccountName = 'user@davehdholloway.onmicrosoft.com'
password = 'Pongo8it'
#adlsAccountName = 'daveh@dholloway.com'
#password = 'Pongo8it'

def authenticate_client_key():
    """
    Authenticate using service principal w/ key.
    """
    authority_host_uri = 'https://login.microsoftonline.com'
    tenant = TENANT_ID
    authority_uri = authority_host_uri + '/' + tenant
    resource_uri = 'https://management.core.windows.net/'
#    resource_uri = 'https://nta.azuredatalakestore.net/'
    client_id = CLIENT_ID
    client_secret = CLIENT_SECRET
    
    context = adal.AuthenticationContext(authority_uri, api_version=None)
    mgmt_token = context.acquire_token_with_client_credentials(resource_uri, client_id, client_secret)
    credentials = AADTokenCredentials(mgmt_token, client_id)

    return credentials


running = True

def sighandler(signum, frame):
    """
    Signal handler for exiting app
    """
    global running
    if signum == signal.SIGINT:
        print("Received SIGINT, stopping application...")
        running = False

def basic_action():
    """
    Simple action callback that takes no parameters.
    """
    print("I'm an action!")
    return (iot.STATUS_SUCCESS, "")

def send_event(client):
    """
    Simple action callback that takes one parameter, client, so it can send an
    event up to the cloud.
    """
    client.event_publish("I'm an action!")
    return (iot.STATUS_SUCCESS, "")

def parameter_action(client, params):
    """
    Action callback that takes two parameters, client and action params, that
    will print the message present in the "message" parameter send by the cloud
    when the action is executed.
    """
    message = params.get("message", "")
    print(message)


    # example on how to use out parameters.  Note: completion
    # variables DO NOT need to be defined in the thing definiton in
    # the cloud.
    p = {}
    p['response'] = "this is an example completion variable"
    p['response2'] = "Another completion variable"
    p['response3'] = "Yet another completion variable"

    return (iot.STATUS_SUCCESS, "", p)

def azure_file_upload(client, params, user_data):
    """
    Callback for the "file_upload" method which uploads a file from the
    cloud to the local system. Wildcards in the file name are supported.
    """
    file_name = None
    if params:
        file_name = params.get("file_name")
        if "dest_name" in params:
            dest_name = params.get("dest_name")
        else:
            dest_name = None


    if file_name:
        if not file_name.startswith('~'):
            if not file_name.startswith('/'):
                file_name = abspath(os.path.join(user_data[0], "upload", \
                                    file_name))
            client.log(iot.LOGINFO, "Azure Uploading {}".format(file_name))
            # hdc_azure_upload_file does not report errors
            hdcazure.hdc_azure_upload_file(file_name, dest_name)
            result = iot.STATUS_SUCCESS
#            result = client.file_upload(file_name, upload_name=dest_name, \
#                                        blocking=True, timeout=240, \
#                                        file_global=file_global)
            if result == iot.STATUS_SUCCESS:
                message = ""
            else:
                message = iot.status_string(result)
        else:
            message = "Paths cannot use '~' to reference a home directory"
            result = iot.STATUS_BAD_PARAMETER
    else:
        result = iot.STATUS_BAD_PARAMETER
        message = "No file name given"

    return (result, message)

def file_upload(client, params, user_data):
    """
    Callback for the "file_upload" method which uploads a file from the
    cloud to the local system. Wildcards in the file name are supported.
    """
    file_name = None
    message = None

    if params:
        file_name = params.get("file_name")

    if file_name:
        print ("push file named: " + file_name)
        result = iot.STATUS_SUCCESS
    else:
        result = iot.STATUS_BAD_PARAMETER
        message = "No file name given"

    token = lib.auth(TENANT_ID, adlsAccountName, password)
    client = core.AzureDLFileSystem(token, store_name='nta')
    pair = os.path.split(file_name)
    val = client.put(file_name, '/system/' + pair[1])

    print (file_name + ' copied to Azure')
    message = client.ls('/system')

    return (result, message)

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
    app_id = "hdc_azure_app"
    if args.app_id:
        app_id = args.app_id
    client = iot.Client(app_id)

    # Use the demo-connect.cfg file inside the config directory
    # (Default would be python-demo-app-connect.cfg)
    config_file = "iot-azure-actions.cfg"
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
    client.action_register_callback("azure_file_upload", azure_file_upload, ".")

    client.action_register_callback("quit", quit_me)

    # Connect to Cloud
    if client.connect(timeout=10) != iot.STATUS_SUCCESS:
        client.error("Failed")
        sys.exit(1)

    while running and client.is_alive():

        # Wrap sleep with an exception handler to fix SIGINT handling on Windows
        try:
            sleep(1)
        except IOError as err:
            if err.errno != errno.EINTR:
                raise

    client.disconnect(wait_for_replies=True)

