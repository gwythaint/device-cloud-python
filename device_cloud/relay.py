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
This module contains the Relay class which is a secure way to pipe data to a
local socket connection. This is useful for Telnet which is not secure by
default.
"""

import logging
import random
import select
import socket
import ssl
import threading
import time
# -------------------------------------------------------------------
# Note: when using a proxy server, the socket class is overlayed with
# pysocks class.  Keep around a local copy so that local socket
# connections don't use the proxy
# -------------------------------------------------------------------
non_proxy_socket = None

# yocto supports websockets, not websocket, so check for that
try:
    import websocket
except ImportError:
    import websockets as websocket

CONNECT_MSG = "CONNECTED-129812"

class Relay(object):
    """
    Class for establishing a secure pipe between a cloud based websocket and a
    local socket. This is useful for things like Telnet which are not secure to
    use remotely.
    """

    def __init__(self, wsock_host, sock_host, sock_port, secure=True,
                 log=None, local_socket=None, reconnect=False):
        """
        Initialize a relay object for piping data between a websocket and a
        local socket
        """

        self.wsock_host = wsock_host
        self.sock_host = sock_host
        self.sock_port = sock_port
        self.secure = secure
        self.log = log
        self.log_name = "Relay:{}:{}({:0>5})".format(self.sock_host,
                                                    self.sock_port,
                                                    random.randint(0,99999))
        self.reconnect = reconnect

        if self.log is None:
            self.logger = logging.getLogger(self.log_name)
            log_handler = logging.StreamHandler()
            #log_formatter = logging.Formatter(constants.LOG_FORMAT, datefmt=constants.LOG_TIME_FORMAT)
            #log_handler.setFormatter(log_formatter)
            self.logger.addHandler(log_handler)
            self.logger.setLevel(logging.DEBUG)
            self.log = self.logger.log

        self.running = False
        self.thread = None
        self.lsock = None
        self.wsock = None

    def _loop(self):
        """
        Main loop that pipes all data from one socket to the next. The websocket
        connection is established first so this is also where the local socket
        connection will be started when a specific string is received from the
        Cloud
        """
        op_code_ping = 0x9
        def _connect_local(self, socket_list):
            ret = False
            try:
                # check for proxy.  If not proxy, this
                # is None.
                if non_proxy_socket:
                    self.lsock = non_proxy_socket(socket.AF_INET,
                                           socket.SOCK_STREAM)
                else:
                    self.lsock = socket.socket(socket.AF_INET,
                                           socket.SOCK_STREAM)
                    self.lsock.setblocking(0)
                    socket_list.append(self.lsock)

                    # disable nagle
                    self.lsock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, True)
                self.lsock.connect((self.sock_host,
                                    self.sock_port))
            except socket.error:
                self.running = False
                ret = True
                self.log(logging.ERROR,
                         "%s - Failed to open local socket",
                         self.log_name)
            return ret

        lconnect = 0;
        ws_empty_count = 0
        ws_max_empty_check = 5
        select_timeout = 1
        while self.running is True:
            socket_list = [self.wsock]
            write_list = []
            if self.lsock:
                socket_list.append(self.lsock)

            read_sockets, write_sockets, _es = select.select(socket_list,
                                                 [], [], select_timeout)

            # --------------------------------------------------------
            # Workaround for websocket module.  select shows 0 sockets
            # ready, but in fact there is a ws pkt waiting.  To force
            # the select, append the wsock to the read_sockets list.
            # 
            # --------------------------------------------------------
            if ws_empty_count == ws_max_empty_check:
                #self.wsock.ping("PING")
                read_sockets.append(self.wsock)
                ws_empty_count = 0
            if len(read_sockets) ==0:
                ws_empty_count += 1

            for sock in read_sockets:
                if sock == self.wsock:
                    try:
                        op, data_in = sock.recv_data()
                        self.log(logging.DEBUG, "WS read {}".format(len(data_in)))
                        
                        # ------------------------------------------
                        # handle websocket ping op code
                        # ------------------------------------------
                        if op == op_code_ping:
                            self.log(logging.INFO, "Received ping, answering")
                            self.wsock.pong(data_in)
                            continue
                    except websocket.WebSocketConnectionClosedException:
                        self.running = False
                        break
                    if data_in:
                        if self.lsock:
                            self.lsock.send(data_in)
                            #self.log(logging.DEBUG, "LS sent{}".format(len(data_in)))
                        elif lconnect == 0 and data_in.decode('ascii') == CONNECT_MSG:
                            # If the local socket has not been established yet,
                            # and we have received the connection string, start
                            # local socket.
                            if _connect_local(self, socket_list):
                                break
                            lconnect = 1;
                            self.log(logging.INFO,
                                    "%s - Local socket successfully opened",
                                     self.log_name)
                    else:
                        self.log(logging.INFO,
                                 "%s - Received NULL from websocket, Stopping",
                                 self.log_name)
                        self.running = False
                        break
                else:
                    data_in = sock.recv(4096)
                    #self.log(logging.DEBUG,"LS recv {}".format(len(data_in)))
                    if data_in:
                        self.wsock.send_binary(data_in)
                        #self.log(logging.DEBUG,"LS sent {}".format(len(data_in)))
                    else:
                        self.log(logging.INFO,
                             "%s - Received NULL from local socket, reconnecting",
                             self.log_name)
                        if self.reconnect:
                            print("Reconnecting local socket")
                            time.sleep(2)
                            _connect_local(self, socket_list)
                        else:
                            self.running = False
                            break
        if self.lsock:
            self.lsock.close()
            self.lsock = None
        self.wsock.close()
        self.wsock = None
        self.log(logging.INFO, "%s - Sockets Closed", self.log_name)

    def start(self):
        """
        Establish the websocket connection and start the main loop
        """

        if not self.running:
            self.running = True

            sslopt = {}
            if not self.secure:
                sslopt["cert_reqs"] = ssl.CERT_NONE

            # Connect websocket to Cloud
            self.wsock = websocket.WebSocket(sslopt=sslopt)
            try:
                self.wsock.connect(self.wsock_host)
            except ssl.SSLError as error:
                self.running = False
                self.wsock.close()
                self.wsock = None
                self.log(logging.ERROR, "%s - Failed to open Websocket",
                         self.log_name)
                raise error

            self.log(logging.INFO, "%s - Websocket Opened", self.log_name)

            self.thread = threading.Thread(target=self._loop)
            self.thread.start()

        else:
            raise RuntimeError("{} - Already running!".format(self.log_name))

    def stop(self):
        """
        Stop piping data between the two connections and stop the loop thread
        """

        self.log(logging.INFO, "%s - Stopping", self.log_name)
        self.running = False
        self.reconnect = False
        if self.thread:
            self.thread.join()
            self.thread = None


relays = []

def create_relay(url, host, port, secure=True, log_func=None, local_socket=None,
                 reconnect=False):
    global relays, non_proxy_socket

    non_proxy_socket = local_socket
    newrelay = Relay(url, host, port, secure=secure, log=log_func, reconnect=reconnect)
    newrelay.start()
    relays.append(newrelay)

def stop_relays():
    global relays

    threads = []
    while relays:
        relay = relays.pop()
        thread = threading.Thread(target=relay.stop)
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()

