"""
This module handles all the underlying functionality of the Client
"""

import fnmatch
import json
import logging
import os
import Queue
import random
import ssl
import threading
from binascii import crc32
from datetime import datetime
from datetime import timedelta
from time import sleep
import requests
import paho.mqtt.client as mqttlib

from hdcpython import constants
from hdcpython import defs
from hdcpython import tr50
from hdcpython.tr50 import TR50Command


def status_string(error_code):
    """
    Return a string describing the error code
    """

    return constants.STATUS_STRINGS[error_code]

def is_valid_status(error_code):
    """
    Check if passed object is a valid status code
    """

    return (error_code.__class__.__name__ == "int" and
            error_code >= constants.STATUS_SUCCESS and
            error_code <= constants.STATUS_FAILURE)


class Handler(object):
    """
    Handles all underlying functionality of the Client
    """

    def __init__(self, config, client):
        # Configuration
        self.config = config

        # Set Client
        self.client = client

        # Set up logging, with optional logging to a specified file
        if self.config.key:
            self.logger = logging.getLogger(self.config.key)
        else:
            self.logger = logging.getLogger("APP NAME HERE")
        log_formatter = logging.Formatter(constants.LOG_FORMAT)
        log_handler = logging.StreamHandler()
        log_handler.setFormatter(log_formatter)
        self.logger.addHandler(log_handler)
        if self.config.log_file:
            log_file_handler = logging.FileHandler(self.config.log_file)
            log_file_handler.setFormatter(log_formatter)
            self.logger.addHandler(log_file_handler)
        self.logger.setLevel(logging.DEBUG)

        # Ensure we're not missing required configuration information
        if not self.config.key or not self.config.cloud_token:
            self.logger.error("Missing key or cloud token from configuration")
            raise KeyError("Missing key or cloud token from configuration")

        # Print configuration
        for key in self.config:
            self.logger.debug("Config: %s %s", key, self.config[key])

        # Set up MQTT client
        self.mqtt = mqttlib.Client(self.config.key)
        self.mqtt.on_connect = self.on_connect
        self.mqtt.on_disconnect = self.on_disconnect
        self.mqtt.on_message = self.on_message
        self.mqtt.username_pw_set(self.config.key, self.config.cloud_token)

        # Dict to associate action names with callback functions and any user
        # data
        self.callbacks = defs.Callbacks()

        # Connection state of the Client
        self.state = constants.STATE_DISCONNECTED

        # Lock for thread safety
        self.lock = threading.Lock()

        # Queue for any pending publishes (number, string, location, etc.)
        self.publish_queue = Queue.Queue()

        # Dicts to track which messages sent out have not received replies. Also
        # stores any actions to be taken when the reply is received.
        self.reply_tracker = defs.OutTracker()
        self.no_reply = []

        # Counter to allow every message to be sent on a unique topic
        self.topic_counter = 1

        # Thread trackers. Main thread for handling MQTT loop, and worker
        # threads for everything else.
        self.main_thread = None
        self.worker_threads = []

        # Queue to track any pending work (parsing messages, actions,
        # publishing, file transfer, etc.)
        self.work_queue = Queue.Queue()

    def action_deregister(self, action_name):
        """
        Disassociate any function or command from an action in the Cloud
        """

        status = constants.STATUS_SUCCESS

        try:
            self.callbacks.remove_action(action_name)
        except KeyError as error:
            self.logger.error(str(error))
            status = constants.STATUS_NOT_FOUND

        return status

    def action_register_callback(self, action_name, callback_function,
                                 user_data=None):
        """
        Associate a callback function with an action in the Cloud
        """

        status = constants.STATUS_SUCCESS
        action = defs.Action(action_name, callback_function, self.client,
                             user_data=user_data)
        try:
            self.callbacks.add_action(action)
            self.logger.info("Registered action \"%s\" with function \"%s\"",
                             action_name, callback_function.__name__)
        except KeyError as error:
            self.logger.error("Failed to register action. %s", str(error))
            status = constants.STATUS_EXISTS

        return status

    def action_register_command(self, action_name, command):
        """
        Associate a console command with an action in the Cloud
        """

        status = constants.STATUS_SUCCESS
        action = defs.ActionCommand(action_name, command, self.client)
        try:
            self.callbacks.add_action(action)
            self.logger.info("Registered action \"%s\" with command \"%s\"",
                             action_name, command)
        except KeyError as error:
            self.logger.error("Failed to register action. %s", str(error))
            status = constants.STATUS_EXISTS

        return status

    def connect(self, timeout=0):
        """
        Connect to MQTT and start main thread
        """

        status = constants.STATUS_FAILURE

        # Ensure we have a host and port to connect to
        if not self.config.cloud_host or not self.config.cloud_port:
            self.logger.error("Missing host or port from configuration")
            raise KeyError("Missing host or port from configuration")

        current_time = datetime.utcnow()
        end_time = current_time + timedelta(seconds=timeout)
        self.state = constants.STATE_CONNECTING

        # Start a secure connection if the cert file is available
        if self.config.ca_bundle_file:
            self.mqtt.tls_set(self.config.ca_bundle_file,
                              tls_version=ssl.PROTOCOL_TLSv1_2)

        # Start MQTT connection
        result = self.mqtt.connect(self.config.cloud_host,
                                   self.config.cloud_port, 60)

        if result == 0:
            # Successful MQTT connection
            self.logger.info("Connecting...")

            # Start main loop thread so that MQTT can make the on_connect
            # callback
            self.main_thread = threading.Thread(target=self.main_loop)
            self.main_thread.start()

            # Wait for cloud connection
            while ((timeout == 0 or current_time < end_time) and
                   self.state == constants.STATE_CONNECTING):
                sleep(1)
                current_time = datetime.utcnow()

            # Still connecting, timed out
            if self.state == constants.STATE_CONNECTING:
                self.logger.error("Connection timed out")
                status = constants.STATUS_TIMED_OUT

        if self.state == constants.STATE_CONNECTED:
            # Connected Successfully
            status = constants.STATUS_SUCCESS
        else:
            # Not connected. Stop main loop.
            self.logger.error("Failed to connect")
            self.state = constants.STATE_DISCONNECTED
            self.main_thread.join()

        # Return result of connection
        return status

    def disconnect(self, wait_for_replies=False, timeout=0):
        """
        Stop threads and shut down MQTT client
        """

        current_time = datetime.utcnow()
        end_time = current_time + timedelta(seconds=timeout)

        # Optionally wait for any outstanding replies. Any that timeout will be
        # removed so that this loop can end.
        if wait_for_replies:
            self.logger.info("Waiting for replies...")
            while ((timeout == 0 or current_time < end_time) and
                   len(self.reply_tracker) != 0):
                sleep(1)
                current_time = datetime.utcnow()

        # Disconnect MQTT and wait for main thread, which in turn waits for
        # worker threads
        self.logger.info("Disconnecting...")
        self.mqtt.disconnect()
        while ((timeout == 0 or current_time < end_time) and
               self.state == constants.STATE_CONNECTED):
            sleep(1)
            current_time = datetime.utcnow()

        # Wait for pending work that has not been dealt with
        while ((timeout == 0 or current_time < end_time) and
               not self.work_queue.empty()):
            sleep(1)
            current_time = datetime.utcnow()

        self.state = constants.STATE_DISCONNECTED
        #TODO: Kill any hanging threads
        self.main_thread.join()

        return constants.STATUS_SUCCESS

    def handle_action(self, action_request):
        """
        Handle action execution requests from Cloud
        """

        result_code = -1
        result_args = {"mail_id":action_request.request_id}
        action_result = None
        action_failed = False

        try:
            # Execute callback
            action_result = self.callbacks.execute_action(action_request)

        except Exception as error:
            # Error with action execution. Might not have been registered.
            action_failed = True
            self.logger.error("Action %s execution failed", action_request.name)
            self.logger.error(".... %s", str(error))
            result_code = constants.STATUS_FAILURE
            result_args["error_message"] = "ERROR: {}".format(str(error))
            if action_request.name not in self.callbacks:
                result_code = constants.STATUS_NOT_FOUND
            else:
                self.logger.exception("Exception:")

        # Action execution did not raise an error
        if not action_failed:
            # Handle returning a tuple or just a status code
            if action_result.__class__.__name__ == "tuple":
                result_code = action_result[0]
                if len(action_result) >= 2:
                    result_args["error_message"] = str(action_result[1])
                if len(action_result) >= 3:
                    result_args["params"] = action_result[2]
            else:
                result_code = action_result

            if not is_valid_status(result_code):
                # Returned 'status' is not a valid status
                error_string = ("Invalid return status: " +
                                str(result_code))
                self.logger.error(error_string)
                result_code = constants.STATUS_BAD_PARAMETER
                result_args["error_message"] = "ERROR: " + error_string

        # Return status to Cloud
        result_args["error_code"] = tr50.translate_error_code(result_code)
        mailbox_ack = tr50.create_mailbox_ack(**result_args)

        message_desc = "Action Complete \"{}\"".format(action_request.name)
        message_desc += " result : {}({})".format(result_code,
                                                  status_string(result_code))
        if result_args.get("error_message"):
            message_desc += " \"{}\"".format(result_args["error_message"])
        if result_args.get("params"):
            message_desc += " \"{}\"".format(str(result_args["params"]))
        message = defs.OutMessage(mailbox_ack, message_desc)
        status = self.send(message)

        return status

    def handle_file_download(self, download):
        """
        Handle any accepted C2D file transfers
        """
        #TODO: Timeout

        status = constants.STATUS_SUCCESS
        self.logger.info("Downloading \"%s\"", download.file_name)

        # Start creating URL for file download
        url = "{}/file/{}".format(self.config.cloud_host, download.file_id)

        # Download directory
        download_dir = os.path.join(self.config.runtime_dir, "download")
        # Temporary file name while downloading
        temp_file_name = "".join([random.choice("0123456789") for _ in range(10)])
        temp_file_name += ".part"
        temp_path = os.path.join(download_dir, temp_file_name)

        # Path where temporary file will be moved to
        real_path = os.path.join(download_dir, download.file_name)

        # Ensure download directory exists
        if not os.path.isdir(download_dir):
            self.logger.error("Cannot find download directory \"%s\". "
                              "Download cancelled.", download_dir)
            status = constants.STATUS_NOT_FOUND

        if status == constants.STATUS_SUCCESS:
            # Secure or insecure HTTP request.
            response = None
            if self.config.ca_bundle_file:
                url = "https://" + url
                cert_location = self.config.ca_bundle_file
                response = requests.get(url, stream=True,
                                        verify=cert_location)
            else:
                url = "http://" + url
                response = requests.get(url, stream=True)

            if response.status_code == 200:
                # Write to temporary file
                with open(temp_path, "wb") as temp_file:
                    for chunk in response.iter_content(512):
                        temp_file.write(chunk)
                status = constants.STATUS_SUCCESS
            else:
                # Request was unsuccessful
                self.logger.error("Failed to download \"%s\" (download error)",
                                  download.file_name)
                self.logger.error(".... %s", response.content)
                status = constants.STATUS_FAILURE

            if status == constants.STATUS_SUCCESS:
                # Ensure the downloaded file matches the checksum sent by the
                # Cloud.
                checksum = 0
                with open(temp_path, "rb") as temp_file:
                    for chunk in temp_file:
                        checksum = crc32(chunk, checksum)
                    checksum = checksum & 0xffffffff
                if checksum == download.file_checksum:
                    # Checksums match, move temporary file to real file position
                    os.rename(temp_path, real_path)
                    self.logger.info("Successfully downloaded \"%s\"",
                                     download.file_name)
                else:
                    # Checksums do not match, remove temporary file and fail
                    os.remove(temp_path)
                    self.logger.error("Failed to download \"%s\" "
                                      "(checksums do not match)",
                                      download.file_name)
                    status = constants.STATUS_FAILURE

            # Update file transfer status
            download.status = status

        return status

    def handle_file_upload(self, upload):
        """
        Handle any accepted D2C file transfers
        """

        #TODO: Timeout

        status = constants.STATUS_SUCCESS

        self.logger.info("Uploading \"%s\"", upload.file_name)

        # Start creating URL for file upload
        url = "{}/file/{}".format(self.config.cloud_host, upload.file_id)

        # Upload directory
        upload_dir = os.path.join(self.config.runtime_dir, "upload")
        # Path of file to upload
        file_path = os.path.join(upload_dir, upload.file_name)

        # Ensure upload directory exists
        if not os.path.isdir(upload_dir):
            self.logger.error("Cannot find upload directory \"%s\". "
                              "Upload cancelled.", upload_dir)
            status = constants.STATUS_NOT_FOUND

        if status == constants.STATUS_SUCCESS:
            # If file exists attempt upload
            response = None
            if os.path.exists(file_path):
                with open(file_path, "rb") as up_file:
                    # Secure or insecure HTTP Post
                    if self.config.ca_bundle_file:
                        url = "https://" + url
                        cert_location = self.config.ca_bundle_file
                        response = requests.post(url, data=up_file,
                                                 verify=cert_location)
                    else:
                        url = "http://" + url
                        response = requests.post(url, data=up_file)
                if response.status_code == 200:
                    self.logger.info("Successfully uploaded \"%s\"",
                                     upload.file_name)
                    status = constants.STATUS_SUCCESS
                else:
                    self.logger.error("Failed to upload \"%s\"",
                                      upload.file_name)
                    self.logger.debug(".... %s", response.content)
                    status = constants.STATUS_FAILURE

            else:
                # File does not exist
                self.logger.error("File \"%s\" does not exist, cannot upload",
                                  upload.file_name)
                status = constants.STATUS_NOT_FOUND

            # Update file transfer status
            upload.status = status

        return status

    def handle_message(self, mqtt_message):
        """
        Handle messages received from Cloud
        """

        status = constants.STATUS_NOT_SUPPORTED

        msg_json = mqtt_message.json
        if "notify/" in mqtt_message.topic:
            # Received a notification
            if mqtt_message.topic[len("notify/"):] == "mailbox_activity":
                # Mailbox activity, send a request to check the mailbox
                self.logger.info("Recevied notification of mailbox activity")
                mailbox_check = tr50.create_mailbox_check(auto_complete=False)
                to_send = defs.OutMessage(mailbox_check, "Mailbox Check")
                self.send(to_send)
                status = constants.STATUS_SUCCESS

        elif "reply/" in mqtt_message.topic:
            # Received a reply to a previous message
            topic_num = mqtt_message.topic[len("reply/"):]
            for command_num in msg_json:
                reply = msg_json[command_num]

                # Retrieve the sent message that this is a reply for, removing
                # it from being tracked
                self.lock.acquire()
                try:
                    sent_message = self.reply_tracker.pop_message(topic_num,
                                                                  command_num)
                except KeyError as error:
                    raise error
                finally:
                    self.lock.release()
                sent_command_type = sent_message.command.get("command")

                # Log success status of reply
                if reply.get("success"):
                    self.logger.info("Received success for %s-%s - %s",
                                     topic_num, command_num, sent_message)
                else:
                    self.logger.error("Received failure for %s-%s - %s",
                                      topic_num, command_num, sent_message)
                    self.logger.error(".... %s", str(reply))

                # Check what kind of message this is a reply to
                if sent_command_type == TR50Command.file_get:
                    # Recevied a reply for a file download request
                    if reply.get("success"):
                        file_id = reply["params"].get("fileId")
                        file_checksum = reply["params"].get("crc32")
                        file_transfer = sent_message.data
                        file_transfer.file_id = file_id
                        file_transfer.file_checksum = file_checksum
                        work = defs.Work(constants.WORK_DOWNLOAD, file_transfer)
                        self.queue_work(work)
                    else:
                        sent_message.data.status = constants.STATUS_FAILURE

                elif sent_command_type == TR50Command.file_put:
                    # Received a reply for a file upload request
                    if reply.get("success"):
                        file_id = reply["params"].get("fileId")
                        file_transfer = sent_message.data
                        file_transfer.file_id = file_id
                        work = defs.Work(constants.WORK_UPLOAD, file_transfer)
                        self.queue_work(work)
                    else:
                        sent_message.data.status = constants.STATUS_FAILURE

                elif sent_command_type == TR50Command.mailbox_check:
                    # Received a reply for a mailbox check
                    if reply.get("success"):
                        for mail in reply["params"]["messages"]:
                            mail_command = mail.get("command")
                            if mail_command == "method.exec":
                                # Action execute request in mailbox
                                mail_id = mail.get("id")
                                action_name = mail["params"].get("method")
                                action_params = mail["params"].get("params")
                                action_request = defs.ActionRequest(mail_id,
                                                                    action_name,
                                                                    action_params)
                                work = defs.Work(constants.WORK_ACTION,
                                                 action_request)
                                self.queue_work(work)

            status = constants.STATUS_SUCCESS

        return status

    def handle_publish(self):
        """
        Publish any pending publishes in the publish queue, or the cloud logger
        """

        status = constants.STATUS_SUCCESS

        # Collect all pending publishes in publish queue
        to_publish = []
        while not self.publish_queue.empty():
            try:
                to_publish.append(self.publish_queue.get())
            except Queue.Empty:
                break

        if to_publish:
            # If pending publishes are found, parse into list for sending
            messages = []
            for pub in to_publish:

                # Create publish command for an alarm
                if pub.type == "PublishAlarm":
                    command = tr50.create_alarm_publish(self.config.key,
                                                        pub.name, pub.state,
                                                        message=pub.message,
                                                        timestamp=pub.timestamp)
                    message_desc = "Alarm Publish {}".format(pub.name)
                    message_desc += " : {}".format(pub.state)
                    message = defs.OutMessage(command, message_desc)

                # Create publish command for strings
                elif pub.type == "PublishAttribute":
                    command = tr50.create_attribute_publish(self.config.key,
                                                            pub.name, pub.value,
                                                            timestamp=pub.timestamp)
                    message_desc = "Attribute Publish {}".format(pub.name)
                    message_desc += " : \"{}\"".format(pub.value)
                    message = defs.OutMessage(command, message_desc)

                # Create publish command for numbers
                elif pub.type == "PublishTelemetry":
                    command = tr50.create_property_publish(self.config.key,
                                                           pub.name, pub.value,
                                                           timestamp=pub.timestamp)
                    message_desc = "Property Publish {}".format(pub.name)
                    message_desc += " : {}".format(pub.value)
                    message = defs.OutMessage(command, message_desc)

                # Create publish command for location
                elif pub.type == "PublishLocation":
                    command = tr50.create_location_publish(self.config.key,
                                                           pub.latitude,
                                                           pub.longitude,
                                                           heading=pub.heading,
                                                           altitude=pub.altitude,
                                                           speed=pub.speed,
                                                           fix_accuracy=pub.accuracy,
                                                           fix_type=pub.fix_type,
                                                           timestamp=pub.timestamp)
                    message_desc = "Location Publish {}".format(str(pub))
                    message = defs.OutMessage(command, message_desc)

                # Create publish command for a log
                elif pub.type == "PublishLog":
                    command = tr50.create_log_publish(self.config.key,
                                                      pub.message,
                                                      timestamp=pub.timestamp)
                    message_desc = "Log Publish {}".format(pub.message)
                    message = defs.OutMessage(command, message_desc)

                messages.append(message)

            # Send all publishes
            status = self.send(messages)
        return status

    def handle_work_loop(self):
        """
        Loop for worker threads to handle any items put on the work queue
        """

        # Continuously loop while connected
        while self.is_connected():
            work = None
            try:
                work = self.work_queue.get(timeout=self.config.loop_time)
            except Queue.Empty:
                pass
            # If work is retrieved from the queue, handle it based on type
            if work:
                try:
                    if work.type == constants.WORK_MESSAGE:
                        self.handle_message(work.data)
                    elif work.type == constants.WORK_PUBLISH:
                        self.handle_publish()
                    elif work.type == constants.WORK_ACTION:
                        self.handle_action(work.data)
                    elif work.type == constants.WORK_DOWNLOAD:
                        self.handle_file_download(work.data)
                    elif work.type == constants.WORK_UPLOAD:
                        self.handle_file_upload(work.data)
                except Exception:
                    # Print traceback, but don't kill thread
                    self.logger.exception("Exception:")

        return constants.STATUS_SUCCESS

    def is_connected(self):
        """
        Returns connection status of Client to Cloud
        """

        return self.state == constants.STATE_CONNECTED

    def main_loop(self):
        """
        Main loop for MQTT to send and receive messages, as well as queue work
        for publishing and checking timeouts
        """

        # Continuously loop while connected or connecting
        while (self.state == constants.STATE_CONNECTED or
               self.state == constants.STATE_CONNECTING):
            self.mqtt.loop(timeout=self.config.loop_time)
            current_time = datetime.utcnow()

            self.lock.acquire()
            try:
                # Check if any messages have timed out with no reply
                max_timeout = self.config.message_timeout
                removed = self.reply_tracker.time_out(current_time, max_timeout)

                # Log any timed out messages
                if len(removed) > 0:
                    self.logger.error("Message(s) timed out:")
                for remove in removed:
                    self.logger.error(".... %s", remove.description)
            finally:
                self.lock.release()

            # Make a work item to publish anything that's pending
            if not self.publish_queue.empty():
                work = defs.Work(constants.WORK_PUBLISH, None)
                self.work_queue.put(work)

        # On disconnect, show all timed out messages
        if self.no_reply:
            self.logger.error("These messages never received a reply:")
            for message in self.no_reply:
                self.logger.error(".... %s - %s", message.out_id,
                                  message.description)

        return constants.STATUS_SUCCESS

    def on_connect(self, mqtt, userdata, flags, rc):
        """
        Callback when MQTT Client connects to Cloud
        """

        # Check connection result from MQTT
        self.logger.info("MQTT connected: %s", mqttlib.connack_string(rc))
        if rc == 0:
            self.state = constants.STATE_CONNECTED
        else:
            self.state = constants.STATE_DISCONNECTED

        # Start worker threads if we have successfully connected
        if self.state == constants.STATE_CONNECTED:
            for _ in range(self.config.thread_count):
                self.worker_threads.append(threading.Thread(
                    target=self.handle_work_loop))
            for thread in self.worker_threads:
                thread.start()

    def on_disconnect(self, mqtt, userdata, rc):
        """
        Callback when MQTT Client disconnects from Cloud
        """

        self.logger.info("MQTT disconnected %d", rc)
        self.state = constants.STATE_DISCONNECTED
        # Wait for worker threads to finish.
        for thread in self.worker_threads:
            thread.join()

    def on_message(self, mqtt, userdata, msg):
        """
        Callback when MQTT Client receives a message
        """

        self.logger.debug("Received message on topic \"%s\"", msg.topic)
        self.logger.debug(".... %s", msg.payload)

        # Queue work to handle received message. Don't block main loop with this
        # task.
        message = defs.Message(msg.topic, json.loads(msg.payload))
        work = defs.Work(constants.WORK_MESSAGE, message)
        self.queue_work(work)

    def queue_publish(self, pub):
        """
        Place pub in the publish queue
        """

        self.publish_queue.put(pub)
        return constants.STATUS_SUCCESS

    def queue_work(self, work):
        """
        Place work in the work queue
        """

        self.work_queue.put(work)
        return constants.STATUS_SUCCESS

    def request_download(self, file_name, blocking=False, timeout=0):
        """
        Request a C2D file transfer
        """

        current_time = datetime.utcnow()
        end_time = current_time + timedelta(seconds=timeout)

        self.logger.info("Request download of %s", file_name)

        # File Transfer object for tracking progress
        transfer = defs.FileTransfer(file_name)

        # Generate and send message to request file transfer
        command = tr50.create_file_get(self.config.key, file_name)
        message = defs.OutMessage(command, "Download {}".format(file_name),
                                  data=transfer)
        status = self.send(message)

        # If blocking is set, wait for result of file transfer
        if status == constants.STATUS_SUCCESS and blocking:
            while ((timeout == 0 or current_time < end_time) and
                   transfer.status is None):
                sleep(1)
                current_time = datetime.utcnow()

            if transfer.status is None:
                status = constants.STATUS_TIMED_OUT
            else:
                status = transfer.status

        return status

    def request_upload(self, file_filter, blocking=False, timeout=0):
        """
        Request a D2C file transfer
        """

        status = constants.STATUS_SUCCESS
        current_time = datetime.utcnow()
        end_time = current_time + timedelta(seconds=timeout)
        transfer = None

        self.logger.info("Request upload of %s", file_filter)

        # Check to make sure upload directory exists
        upload_dir = os.path.join(self.config.runtime_dir, "upload")
        if os.path.isdir(upload_dir):

            # Get a list of all matching files to upload
            files = [f for f in os.listdir(upload_dir) if
                     os.path.isfile(os.path.join(upload_dir, f))]
            files = fnmatch.filter(files, file_filter)

            transfers = []
            for file_name in files:
                # Get file crc32 checksum
                checksum = 0
                up_file_path = os.path.join(upload_dir, file_name)
                with open(up_file_path, "rb") as up_file:
                    for chunk in up_file:
                        checksum = crc32(chunk, checksum)
                checksum = checksum & 0xffffffff

                if checksum != 0:
                    # File Transfer object for tracking progress
                    transfer = defs.FileTransfer(file_name)

                    # Generate and send message to request file transfer
                    command = tr50.create_file_put(self.config.key, file_name)
                    message_desc = "Upload {}".format(file_name)
                    message = defs.OutMessage(command, message_desc,
                                              data=transfer)
                    status = self.send(message)
                    transfers.append(transfer)
                else:
                    self.logger.error("Upload request failed. Failed to "
                                      "retrieve checksum for \"%s\".",
                                      file_name)
                    status = constants.STATUS_FAILURE
                    break

        else:
            # Upload directory not found
            self.logger.error("Cannot find upload directory \"%s\". "
                              "Upload cancelled.", upload_dir)
            status = constants.STATUS_NOT_FOUND

        # If blocking is set, wait for result of file transfer
        if transfers and status == constants.STATUS_SUCCESS and blocking:
            while ((timeout == 0 or current_time < end_time) and
                   len(transfers) != 0) and self.is_connected():
                if transfers[0].status is not None:
                    transfers.pop(0)
                else:
                    sleep(1)
                current_time = datetime.utcnow()

            if len(transfers) != 0:
                status = constants.STATUS_TIMED_OUT
            else:
                status = constants.STATUS_SUCCESS

        return status

    def send(self, messages):
        """
        Send commands to the Cloud, and track them to wait for replies
        """

        status = constants.STATUS_FAILURE

        message_list = messages
        if messages.__class__.__name__ != "list":
            message_list = [messages]

        # Generate final request string
        payload = tr50.generate_request([x.command for x in message_list])

        # Lock to ensure all outgoing messages are tracked before handling
        # received messages
        self.lock.acquire()
        try:
            # Obtain new unused topic number
            while True:
                topic_num = "{:0>4}".format(self.topic_counter)
                self.topic_counter += 1
                if topic_num not in self.reply_tracker:
                    break

            # Send payload over MQTT
            result, mid = self.mqtt.publish("api/{}".format(topic_num),
                                            payload, 1)

            if result == 0:
                status = constants.STATUS_SUCCESS

                # Track outgoing messages
                current_time = datetime.utcnow()

                # Track each message
                #for i in range(len(message_list)):
                for num, msg in enumerate(message_list):

                    # Add timestamps and ids
                    msg.timestamp = current_time
                    msg.timestamp = current_time
                    msg.out_id = "{}-{}".format(topic_num, num+1)

                    self.reply_tracker.add_message(msg)
                    self.logger.info("Sending %s-%d - %s", topic_num, num+1,
                                     msg)
                    self.logger.debug(".... %s", msg.command)
        finally:
            self.lock.release()

        return status
