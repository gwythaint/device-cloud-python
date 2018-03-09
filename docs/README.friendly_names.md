Description
===========
By default, the friendly name is set to the thing_key.  To set a more
human-readable name in an application, call the following API:

```
client.update_thing_details(name="My friendly name for thing 1")
```

Note: the thing_key cannot be updated.

Example
-------
If a MAC address is preferred, set the friendly name to the MAC address:
```
from uuid import getnode as get_mac

mac_address = get_mac()
mac_str = ':'.join(("%012X" % mac_address)[i:i+2] for i in range(0, 12, 2))

client.update_thing_details(name=mac_str)
```

Device Manager iot.cfg
----------------------
The device manager iot.cfg configuration file supports a new option,
which is set to None by default:
```
"thing_friendly_name":"None"
```

The value of "None" means that the field is ignored.  If the value is
something other than None, the thing_friendly_name will be updated.
