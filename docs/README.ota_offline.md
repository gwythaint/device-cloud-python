Description
===========
In order to support the use case where an OTA package has been
downloaded with the intent to install it manually.  The OTA process in
offline mode is functionally equivalent to the online work flow,
except that there is no cloud communication.  A wrapper utility called
"offline_ota_handler.py" is provided to instantiate the ota_handler
and client classes.

Usage
-----
This work flow expects an OTA package to reside in the
$runtime/download directory.  E.g. a file download operation has been
executed from the cloud for the OTA package, i.e. downloaded only.

Here is the directory hierarchy expected:
```
offline_ota_handler.py
runtime/
├── download
│   └── ota-package.tar.gz
└── upload
```

Run the offline install tool:
Note: a fake connection file is created with bogus information.

```sh
./offline_ota_handler.py -r runtime -p ota-package.tar.gz

Warning: running in offline mode
Feb 22 16:32:41 INFO: handler.py:1211 - qos_level set as 1
Feb 22 16:32:41 DEBUG: handler.py:119 - CONFIG:
{
  "app_id": "offline_ota_handler", 
  "ca_bundle_file": "/usr/local/lib/python2.7/dist-packages/certifi/cacert.pem", 
  "cloud": {
    "host": "fake.net", 
    "port": 8888, 
    "token": "1234567890abcdef"
  }, 
  "config_dir": ".", 
  "config_file": "offline_ota_handler.cfg", 
  "device_id": "9355805a-1453-47b0-9580-ad579f49c374", 
  "keep_alive": 0, 
  "key": "9355805a-1453-47b0-9580-ad579f49c374-offline_ota_handler", 
  "loop_time": 1, 
  "proxy": {}, 
  "qos_level": 1, 
  "thread_count": 3, 
  "validate_cloud_cert": true
}
Feb 22 16:32:41 DEBUG: handler.py:1078 - log_level set as DEBUG
Feb 22 16:32:41 INFO: ota_handler.py:110 - Started OTA Update
Status of update: (1, 'Software Update Started (Invoked)')
Feb 22 16:32:41 INFO: ota_handler.py:118 - Clean up previous update artifacts...
Feb 22 16:32:41 INFO: ota_handler.py:126 - Downloading Package...
Feb 22 16:32:41 INFO: ota_handler.py:133 - Download Phase Done!
Feb 22 16:32:41 INFO: ota_handler.py:136 - Unzipping Package...
Feb 22 16:32:41 INFO: ota_handler.py:146 - Unzip Complete!
Feb 22 16:32:41 INFO: ota_handler.py:149 - Reading Update Data...
Feb 22 16:32:41 INFO: ota_handler.py:159 - Data Read Successful!
Feb 22 16:32:41 INFO: ota_handler.py:162 - Running Pre-Install...
Feb 22 16:32:42 INFO: ota_handler.py:183 - Pre-Install Complete!
Feb 22 16:32:42 INFO: ota_handler.py:187 - Running Install...
Feb 22 16:32:43 INFO: ota_handler.py:200 - Install Complete!
Feb 22 16:32:43 INFO: ota_handler.py:204 - Running Post-Install...
Feb 22 16:32:44 INFO: ota_handler.py:225 - Post-Install Complete!
Feb 22 16:32:44 INFO: ota_handler.py:237 - OTA Successful!
Feb 22 16:32:44 WARNING: ota_handler.py:262 - removing file name runtime/download/ota-package.tar.gz
Feb 22 16:32:44 INFO: ota_handler.py:273 - Update finished with status Success
Feb 22 16:32:44 INFO: ota_handler.py:276 - Logging stdout to file /home/pb/hdc/device-cloud-python/runtime/otapackage/ota_install.log
```

In the example above:
  * -r the runtime directory relative to the current directory.
  * -p the OTA package name that is currently in the runtime/download directory.
  * The same ota_handler.py class is used for online OTA handling.
  * The same stdout/stderr log is written to runtime/otapackage/ota_install.log.
