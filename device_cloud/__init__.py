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
This module contains the Client class required for applications to connect and
interact with the Wind River Helix Device Cloud 2.Next.
"""

from logging import CRITICAL as LOGCRITICAL
from logging import ERROR as LOGERROR
from logging import DEBUG as LOGDEBUG
from logging import INFO as LOGINFO
from logging import NOTSET as LOGNOTSET
from logging import WARNING as LOGWARNING

from device_cloud._core.client import Client
from device_cloud._core.handler import status_string

from device_cloud._core.constants import DEFAULT_CONFIG_DIR
from device_cloud._core.constants import DEFAULT_CONFIG_FILE
from device_cloud._core.constants import DEFAULT_KEEP_ALIVE
from device_cloud._core.constants import DEFAULT_LOOP_TIME
from device_cloud._core.constants import DEFAULT_THREAD_COUNT

from device_cloud._core.constants import STATUS_SUCCESS
from device_cloud._core.constants import STATUS_INVOKED
from device_cloud._core.constants import STATUS_BAD_PARAMETER
from device_cloud._core.constants import STATUS_BAD_REQUEST
from device_cloud._core.constants import STATUS_EXECUTION_ERROR
from device_cloud._core.constants import STATUS_EXISTS
from device_cloud._core.constants import STATUS_FILE_OPEN_FAILED
from device_cloud._core.constants import STATUS_FULL
from device_cloud._core.constants import STATUS_IO_ERROR
from device_cloud._core.constants import STATUS_NO_MEMORY
from device_cloud._core.constants import STATUS_NO_PERMISSION
from device_cloud._core.constants import STATUS_NOT_EXECUTABLE
from device_cloud._core.constants import STATUS_NOT_FOUND
from device_cloud._core.constants import STATUS_NOT_INITIALIZED
from device_cloud._core.constants import STATUS_OUT_OF_RANGE
from device_cloud._core.constants import STATUS_PARSE_ERROR
from device_cloud._core.constants import STATUS_TIMED_OUT
from device_cloud._core.constants import STATUS_TRY_AGAIN
from device_cloud._core.constants import STATUS_NOT_SUPPORTED
from device_cloud._core.constants import STATUS_FAILURE

import device_cloud.osal
import device_cloud.ota_handler
import device_cloud.relay
import device_cloud.identity

__all__ = ["Client",
           "status_string",
           "osal"
           "ota_handler",
           "relay",
           "identity",
           "DEFAULT_CONFIG_DIR",
           "DEFAULT_CONFIG_FILE",
           "DEFAULT_KEEP_ALIVE",
           "DEFAULT_LOOP_TIME",
           "DEFAULT_THREAD_COUNT",
           "LOGCRITICAL",
           "LOGERROR",
           "LOGDEBUG",
           "LOGINFO",
           "LOGNOTSET",
           "LOGWARNING",
           "STATUS_SUCCESS",
           "STATUS_INVOKED",
           "STATUS_BAD_PARAMETER",
           "STATUS_BAD_REQUEST",
           "STATUS_EXECUTION_ERROR",
           "STATUS_EXISTS",
           "STATUS_FILE_OPEN_FAILED",
           "STATUS_FULL",
           "STATUS_IO_ERROR",
           "STATUS_NO_MEMORY",
           "STATUS_NO_PERMISSION",
           "STATUS_NOT_EXECUTABLE",
           "STATUS_NOT_FOUND",
           "STATUS_NOT_INITIALIZED",
           "STATUS_OUT_OF_RANGE",
           "STATUS_PARSE_ERROR",
           "STATUS_TIMED_OUT",
           "STATUS_TRY_AGAIN",
           "STATUS_NOT_SUPPORTED",
           "STATUS_FAILURE"]
