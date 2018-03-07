Description
===========
The device manager will publish an attribute called
"remote_access_support" with a value defind below.  The iot.cfg will
contain the configuration details.  Once the device_manager.py is run,
it will read the iot.cfg and publish an attribute where the content is
a list of services and ports that it supports. The goal is that this
attribute "remote_access_support" will be used by the UI to setup a
remote session.  If the device does not publish the attribute, then
the device is assumed to not support remote access.

Requirements
------------
  * the content of the attribute will be a json string
  * device manager will read the iot.cfg for remote access protocols
  * device manager must build an attribute based on the settings in
    the iot.cfg
  * device manager will publish an attribute called "remote_access_support"
  * the protocol name will be used by the UI to display the type of
  service
  * the port will be used to connect to the device
  * optional parameters for a maximum session timeout will be used as
  hints or defaults in the UI
 

JSON String Published As Attribute
----------------------------------
The following is published as a JSON string:
(added white space for readability)
```
[
	{ "protocol": "Telnet", "port": "23", "session_timeout": "60" },
	{ "protocol": "SSH", "port": "22" }, 
	{ "protocol": "VNC", "port": "5900" },
	{ "protocol": "HTTP", "port": "80" }
]    
```

Changes To iot.cfg 
------------------
```
	"remote_access_support":[
		{ "name": "Telnet", "port":"23", "session_timeout":"120", "status":true },
		{ "name": "SSH",    "port":"22",   "status":true },
		{ "name": "VNC",    "port":"5900", "status":true },
		{ "name": "HTTP",   "port":"80",   "status":true }
	]
```

Required paramters:
  * name: name of the protocol to display in the UI
  * port: port that is bound on the device
  * status: if true, then publish the service in the attribute
Optional parameters:
  * session_timeout in minutes:
