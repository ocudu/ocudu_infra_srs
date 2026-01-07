#!/usr/bin/python3
#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#


import sys
import argparse
import Android_UE_Controller
import subprocess
import os
import time


if __name__ == "__main__":
    # start ADB Server
    os.popen("adb start-server")

    # init classes
    configurator = Android_UE_Controller.SettingsConfigurator()
    testing = Android_UE_Controller.ConnectionTesting()
    util = Android_UE_Controller.Utilities()
    log = Android_UE_Controller.Logger("log.txt")

    # initial checkups
    parser = argparse.ArgumentParser()
    parser.add_argument('-ac', '--adb-command', action='store', type=str, help="Run ADB command")
    parser.add_argument('-sc', '--shell-command', action='store', type=str, help="Run Android shell command")
    parser.add_argument('-rsc', '--root-shell-command', action='store', type=str,
                        help='Run Android shell command with root permission')
    parser.add_argument('-am', '--airplane-mode', action='store', choices=['on', 'off'], type=str,
                        help='Toggle Airplane Mode')
    parser.add_argument('-av', '--android-version', action='store_true', help='Get Android Version')
    parser.add_argument('-adi', '--additional-device-info', action='store_true', help='Returns IMSI, ICCID and IMEI')
    parser.add_argument('-cs', '--connection-status', action='store_true', help='Returns LTE connection information')
    parser.add_argument('-pt', '--ping-test', action='store', help='Test internet connection via ping')
    parser.add_argument('-ip', '--get-ip', action='store', help='Get assigned IP address by device name')
    parser.add_argument('-rrc', '--rrc-connection-status', action='store_true', help='Test RRC connection status')
    parser.add_argument('-emm', '--emm-connection-status', action='store_true', help='Test EMM connection status')
    parser.add_argument('-s', '--serial', action='store', type=str, help='Enter serial number if multiple devices are connected')

    # add sub-commands via subparsers
    subparsers = parser.add_subparsers(dest="subparser")

    # set APN sub-parser
    parser_apn_set = subparsers.add_parser('set-apn', help='Set & select new APN')
    parser_apn_set.add_argument('-name', dest='apn_name', action='store', help='Displayed name in menu')
    parser_apn_set.add_argument('-apn', dest='apn_apn', action='store', help='Access Point Name')
    parser_apn_set.add_argument('-proxy', dest='apn_proxy', action='store', help='Proxy')
    parser_apn_set.add_argument('-port', dest='apn_port', action='store', help='Port')
    parser_apn_set.add_argument('-user', dest='apn_user', action='store', help='APN User')
    parser_apn_set.add_argument('-pw', dest='apn_pw', action='store', help='Password')
    parser_apn_set.add_argument('-server', dest='apn_server', action='store', help='Server')
    parser_apn_set.add_argument('-mmsc', dest='apn_mmsc', action='store', help='Multimedia Messaging Service Center (MMSC)')
    parser_apn_set.add_argument('-mmsport', dest='apn_mmsport', action='store', help='MMS Port')
    parser_apn_set.add_argument('-mmsproxy', dest='apn_mmsproxy', action='store', help='MMS Proxy')
    parser_apn_set.add_argument('-mcc', dest='apn_mcc', action='store',help='Mobile Country Code')
    parser_apn_set.add_argument('-mnc', dest='apn_mnc', action='store', help='Mobile Network Code')
    parser_apn_set.add_argument('-type', dest='apn_type', action='store', help='Type')
    parser_apn_set.add_argument('-auth', dest='apn_auth', action='store', help='Authentication type')
    parser_apn_set.add_argument('-protocol', dest='apn_prot', action='store', help='APN protocol')
    parser_apn_set.add_argument('-mvnotype', dest='apn_mvno_type', action='store', help='MVNo-Type')
    parser_apn_set.add_argument('-mvnoval', dest='apn_mvno_value', action='store', help='MVNO-Value')
    parser_apn_set.add_argument('-groupid', dest='apn_group_id', action='store', help='APN Group ID [CAUTION!]')
    parser_apn_set.add_argument('-select', dest='apn_sel', action='store', choices=['True', 'False'], help='Select APN?')

    # del APN sub-parser
    parser_apn_del = subparsers.add_parser('del-apn', help='Delete specified APN')
    parser_apn_del.add_argument('-name', dest='apn_name_del', action='store', help='Displayed name in menu')
    parser_apn_del.add_argument('-default', dest='apn_set_default', action='store_true', help='Reset all APNs and restore default')
    parser_apn_del.add_argument('-delgroup', dest='apn_del_group', action='store', help='Delete specific group of APNs by Group ID')

    # select APN sub-parser
    parser_apn_del = subparsers.add_parser('sel-apn', help='Select preferred APN')
    parser_apn_del.add_argument('-name', dest='apn_name_sel', action='store', help='Displayed name in menu')

    args = parser.parse_args()

    if args.serial:
        device_list = util.run_adb_cmd('devices')
        if args.serial not in device_list:
            print("Serial does not match to a connected device, exiting...")
            sys.exit(1)

    if args.adb_command:
        out = util.run_adb_cmd(args.adb_command, args.serial)
        print(out)

    if args.shell_command:
        out = util.run_adb_shell_cmd(args.shell_command, False, args.serial)
        print(out)
    if args.root_shell_command:
        out = util.run_adb_shell_cmd(args.root_shell_command, True, args.serial)
        print(out)

    if args.android_version:
        android_version = ((util.get_android_ver(args.serial)).split(".",1))[0]
        log.info("Android version: " + android_version)
        print("Android version: " + android_version)

    if args.airplane_mode:
        # First set the UI button and then execute the actual intent to modify all radio connections
        if args.airplane_mode == 'on':
            configurator.set_airplane_mode(True, args.serial)
            print("Set airplane mode: on")
        else:
            configurator.set_airplane_mode(False, args.serial)
            print("Set airplane mode: off")

    if args.additional_device_info:
        # IMSI
        imsi = util.run_adb_shell_cmd('service call iphonesubinfo 7 | awk -F \"\'\" \'{print $2}\' | sed \'1 d\' | tr -d \'.\' | awk \'{print}\' ORS=', True, args.serial)
        # ICCID (TODO: Some devices only return valid ICCID for iphonesubinfo 11)
        iccid = util.run_adb_shell_cmd('service call iphonesubinfo 10 | awk -F \"\'\" \'{print $2}\' | sed \'1 d\' | tr -d \'.\' | awk \'{print}\' ORS=', False, args.serial)
        # IMEI
        imei = util.run_adb_shell_cmd('service call iphonesubinfo 4 | awk -F \"\'\" \'{print $2}\' | sed \'1 d\' | tr -d \'.\' | awk \'{print}\' ORS=', False, args.serial)

        print("IMSI: " + str(imsi))
        print("ICCID: " + str(iccid))
        print("IMEI: " + str(imei))

    if args.connection_status:
        operator_name = util.get_operator_name(args.serial)
        home_plmn = util.get_plmn(args.serial)
        net_type = str(util.get_network_type(args.serial))

        log.info("Operator name: " + operator_name + "PLMN: " + home_plmn)
        log.info("Network type: " + net_type)

        print("Operator name: " + operator_name + "PLMN: " + home_plmn)
        print("Network type: " + net_type)

    if args.ping_test:
        testing.ping_test(args.ping_test, 1, serial=args.serial)

    if args.get_ip:
        print(util.get_ip(args.get_ip, args.serial))

    if args.rrc_connection_status:
        if util.is_rrc_connected(args.serial):
            print("UE is RRC connected")
        sys.exit(0)

    if args.emm_connection_status:
        if util.is_emm_connected(args.serial):
            print("UE is EMM connected")
        sys.exit(0)

    if args.subparser == 'set-apn':
        # check mandatory parameters
        if args.apn_apn is None or args.apn_mcc is None or args.apn_mnc is None:
            log.error("Missing MCC, MNC or APN!")
            print("Missing MCC, MNC or APN!")
            sys.exit(1)

        # check if GroupID was set correctly
        if args.apn_group_id and int(args.apn_group_id) > -1:
            print("Setting Group ID > -1 is not allowed. See README.md for further info.")
            sys.exit(1)

        # parse arguments
        apn_params = {
            "carrier": str(args.apn_name or 'default'),
            "apn": str(args.apn_apn or ''),
            "proxy": str(args.apn_proxy or ''),
            "port": str(args.apn_port or ''),
            "user": str(args.apn_user or ''),
            "password": str(args.apn_pw or ''),
            "server": str(args.apn_server or ''),
            "mmsc": str(args.apn_mmsc or ''),
            "mmsport": str(args.apn_mmsport or ''),
            "mmsproxy": str(args.apn_mmsproxy or ''),
            "mcc": str(args.apn_mcc or ''),
            "mnc": str(args.apn_mnc or ''),
            "auth": str(args.apn_auth or '-1'),
            "type": str(args.apn_type or ''),
            "protocol": str(args.apn_prot or ''),
            "mvnotype": str(args.apn_mvno_type or ''),
            "mvnoval": str(args.apn_mvno_value or ''),
            "groupid": str(args.apn_group_id or '-2')
        }

        select_apn = False
        if args.apn_sel == "true":
            select_apn = True

        # set APN
        configurator.set_apn(apn_params, select_apn, args.serial)
        print("Setting APN done")

    if args.subparser == 'sel-apn':
        configurator.select_apn(args.apn_name_sel, args.serial)
        print(args.apn_name_sel + " selected as preferred APN")

    if args.subparser == 'del-apn':
        if args.apn_set_default:
            configurator.restore_default_apn(args.serial)
        elif args.apn_del_group:
            if args.apn_del_group in range(-2147483647, -1):
                configurator.restore_default_apn(args.apn_del_group, args.serial)
            else:
                print("Group ID out of range [-2147483647, -1]")
        elif args.apn_name_del:
            configurator.delete_apn(args.apn_name_del, args.serial)
            print("APN " + args.apn_name_del + " deleted")
        else:
            print("Specify name or set to default.")
