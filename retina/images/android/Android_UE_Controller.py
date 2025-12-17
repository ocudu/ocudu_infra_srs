#!/usr/bin/python3
#
# Copyright 2021-2025 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#


from sys import platform
import logging
from shutil import which
import subprocess
import sys
import re
import time


class Logger:

    # TODO
    #   Rework logging

    def __init__(self, log_file_path):
        logging.basicConfig(filename=log_file_path, format='%(asctime)s %(message)s',
                            datefmt='%m/%d/%Y %I:%M:%S %p',
                            level=logging.DEBUG)

    def info(self, message):
        logging.info("[INFO] " + message)

    def error(self, message):
        logging.error("[ERR] " + message)


class SettingsConfigurator:

    def __init__(self):
        self.log_file_path = "log.txt"

        self.util = Utilities()
        if self.util.ADB_BIN is None:
            print("ADB not found! Exiting...")
            sys.exit(1)

        # initiate logging
        self.log = Logger(self.log_file_path)

    def set_airplane_mode(self, apm_state, serial=None):
        """
        Enable/Disable airplane mode.

        :param apm_state : True: Activate airplane mode, False: Deactivate airplane mode
        :param serial : Device serial
        """

        self.log.info("Setting airplane mode: " + str(apm_state))

        airplane_cmd = 'settings put global airplane_mode_on ' + str(int(apm_state)) \
                       + ' && su -c am broadcast -a android.intent.action.AIRPLANE_MODE'

        self.util.run_adb_shell_cmd(airplane_cmd, True, serial)

    def get_carrier_id(self, carrier_name, serial=None):
        """
        Get ID of telco carrier from the UE's database

        :param carrier_name : Command to execute
        :param serial : Device serial
        :return: Carrier ID
        """

        qry_carrier_cmd = "content query --uri content://telephony/carriers --where \\\'name=\\\"" + str(carrier_name) + "\\\" \\\'"
        available_carrier = self.util.run_adb_shell_cmd(qry_carrier_cmd, True, serial).split("\n")
        if 'Row:' in available_carrier[0]:  # found carrier
            carr_id = re.findall(r'_id=(\S+),', str(available_carrier))[0]
        else:
            carr_id = -1

        return carr_id

    def set_new_carrier(self, apn_parameter, carr_id, serial=None):
        """
        Add / update APN carrier

        :param apn_parameter : Carrier specific parameters
        :param carr_id : Carrier ID, -1 if not existing
        :param serial : Device serial
        :return: New carrier ID
        """

        # build command to add/update carrier
        if carr_id != -1:  # carrier was found, delete it first
            self.delete_apn(apn_parameter["carrier"], serial)

        set_carrier_cmd = "content insert --uri content://telephony/carriers" \
                          + " --bind name:s:\"" + apn_parameter["carrier"] + "\"" \
                          + " --bind numeric:s:\"" + apn_parameter["mcc"] + apn_parameter["mnc"] + "\"" \
                          + " --bind mcc:s:\"" + apn_parameter["mcc"] + "\"" \
                          + " --bind mnc:s:\"" + apn_parameter["mnc"] + "\""\
                          + " --bind apn:s:\"" + apn_parameter["apn"] + "\"" \
                          + " --bind user:s:\"" + apn_parameter["user"] + "\"" \
                          + " --bind password:s:\"" + apn_parameter["password"] + "\"" \
                          + " --bind mmsc:s:\"" + apn_parameter["mmsc"] + "\"" \
                          + " --bind mmsport:s:\"" + apn_parameter["mmsport"] + "\"" \
                          + " --bind mmsproxy:s:\"" + apn_parameter["mmsproxy"] + "\"" \
                          + " --bind authtype:s:\"" + apn_parameter["auth"] + "\"" \
                          + " --bind type:s:\"" + apn_parameter["type"] + "\"" \
                          + " --bind protocol:s:\"" + apn_parameter["protocol"] + "\"" \
                          + " --bind mvno_type:s:\"" + apn_parameter["mvnotype"] + "\"" \
                          + " --bind mvno_match_data:s:\"" + apn_parameter["mvnoval"] + "\"" \
                          + " --bind sub_id:s:\"" + apn_parameter["groupid"] + "\""

        self.util.run_adb_shell_cmd(set_carrier_cmd, True, serial)

        # search for carrier
        return self.get_carrier_id(apn_parameter["carrier"], serial)

    def set_preferred_apn(self, carr_id, serial=None):
        """
        Select/activate APN in Android. It is indispensable that the carrier was set in advance.

        :param carr_id : ID of carrier to be selected
        :param serial : Device serial
        """

        set_apn_cmd = "content insert --uri content://telephony/carriers/preferapn --bind apn_id:s:\"" + str(carr_id) + "\""
        self.util.run_adb_shell_cmd(set_apn_cmd, True, serial)

    def set_apn(self, apn_param, sel_apn, serial=None):
        """
        Adds new APN and optionally activates it.

        :param apn_param : Parameters necessary to set new APN.
        :param sel_apn : Select APN
        :param serial : Device serial
        """

        # search for carrier
        # carrier_id = -1 if carrier was not found
        carrier_id = self.get_carrier_id(apn_param["carrier"], serial)

        # add/update carrier
        carrier_id = self.set_new_carrier(apn_param, carrier_id, serial)

        if sel_apn:
            # select as preferred APN
            self.set_preferred_apn(carrier_id, serial)

        self.log.info("Setting APN done.")

    def select_apn(self, carr_name, serial=None):
        """
        Set preferred APN.

        :param carr_name : Name of the APN to be selected
        :param serial : Device serial
        """

        # search for carrier_id
        carr_id = self.get_carrier_id(carr_name, serial)
        if carr_id == 0:
            return False

        # select carrier by id
        sel_apn_cmd = "content update --uri content://telephony/carriers/preferapn --bind apn_id:s:\"" + str(carr_id) + "\""
        self.util.run_adb_shell_cmd(sel_apn_cmd, True, serial)
        return True

    def delete_apn(self, carr_name, serial=None):
        """
        Delete a specific or all APN(s).

        :param carr_name : Name of the APN to be deleted
        :param serial : Device serial
        """

        if carr_name == "":
            self.log.error("No APN specified to be deleted.")

        set_apn_cmd = "content delete --uri content://telephony/carriers --where \\\'name=\\\"" + str(carr_name) + "\\\" \\\'"
        self.util.run_adb_shell_cmd(set_apn_cmd, True, serial)

    def restore_default_apn(self, sub_id=-2, serial=None):
        """
        Delete all APNs added with this controller. Therefore, it uses the sub_id field to define a Group ID.
        Group ID has to be > -1.

        :param sub_id : Group ID which should be deleted (default: -2)
        :param serial : Device serial
        """

        restore_apn_cmd = "content delete --uri content://telephony/carriers --where \\\'sub_id=\\\"" + str(sub_id) + "\\\" \\\'"

        self.util.run_adb_shell_cmd(restore_apn_cmd, True, serial)
    
    def set_usb_tethering(self, state, serial=None):
        """
        Enable/Disable USB tethering.

        :param state : True: Activate USB tethering, False: Deactivate USB tethering
        :param serial : Device serial
        """

        self.log.info("Setting USB tethering: " + str(state))

        # If a new version of vsc is running, we can toggle usb tethering through this interface. Older versions do not have the rndis parameter.
        svc_return = self.util.run_adb_shell_cmd('svc usb', True, serial)
        if 'rndis' in svc_return:
            if state:
                # Activate USB tethering
                self.util.run_adb_shell_cmd('svc usb setFunctions rndis', True, serial)
            else:
                # We can use this to deactivate USB tethering. Removes the USB properties except for "charging" status
                self.util.run_adb_shell_cmd('svc usb setFunctions', True, serial)
            
            time.sleep(3)
            return

        # Use this workaround if we have no compatible vsc version on the device. 
        # This dictionary maps the correct parcel payload to the corresponding android version
        # As reference see setUsbTethering method in https://android.googlesource.com/platform/frameworks/base/+/master/core/java/android/net/IConnectivityManager.aidl
        connectivity_parcel_payload = {
            5 : "service call connectivity 30 i32 " + str(state),
            6 : "service call connectivity 30 i32 " + str(state),
            7 : "service call connectivity 33 i32 " + str(state),
            8 : "service call connectivity 33 i32 " + str(state), 
            9 : "service call connectivity 33 i32 " + str(state) + "s16 ogt",
            10 : "service call connectivity 33 i32 " + str(state) + "s16 ogt",
        }
        android_ver = (self.util.get_android_ver(serial)).split(".",1)[0]
        
        self.util.run_adb_shell_cmd(connectivity_parcel_payload.get(int(android_ver)), True, serial)
        time.sleep(3)
    
    def set_usb_tethering_ip(self, ip, serial=None):
        if 'rndis0' not in self.util.run_adb_shell_cmd('ip link show', True, serial):
            print('rndis0 interface not found, check if usb tethering is working.')
            return
        self.util.run_adb_shell_cmd('ip address add ' + ip + '/24 dev rndis0', True, serial)
    
    def start_ssh_server(self, port, pub_key=None, serial=None):
        # Kill any active dropbear instance before starting a new one
        self.util.run_adb_shell_cmd('pkill -f dropbearmulti', True, serial)
        # Make filesystem writeable
        self.util.run_adb_shell_cmd('mount -o rw,remount /', True, serial)
        time.sleep(2)
        self.util.run_adb_shell_cmd('mount -o rw,remount /system', True, serial)
        time.sleep(2)
        if pub_key is not None:
            # Keep /data/local/tmp as location convention for keys. This directory is accessible by everyone and avoids permission problems
            self.util.run_adb_shell_cmd('echo "' + pub_key.read() + '" >> /data/local/tmp/authorized_keys', True, serial)
        # Start the dropbear SSH server. Do not modify the parameters.
        self.util.run_adb_shell_cmd('dropbearmulti dropbear -R -p ' + port + ' -T /data/local/tmp/authorized_keys -U 0 -G 0 -N root -A && sleep 3', True, serial)


class ConnectionTesting:

    def __init__(self):
        self.log_file_path = "log.txt"

        self.util = Utilities()
        if self.util.ADB_BIN is None:
            print("ADB not found! Exiting...")
            sys.exit(1)

        # initiate logging
        self.log = Logger(self.log_file_path)

    def ping_test(self, ip_addr="8.8.8.8", count=1, serial=None):
        """
        Tests internet connection via ping.

        :param ip_addr : IP address to ping
        :param count : Number of iterations
        :param serial : Device serial
        :return: Network types as List
        """

        ping_cmd = "ping -c " + str(count) + " " + ip_addr
        ping_out = self.util.run_adb_shell_cmd(ping_cmd, False, serial)
        if "64 bytes from " + ip_addr in ping_out:
            return True
        else:
            return False

    def connection_test(self, iperf_server, iperf_port, serial=None):
        """
        Network connection test via iperf. Test connection and save results to log file.

        :param iperf_server : IP address of iperf server
        :param iperf_port : Port of iperf server
        :param serial : Device serial
        """

        # check if network connection is established
        net_type = self.util.get_network_type(serial)

        if net_type[0] == "Unknown":
            self.log.info("SIM1 is not connected")

        if len(net_type) > 1:  # Dual SIM phone
            if net_type[1] == "Unknown":
                self.log.info("SIM2 is not connected")

        # ping test to test the connection
        if not self.ping_test(iperf_server, 1, serial):
            self.log.error("No internet connection established.")
            return

        # use iperf to test connection
        iperf_cmd = "iperf -c " + iperf_server + " -p " + str(iperf_port)
        output = self.util.run_adb_shell_cmd(iperf_cmd, True, serial)
        self.log.info("Running iperf connection test")
        self.log.info("Command: " + iperf_cmd)
        self.log.info(output)
        return output


class Utilities:

    def __init__(self):
        self.ADB_BIN = None
        self.log_file_path = "log.txt"

        # initiate logging
        self.log = Logger(self.log_file_path)

        # Get ADB path
        if platform in ('cygwin', 'win32'):  # Windows
            self.log.error("Windows is currently not support!")
        elif platform == 'darwin':  # Mac OS
            self.ADB_BIN = which('adb')
        else:  # Linux
            self.ADB_BIN = which('adb')
        if self.ADB_BIN is None:
            self.log.error("ADB was not found!")
            sys.exit(1)

        # Make sure ADB server is running
        self.run_adb_cmd('start-server')

    def run_adb_cmd(self, command, serial=None):
        """
        Execute ADB command

        :param command : ADB command to execute
        :param serial : Device serial
        :return : UTF-8 decoded process stdout
        """

        self.log.info("Execute ADB command: " + command)
        try:
            if serial is not None:
                process = subprocess.Popen([self.ADB_BIN, '-s' + serial, command], stdin=subprocess.PIPE,
                                           stdout=subprocess.PIPE)
            else:
                process = subprocess.Popen([self.ADB_BIN, command], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        except subprocess.CalledProcessError as err:
            self.log.error("Execution of ADB command \"" + command + "\" failed")
            self.log.error("Error message: " + err.output)
            return ""

        process_stdout = process.stdout.read().decode('utf-8')
        process.stdout.flush()
        # self.log.info(process_stdout)

        return process_stdout

    def run_adb_shell_cmd(self, command, run_root, serial=None):
        """
        Execute shell command over ADB shell

        :param command : Command to execute
        :param run_root : Run command as root
        :param serial : Device serial
        :return: UTF-8 decoded process stdout
        """

        self.log.info("Execute ADB Shell command: " + command + " root privileges: " + str(run_root))
        if run_root:
            try:
                # Use 'exec-out' to run commands in one line
                if serial is not None:
                    process = subprocess.Popen([self.ADB_BIN, '-s', serial, 'exec-out', 'su -c ' + command],
                                               stdin=subprocess.PIPE, stdout=subprocess.PIPE)
                else:
                    process = subprocess.Popen([self.ADB_BIN, 'exec-out', 'su -c ' + command], stdin=subprocess.PIPE,
                                               stdout=subprocess.PIPE)
            except subprocess.CalledProcessError as err:
                self.log.error("Execution of shell command \"" + command + "\" failed")
                self.log.error("Error message: " + err.output)
                return ""
        else:
            try:
                if serial is not None:
                    process = subprocess.Popen([self.ADB_BIN, '-s', serial, 'exec-out', command], stdin=subprocess.PIPE,
                                               stdout=subprocess.PIPE)
                else:
                    process = subprocess.Popen([self.ADB_BIN, 'exec-out', command], stdin=subprocess.PIPE,
                                               stdout=subprocess.PIPE)
            except subprocess.CalledProcessError as err:
                self.log.error("Execution of shell command \"" + command + "\" failed")
                self.log.error("Error message: " + err.output)
                return ""

        process_stdout = process.stdout.read().decode('utf-8')
        process.stdout.flush()
        # self.log.info(process_stdout)

        return process_stdout

    def get_android_ver(self, serial=None):
        """
        Get Android version of UE

        :param serial : Device serial
        :return: Android version as string
        """

        android_ver = self.run_adb_shell_cmd('getprop ro.build.version.release', False, serial)

        return android_ver

    def get_operator_name(self, serial=None):
        """
        Returns the operator name

        :param serial : Device serial
        :return: Operator name
        """

        operator_name = self.run_adb_shell_cmd('getprop gsm.operator.alpha', False, serial)
        if operator_name is '':
            operator_name = self.run_adb_shell_cmd('getprop gsm.operator.orig.alpha', False, serial)

        return operator_name if operator_name is not '' else 'None'

    def get_signal_info(self, serial=None):
        """
        Returns signal information

        :param serial : Device serial
        :return: Signal information
        """

        # TODO: Parse values which are needed
        signal_info = self.run_adb_shell_cmd('dumpsys telephony.registry | grep mSignalStrength', False, serial)

        return signal_info

    def get_plmn(self, serial=None):
        """
        Returns PLMN of current connection

        :param serial : Device serial
        :return: Signal information
        """

        return self.run_adb_shell_cmd('getprop gsm.operator.numeric', False, serial)

    def get_network_type(self, serial=None):
        """
        Returns network type [SIM1,SIM2]

        :param serial : Device serial
        :return: Network types as List
        """

        network_type = self.run_adb_shell_cmd('getprop gsm.network.type', False, serial)
        network_type_list = network_type.split(sep=',')
        network_type_list = [x.replace('\n', '') for x in network_type_list]  # remove trailing \n
        return network_type_list

    def get_ip(self, device, serial=None):
        """
        Returns IP address of given adapter

        :param device : Adapter name
        :param serial : Device serial
        :return: Network types as List
        """

        if type(device) != str:
            return "-1"
        ip_grep_cmd = "ifconfig " + device + " | grep \'inet addr\' | cut -d: -f2 | awk \'{print $1}\'"
        return self.run_adb_shell_cmd(ip_grep_cmd, True, serial)

    def is_rrc_connected(self, serial):
        """
        Checks if COTS UE is RRC connected

        :param serial : Device serial
        :return: RRC connected? (bool)
        """
        # TODO
        #   How to check if a COTS UE is RRC connected?
        #   Add timer to avoid endless checking loops
        return True

    def is_emm_connected(self, serial):
        """
        Checks if COTS UE is EMM connected

        :param serial : Device serial
        :return: EMM connected? (bool)
        """
        # TODO
        #   Is this sufficient for the EMM connection test?
        #   Add timer to avoid endless checking loops
        conn_stat = self.get_network_type(serial)
        print(conn_stat)
        if 'LTE' in conn_stat:
            return True
        return False
