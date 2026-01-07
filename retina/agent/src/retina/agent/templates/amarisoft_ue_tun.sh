#!/bin/bash
#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

set -e

# TODO use mask from variable, not hardcoded
TUN_MASK=24

ue_id="$1"           # UE ID
pdn_id="$2"          # PDN unique id (start from 0)
ifname="$3"          # Interface name
ipv4_addr="$4"       # IPv4 address
ipv4_dns="$5"        # IPv4 DNS
ipv6_local_addr="$6" # IPv6 local address
ipv6_dns="$7"        # IPv6 DNS

echo "UE PDN TUN iface requested: ue_id: $ue_id, pdn_id: $pdn_id, ifname: $ifname, ipv4_addr: $ipv4_addr, ipv4_dns: $ipv4_dns, ipv6_local_addr: $ipv6_local_addr, ipv6_dns: $ipv6_dns"

if [ "$ifname" = "" ]; then
    exit 0
fi

if [ "$ipv4_addr" = "" ]; then
    exit 0
fi

ip link set dev "$ifname" up >/dev/null
ip addr add "${ipv4_addr}/${TUN_MASK}" dev $ifname
echo "Created iface $ifname with ${ipv4_addr}"
