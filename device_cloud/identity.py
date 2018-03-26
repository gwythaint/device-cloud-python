import uuid
from uuid import getnode as get_mac

"""
This is a simple class used to select how certain device IDs are
generated without editing the main device manager code.  By default,
UUID is used for the device ID.  To use an alternate method, define
the function in this module and use a python decorator to call it
below.

Note: the design is that the decorator must override the default
implementation, not append to it.
"""

class Identity(object):
    def alternate_device_id(self):
        """
        This is an example implementation showing how to override the
        default get_device_id function which uses uuid.  This alternate
        method uses the mac address.  Note: get_mac will return a random
        number if it cannot find the mac address.
        """

        def gen_alt_device_id(self):
            mac_raw =get_mac()
            return '-'.join(("%012X" % mac_raw)[i:i+2] for i in range(0, 12, 2))

        def wrapper(self):
            return gen_alt_device_id(self)

        return wrapper

    #@alternate_device_id
    def get_device_id(self):
        """
        Default implementation for get_device_id is uuid.uuid4().  To
        override that, add a function and use a decorator.  E.g.
        @alternate_device_id is a decorator.  Uncomment to use it.
        """
        return str(uuid.uuid4())
