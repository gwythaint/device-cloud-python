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
This module defines several helper classes for use in the device_cloud handler
"""

import inspect
import json
import subprocess
from datetime import datetime

from device_cloud._core import constants

class Action(object):
    """
    Holds information associating an action and a callback
    """

    def __init__(self, name, callback, client, user_data=None):
        self.name = name
        self.callback = callback
        self.client = client
        self.user_data = user_data

    def __str__(self):
        string = "Action {} --> Callback {}"
        return string.format(self.name, self.callback.__name__)

    def execute(self, request):
        """
        Execute callback
        """

        # Determine the callback prototype that we have
        signature = inspect.getargspec(self.callback)
        args = []
        arglen = len(signature.args)

        # If there is a "self" parameter (ie. for class methods as a callback),
        # decrement the number of args so as to supply the correct amount
        if inspect.ismethod(self.callback):
            arglen -= 1

        # Build the arguments to pass based on the protoype
        if arglen >= 1:
            args.append(self.client)

        if arglen >= 2:
            args.append(request.params)

        if arglen >= 3:
            args.append(self.user_data)

        if arglen >= 4:
            args.append(request)

        return self.callback(*args)


class ActionCommand(Action):
    """
    Holds information associating an action and a console command
    """

    def __init__(self, name, callback, client, user_data=None):
        super(ActionCommand, self).__init__(name, None, client, user_data)
        self.command = callback

    def __str__(self):
        return "Action {} --> Command \"{}\"".format(self.name, self.command)

    def execute(self, request):
        """
        Execute command
        """

        # Append parameters as command line arguments
        final_command = [self.command]
        if request.params:
            for key in request.params:
                if request.params[key] is True:
                    # Value is True, just append flag
                    final_command.append("--{}".format(key))
                elif request.params[key] is False:
                    # Value is False, do not append flag
                    pass
                else:
                    # Append --param=value
                    final_command.append("--{}={}".format(key,
                                                          request.params[key]))

        # Execute command with arguments and wait for result
        proc = subprocess.Popen(final_command, shell=False,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        outstr, errstr = proc.communicate()
        ret_code = proc.returncode

        return_string = "command: {}  ,  stdout: {}  ,  stderr: {}"
        return (ret_code, return_string.format(final_command, outstr, errstr))


class ActionRequest(object):
    """
    Holds information about action requests for execution
    """

    def __init__(self, request_id, name, params):
        self.request_id = request_id
        self.name = name
        self.params = params


class Callbacks(dict):
    """
    Dict to hold all action callbacks and execute them when required
    """

    def __init__(self):
        super(Callbacks, self).__init__()

    def add_action(self, action):
        """
        Add a new action callback if an action of that name is not already
        registered
        """

        if self.__contains__(action.name):
            raise KeyError("Action \"{}\" already has a callback".format(
                action.name))
        else:
            self.__setitem__(action.name, action)

    def execute_action(self, action_request):
        """
        Execute a specific action callback from an action request
        """

        result = None

        # Attempt to execute action callback if an action with the same name as
        # the request is registered
        if action_request.name not in self:
            raise KeyError("Action \"{}\" does not have a callback".format(
                action_request.name))
        else:
            result = self[action_request.name].execute(action_request)

        return result

    def remove_action(self, action_name):
        """
        Remove an action callback as long as it exists
        """

        if action_name not in self:
            raise KeyError("Action \"{}\" does not have a callback".format(
                action_name))
        else:
            del self[action_name]


class Config(dict):
    """
    Holds all configuration information about the Client
    """

    def __init__(self):
        # Call dict init function
        super(Config, self).__init__()

    def __getattribute__(self, attr):
        try:
            return super(Config, self).__getattribute__(attr)
        except AttributeError:
            return self.get(attr)

    def __setattr__(self, attr, value):
        self.__setitem__(attr, value)

    def __str__(self):
        return json.dumps(self, indent=2, sort_keys=True)

    def update(self, other, overwrite=True):
        # Update self with values from other dict
        # Default behaviour is to overwrite all values, but optionally can keep
        # any previous values
        if not isinstance(other, dict):
            raise ValueError("Config can only be updated with a dict")

        for key, value in other.items():
            if isinstance(value, dict):
                if key not in self:
                    self[key] = Config()
                if isinstance(self[key], Config):
                    self[key].update(value, overwrite)
                elif overwrite:
                    self[key] = Config()
                    self[key].update(value, overwrite)

            elif key not in self or overwrite:
                if str(value).lower() == "true":
                    self[key] = True
                elif str(value).lower() == "false":
                    self[key] = False
                elif value is not None:
                    self[key] = value


class FileTransfer(object):
    """
    Holds information about pending file transfers
    """

    def __init__(self, file_name, file_path, client, callback=None,
                 file_id=None, file_checksum=None):
        self.file_name = file_name
        self.file_path = file_path
        self.client = client
        self.callback = callback
        self.file_id = file_id
        self.file_checksum = file_checksum
        self.status = None
        self.resume_download = False
        self.file_size = None
        self.download_temp_path = None

    def finish(self):
        """
        Run the completion callback associated with this file transfer
        """
        if self.callback:
            self.callback(self.client, self.file_name, self.status)


class Message(object):
    """
    Holds received messages in their json format
    """

    def __init__(self, topic, json_msg):
        self.topic = topic
        self.json = json_msg

    def __str__(self):
        return json.dumps(self.json, indent=2, sort_keys=True)



class OutMessage(object):
    """
    Hold sent messages and their timestamps so that their replies can be handled
    """

    def __init__(self, command, description, timestamp=None, data=None,
                 out_id=None):
        self.command = command
        self.description = description
        self.timestamp = timestamp
        self.data = data
        self.out_id = out_id

    def __str__(self):
        return self.description


class OutTracker(dict):
    """
    Holds all sent messages that are waiting for a reply
    """

    def __init__(self):
        super(OutTracker, self).__init__()
        self.mid_tracker = {}

    def add_message(self, message):
        """
        Add a message
        """

        self[message.out_id] = message

    def add_mid(self, mid, topic):
        """
        Add an MID with the topic it will send on
        """

        self.mid_tracker[mid] = topic

    def pop_message(self, topic_num, cmd_num):
        """
        Remove a single message
        """

        out_id = "{}-{}".format(topic_num, cmd_num)
        try:
            message = self.pop(out_id)
        except KeyError:
            raise KeyError("Message {} not found. May be a duplicate "
                           "reply".format(out_id))
        return message

    def pop_mid(self, mid):
        """
        Retrieve the topic an MID is sending on
        """
        try:
            pop_id = self.mid_tracker.pop(mid)
        except KeyError:
            raise KeyError("Message {} not found.".format(mid))
        return pop_id

class Publish(object):
    """
    Super Class for holding information about a pending publish
    """

    def __init__(self):
        self.timestamp = datetime.utcnow().strftime(constants.TIME_FORMAT)
        self.type = self.__class__.__name__


class PublishAlarm(Publish):
    """
    Holds information about an alarm
    """

    def __init__(self, name, state, message=None, republish=False):
        super(PublishAlarm, self).__init__()
        self.name = name
        self.state = state
        self.message = message
        self.republish = republish


class PublishAttribute(Publish):
    """
    Holds information about an attribute that is to be published
    """

    def __init__(self, name, value):
        super(PublishAttribute, self).__init__()
        self.name = name
        self.value = value


class PublishLocation(Publish):
    """
    Holds location information
    """

    def __init__(self, latitude, longitude, heading=None, altitude=None,
                 speed=None, accuracy=None, fix_type=None):
        super(PublishLocation, self).__init__()
        self.latitude = latitude
        self.longitude = longitude
        self.heading = heading
        self.altitude = altitude
        self.speed = speed
        self.accuracy = accuracy
        self.fix_type = fix_type

    def __str__(self):
        string = "latitude: {}, longitude: {}".format(self.latitude,
                                                      self.longitude)
        if self.heading:
            string += ", heading: {}".format(self.heading)
        if self.altitude:
            string += ", altitude: {}".format(self.altitude)
        if self.speed:
            string += ", speed: {}".format(self.speed)
        if self.accuracy:
            string += ", accuracy: {}".format(self.accuracy)
        if self.fix_type:
            string += ", fix type: {}".format(self.fix_type)
        return string


class PublishLog(Publish):
    """
    Holds a log message to be sent to the Cloud
    """

    def __init__(self, message):
        super(PublishLog, self).__init__()
        self.message = message


class PublishTelemetry(Publish):
    """
    Holds information about telemetry that is to be published
    """

    def __init__(self, name, value, timestamp=None, corr_id=None, aggregate=None):
        super(PublishTelemetry, self).__init__()
        if type(timestamp) is datetime:
            self.timestamp = timestamp.strftime(constants.TIME_FORMAT)
        self.name = name
        self.value = value
        self.corr_id = corr_id
        self.aggregate = aggregate


class Work(object):
    """
    Holds information about work that needs to be completed
    """

    def __init__(self, work_type, data):
        self.type = work_type
        self.data = data


