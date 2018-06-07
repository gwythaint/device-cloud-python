#!/usr/bin/env python3

import argparse
import errno
import math
import random
import signal
import sys
import os
import psutil

## Use this only for Azure AD service-to-service authentication
from azure.common.credentials import ServicePrincipalCredentials

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
CLIENT_ID = '4a140eb2-b459-4595-983d-fc140ae1f628'
CLIENT_SECRET = 'MSMBPpMh768MetQPsVme8J4kI/+dMi9jBHcSdfCsMsY='

## Declare variables
adlsAccountName = 'user@davehdholloway.onmicrosoft.com'
password = 'Pongo8it'

store = 'nta'
token = None
client = None

def authenticate_client():
    global token, client

    if (token == None):
        token = lib.auth(TENANT_ID, adlsAccountName, password)
    if (client == None):
        client = core.AzureDLFileSystem(token, store_name=store)
    
def hdc_azure_upload_file(filename, path):
    authenticate_client()
    client.put(filename, path)
    
def hdc_azure_download_file(path, filename):
    authenticate_client()
    client.get(path, filename)


if __name__ == '__main__':
    filename = 'test.txt'
    hdc_azure_upload_file(filename, '/system/' + filename + 'xx')
    hdc_azure_download_file('/system/' + filename, filename + '2')
#    val = client.ls('/system/')
    val = client.ls('/')
    print (val)
