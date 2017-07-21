"""
This module contains all the constant values required by the Client
"""


# CONFIGURATION DEFAULTS

# Default configuration directory
DEFAULT_CONFIG_DIR = "."
# Default level of logging
DEFAULT_LOG_LEVEL = "ALL"
# Default loop time for MQTT in seconds
DEFAULT_LOOP_TIME = 5
# Default number of seconds to receive a reply
DEFAULT_MESSAGE_TIMEOUT = 15
# Default runtime directory
DEFAULT_RUNTIME_DIR = "."
# Default number of worker threads
DEFAULT_THREAD_COUNT = 3


# CONNECTION STATES

# Not connected to Cloud
STATE_DISCONNECTED = 0
# Connecting to Cloud
STATE_CONNECTING = 1
# Connected to Cloud
STATE_CONNECTED = 2


# RETURN STATUSES

# Success
STATUS_SUCCESS = 0
# Action successfully invoked (fire & forget)
STATUS_INVOKED = 1
# Invalid parameter passed
STATUS_BAD_PARAMETER = 2
# Bad request received
STATUS_BAD_REQUEST = 3
# Error executing the requested action
STATUS_EXECUTION_ERROR = 4
# Already exists
STATUS_EXISTS = 5
# File open failed
STATUS_FILE_OPEN_FAILED = 6
# Full storage
STATUS_FULL = 7
# Input/output error
STATUS_IO_ERROR = 8
# No memory
STATUS_NO_MEMORY = 9
# No permission
STATUS_NO_PERMISSION = 10
# Not executable
STATUS_NOT_EXECUTABLE = 11
# Not found
STATUS_NOT_FOUND = 12
# Not Initialized
STATUS_NOT_INITIALIZED = 13
# Parameter out of range
STATUS_OUT_OF_RANGE = 14
# Failed to parse a message
STATUS_PARSE_ERROR = 15
# Timed out
STATUS_TIMED_OUT = 16
# Try again
STATUS_TRY_AGAIN = 17
# Not supported in this version of the api
STATUS_NOT_SUPPORTED = 18
# General Failure
STATUS_FAILURE = 19


# STATUS STRINGS
STATUS_STRINGS = {
    STATUS_SUCCESS:"Success",
    STATUS_INVOKED:"Invoked",
    STATUS_BAD_PARAMETER:"Bad Parameter",
    STATUS_BAD_REQUEST:"Bad Request",
    STATUS_EXECUTION_ERROR:"Execution Error",
    STATUS_EXISTS:"Already Exists",
    STATUS_FILE_OPEN_FAILED:"File Open Failed",
    STATUS_FULL:"Full",
    STATUS_IO_ERROR:"I/O Error",
    STATUS_NO_MEMORY:"Out of Memory",
    STATUS_NO_PERMISSION:"No Permission",
    STATUS_NOT_EXECUTABLE:"Not Executable",
    STATUS_NOT_FOUND:"Not Found",
    STATUS_NOT_INITIALIZED:"Not Initialized",
    STATUS_OUT_OF_RANGE:"Out of Range",
    STATUS_PARSE_ERROR:"Parsing Error",
    STATUS_TIMED_OUT:"Timed Out",
    STATUS_TRY_AGAIN:"Try Again",
    STATUS_NOT_SUPPORTED:"Not Supported",
    STATUS_FAILURE:"Failure"
}


# Log message format
LOG_FORMAT = "[%(asctime)s]%(levelname)s: %(filename)s:%(lineno)d (%(funcName)s) - %(message)s"

# Time format supported by Cloud
TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


# TYPES OF WORK

# Parse a received message
WORK_MESSAGE = 0
# Publish pending publishes
WORK_PUBLISH = 1
# Execute a requested action
WORK_ACTION = 2
# Download a file
WORK_DOWNLOAD = 3
# Upload a file
WORK_UPLOAD = 4

