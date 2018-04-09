#!/usr/bin/env python
"""
Description:
This script is designed to trigger a software rollback.  The process
is as follows:
  * take system snapshot
  * install software
  * set flag to trigger rollback
  * test with cloud-test.py
    * if cloud-test.py returns 0
    *   clear the trigger flags
    * else
    *   start watch dog process

How it works:
The rollback proceedure is driven by the user defined software update
scripts: pre_install.sh, install.sh, post-install.sh and
err_install.sh.  If any phase of the software update process fails, a
rollback can be triggered.  This utility provides the hooks to control
the rollback (see details below).

This utility creates special flag files and starts a watchdog.  The
watchdog waits for the flags to clear within 3 minutes.  If the flags
do not clear, the watchdog exits and the system reboots.  During the
bootup process the ramdisk checks for the rollback flags.  If the
ramdisk finds the rollback flags, it will begin the rollback and then
boot into the sane snapshot.

Requirements:
This script was primarily designed for Wind River Linux IDP, which has
the required dependencies to support rollback.  The filesystem must
provide the following:
  * lvm partition with Wind River Linux IDP OS
  * lvm tools
  * initramfs with special rollback scripts
  * this snapshot utility
  * sudoers access without password, if not running as root

Typical Usage:
This script is meant to be called during the software update phases.
There are four phases:
  * pre_install
  * install
  * post_install
  * err_install
Snapshots are typically taken during the pre_install phase.  When to
perform a rollback is user defined, but the following scenarios are
recommended:

Scenario 1: post_install
(See example scripts in idp-rollback-package)
A software update might succeed, but fail to connect to the cloud if a
bad software package was used.  In order not to brick the device, test
the connectivity in the post_install phase.  In short, this means
setting the trigger flag and returning the correct status.  If a non
zero value is returned, the err_install phase will be called.  The
err_install phase starts the watchdog. 
Add the following to the post_install script:
  * snapshot_util.py -t  (set the trigger files)
  * test for connectivity with cloud-test.py
  * snapshot_util.py -c  (clear the trigger files on success)
  * return 1 on failure.  The err_install will handle
  the clean up.

Note: this test expects the system to have a functional network.  If
reboot on completion was set in the update.json file, a sleep will be
required in this phase to allow the watch dog to time out (3 min).
Recommend a 4 minute sleep.

Scenario 2: err_install
(See example scripts in idp-rollback-package)
Rollback on ANY software update failure.  If this behaviour is
desired, do the following in the err_install phase:
  * snapshot_util.py -t
  * shutdown -r +3
The initramfs will see the flags and start the rollback.
Note: any logs or other meta data should be uploaded or stored off
device before rebooting.
"""

# -------------------------------------------------------------
# Test 1: take snapshot and trigger rollback, then make some FS
# changes to validate
# Status: PASSED
# -------------------------------------------------------------
# Test 2: trigger rollback from watch dog
# Status: PASSED
# -------------------------------------------------------------
# Test 3: implement ota hooks for above and test a failed ota update
# Status:
# -------------------------------------------------------------
import os
import subprocess
import sys
import getopt

''' Global Variables '''
IOT_ROOT                = '/var/lib/python-device-cloud'
IOT_ROLLBACK_FLAG       = IOT_ROOT + '/ota_rollback_enabled'
IOT_TRIGGER_TIMER_FLAG  = IOT_ROOT + '/ota_timer_triggered'
IOT_BOOTONCE_FLAG       = IOT_ROOT + '/ota_bootonce'
REBOOT_DELAY_IN_SECONDS = 60
SUCCESS         = 0
ERROR           = 1
TIME_DELAY      = 1

def exec_cmd(cmd):
   """Execute the shell cmd return status, stdout, stderr"""
   ''' Usage:
       takes a string of cmd + params.
       ret, stdout, stderr = exec_cmd (sys.argv[1])
       ret = True|False
       stdout if ret == True
       stderr if ret == False 
   '''
   print("Executing command '%s'" % cmd)
   output, err = ("","")
   retcode = 0
   try:
       proc = subprocess.Popen(cmd, 
                   shell=True, stdout=subprocess.PIPE,
                   stderr=subprocess.PIPE)
       output, err = proc.communicate()
       retcode = proc.returncode
   except OSError:
       print("Failed to execute the command: %s %s" % (output, err))
       print("Command error:\n" + err)
       return 1
   if retcode == 0:
       print("Command executed successfully: %s%s" % (output, err))
   else:
       print("Failed to execute the command: %s %s" % (output, err))
       print("Command error:\n" + err)
   return retcode, output, err


def take_snapshot():
    ''' Take a snapshot of the running system and save it in the snapshot volume '''
    # find the mount point of / and the size of the LV
    cmd = "df / | tail -1"
    ret, rootdev, err = exec_cmd( cmd )
    rootdev = rootdev.split( ' ' )
    rootdev = rootdev[0]
    if not ret:
        cmd = "sudo /usr/sbin/lvdisplay " + rootdev + " -c 2> /dev/null"
        ret, lv_info, err = exec_cmd( cmd )

    # exit if the mount point is not a LVM volume
    if not ret and not lv_info.strip( ):
        print( "ERROR: %s not a LVM volume" % ( rootdev ) )
        return ERROR

    # find the size of the LVM volume
    if not ret:
        lv_info_part = lv_info.split( ':' )
        vg_lv_part = lv_info_part[0].split( '/' )
        vg_name = vg_lv_part[2]
        lv_name = vg_lv_part[3]
        cmd = "sudo /usr/sbin/lvs " + rootdev + " -o LV_SIZE --noheadings --units G"
        ret, lv_size, err = exec_cmd( cmd )

    # construct snapshot volume name
    if not ret:
        snapshot_vl = "/dev/" + vg_name + "/" + lv_name + "_snapshot"

        # refresh status of run time volume, ie, reload its metadata. This is not necessary in normal operation,
        # but may be useful if something has gone wrong or if you're doing clustering manually without a clustered
        # lock manager. All the use of lvchange --refresh in this file is for this same purpose.
        cmd = "sudo /usr/sbin/lvchange --refresh " + rootdev + " --noudevsync --monitor n"
        ret2, out, err = exec_cmd( cmd )

        # check to see if snapshot volume already exist
        cmd = "sudo /usr/sbin/lvscan | grep " + snapshot_vl
        ret2, out, err = exec_cmd( cmd )
        if not ret2 and out.strip( ):
            # refresh status of the snapshot volume
            cmd = "sudo /usr/sbin/lvchange --refresh " + rootdev + "_snapshot --noudevsync --monitor n"
            ret2, out, err = exec_cmd( cmd )

            # delete the previous snapshot so that we have enough space
            print( "INFO: Removing previous %s" % ( snapshot_vl ) )
            cmd = "sudo /usr/sbin/lvremove --noudevsync -f " + snapshot_vl + " &> /dev/null"
            ret2, out, err = exec_cmd( cmd )

        # take a snapshot of the current running rootfs
        lv_size = lv_size.rstrip( )
        print( "INFO: Creating new " + snapshot_vl + " with volume size " + lv_size )
        cmd = "sudo /usr/sbin/lvcreate --noudevsync -s -n " + snapshot_vl + " -L " + lv_size + " " + rootdev
        ret, out, err = exec_cmd( cmd )

    # display all logical volume
    cmd = "sudo /usr/sbin/lvdisplay"
    ret_junk, out, err = exec_cmd( cmd )

    if not ret:
        return SUCCESS
    else:
        return ERROR

def check_rollback_support():
    ''' Set lvm support flag '''
    cmd = "sudo /usr/sbin/lvscan | grep ACTIVE | awk '{print $1}' 2> /dev/null"
    ret, lv_info, err = exec_cmd( cmd )

    # set the lvm support flag if lvm volumes are found
    if not ret and lv_info:
        lvm_support = True
    else:
        print( "WARN: there is no LVM volume found" )
        lvm_support = False
    return lvm_support 

def set_trigger_flag():
    ''' Write a trigger flag for the watchdog '''
    cmd = "date +%s > " + IOT_TRIGGER_TIMER_FLAG
    ret, out, err = exec_cmd(cmd)
    if ret:
        print("ERROR:failed to write trigger flag %s\n" % err )
        return ERROR
    return SUCCESS

# the device-cloud-watchdog-test.sh script will set this flag, but add the
# handler here for testing
def set_rollback_enabled_flag():
    ''' Write a rollback trigger flag for initramfs '''
    print("INFO: setting rollback enabled flag ...\n")
    cmd = "touch %s" % IOT_ROLLBACK_FLAG
    ret, out, err = exec_cmd(cmd)
    if ret:
        print("ERROR: %s failed \n" % cmd)
        print("ERROR: %s \n" % err)
        return ERROR
    return SUCCESS

def start_watchdog():
    ''' Start the watch dog '''
    print("INFO: device-cloud-watchdog is to start to monitor agent ...\n")

    # make sure there are no existing watchdogs running
    exec_cmd("sudo systemctl stop device-cloud-watchdog >& /dev/null")

    # start the watchdog
    cmd = 'sudo systemctl start device-cloud-watchdog'
    ret, out, err = exec_cmd(cmd)
    if ret:
        print("ERROR: %s failed \n" % cmd)
        print("ERROR: %s \n" % err)
        return ERROR
    return SUCCESS

def usage():
    ''' Usage '''
    print ("Usage:\n"
            "\t-s\tTake Snapshot (LVM)\n" 
            "\t-t\tSet watchdog trigger file\n" 
            "\t-w\tStart watchdog\n" 
            "\t-c\tClear trigger files\n" 
            "\t-h\tThis output\n"
            "\t-r\tSet rollback flag (for testing only)\n") 
    print("\nNote: Each flag must be set sequentially.  For detailed usage notes, run\n"
          "\t $ pydoc snapshot_util")
    sys.exit(ERROR)

# --------------------------------------------
if __name__ == "__main__":
    watchdog = False
    snapshot = False
    trigger = False
    rollback = False
    opt = ""
    clear = False

    print( "INFO: Starting snapshot..." )
    optlist, args = getopt.getopt(sys.argv[1:], "wstch")
    for opt,arg in optlist:
        if opt == "-w":
            print("Watchdog enabled...")
            watchdog = True
        elif opt == "-s":
            print("Preparing to take snapshot...")
            snapshot = True
        elif opt == "-t":
            print("Setting watch dog trigger flag ...")
            trigger = True
        elif opt == "-r":
            print("Setting rollback enabled trigger flag ...")
            rollback = True
        elif opt == "-c":
            print("Clearing trigger flags ...")
            clear = True
        elif opt == "-h":
            usage()
        else:
            print("Error, unrecognised parameter")
            usage()
    if opt == "":
        usage()

    # check for snapshot technology support
    if check_rollback_support() == False:
        print("Error: LVM is not supported.")
        sys.exit(ERROR) 


    if snapshot == True:
        print ("taking snapshot")
        if take_snapshot() != SUCCESS:
            print("ERROR: snapshot failed.  This error is not recoverable.\n"
                  "Unable to rollback.")
            sys.exit(ERROR) 

    # set a rollback timer trigger flag.  The watchdog will use
    # this file.  Must be set before starting agent. Upon success,
    # the agent will remove this flag.
    if trigger == True:
        print ("created trigger flag")
        if set_trigger_flag() != SUCCESS:
            print("ERROR: set trigger flag failed.  This error is not recoverable.\n"
                  "Unable to rollback.")
            sys.exit(ERROR) 

    # This is for testing only.  The watchdog test will set this flag
    if rollback == True:
        if set_rollback_enabled_flag() != SUCCESS:
            print("ERROR: set rollback enabled flag failed.  This error is not recoverable.\n"
                  "Unable to rollback.")

            # try to clean up the trigger flag, if it succeeded and
            # this fails
            exec_cmd("rm -f " + IOT_TRIGGER_TIMER_FLAG)
            sys.exit(ERROR) 

    # start the watch dog
    if watchdog == True:
        print("starting watchdog")
        if start_watchdog() != SUCCESS:
            print("ERROR: Unable to start watchdog.  This error is not recoverable.\n"  
                  "Unable to rollback.")
            sys.exit(ERROR) 

    if clear == True:
        files = [ IOT_ROLLBACK_FLAG, IOT_TRIGGER_TIMER_FLAG ]
        for f in files:
            if os.path.isfile(f):
                try:
                    os.remove(f)
                except (OSError, IOError) as err:
                    error = str(err)
                    print(error + "Unable to remove file")

    # if we get here, all is good
    sys.exit(SUCCESS) 
