Device Cloud IDs
================
This document describes the identification strings used when
identifying an application over MQTT.

Description
-----------
Identification (ID) strings are used for unique identity and lower
level protocol sessions.  There are a few different IDs used to
identify an application:
  * think key
  * device ID
  * application ID
  * application token

Thing Key
---------
Everything that is connected to the cloud requires a
unique key.  The thing_key represents an application like the
device_manager.py in the cloud.  An example of a thing_key is:
  * 07e4cfc1-9aa2-4af2-93a6-e1143b3ece36-device_manager_py

By default the thing key is composed to two parts:
  * *device ID-application ID*

The thing_key is used during MQTT authentication as the *username*.
The thing_key must be <= 64 bytes.

Device ID
---------
The device ID must be unique.  An example device ID is:
  * 07e4cfc1-9aa2-4af2-93a6-e1143b3ece36

It can be anything, but by default a UUID is used.  The device ID is
read from a file *config_dir*/device_id.  If the file exists, whatever
is in that file is used as the device ID.  The device_id file must not
contain a line break.  Some implementations may choose to use a MAC
address, IMEI or other serial number that is unique.  To override the
default behaviour, write to device_id before starting an application
e.g. device_manager.py.  This is typically done at provisioning time.

Note: the method used to generate the device_id can be overridden in
the identity.py class.  See documentation in:
```sh
pydoc device_cloud/identity.py
```

Application ID
--------------
An application ID is the string that describes the application.  It
must be unique on the device.  An example application ID is:
  * device_manager_py

This string is passed into the client at initialization time:
```
client = iot.Client(app_id)
```
The application ID is part of the thing key.

Application Token
-----------------
The application token is 64 bit string that is generated in the cloud.
An administrator has the credentials to query and obtain the
application token for you application.  This token can be used by many
devices that have the same functionality and role.  This token is used
when generating a cloud configuration file, e.g. when running:
  * generate_config.py

The token maps back to a thing definition, role and security group in
the cloud.  The token is used during MQTT authentication as the
*password*.

Client ID
---------
AKA the application ID.
