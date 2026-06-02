#!/bin/bash

# SPDX-FileCopyrightText: Copyright (C) 2019-2025 Amarisoft
# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

ue_id="$1"           # UE ID
pdn_id="$2"          # PDN unique id (start from 0)
ifname="$3"          # Interface name
ipv4_addr="$4"       # IPv4 address
ipv4_dns="$5"        # IPv4 DNS
ipv6_local_addr="$6" # IPv6 local address
ipv6_dns="$7"        # IPv6 DNS
param="$8"           # UE param
apn="$9"             # Access point name
old_link_local=""
cid="-"

# Optional parameters
shift; shift; shift; shift; shift; shift; shift; shift; shift;
while [ "$1" != "" ] ; do
    case "$1" in
    --mtu)
        mtu="$2"
        shift
        ;;
    --cid)
        cid="$2"
        shift
        ;;
    *)
        echo "Bad parameter: $1" >&2
        exit 1
        ;;
    esac
    shift
done

if [ "$pdn_id" = "0" ] ; then
    if [ -e /var/run/netns/$ue_id ] ; then
        ip netns del $ue_id
    fi
    ip netns add $ue_id
fi

echo "Configure $ue_id($param) on pdn $apn#$pdn_id[$cid], tun=$ifname, ip=$ipv4_addr, dns=$ipv4_dns"

# Set DNS ?
if [ "$ipv4_dns" != "" ] || [ "$ipv6_dns" != "" ] ; then
    mkdir -p /etc/netns/$ue_id
    rm -f /etc/netns/$ue_id/resolv.conf
    if [ "$ipv4_dns" != "" ] ; then
        echo "nameserver $ipv4_dns" >> /etc/netns/$ue_id/resolv.conf
    fi
    if [ "$ipv6_dns" != "" ] ; then
        echo "nameserver $ipv6_dns" >> /etc/netns/$ue_id/resolv.conf
    fi
else
    rm -f /etc/netns/$ue_id/resolv.conf
fi

ifname1="pdn$pdn_id"
ip link set dev $ifname name $ifname1 netns $ue_id
ifname="$ifname1"

if [ "$ipv6_local_addr" != "" ] ; then
    ip netns exec $ue_id bash -c "echo '0' > /proc/sys/net/ipv6/conf/$ifname/disable_ipv6"
    ip netns exec $ue_id bash -c "echo '1' > /proc/sys/net/ipv6/conf/$ifname/accept_ra"
    ip netns exec $ue_id bash -c "echo '1' > /proc/sys/net/ipv6/conf/$ifname/router_solicitation_delay"
    ip netns exec $ue_id bash -c "echo '1' > /proc/sys/net/ipv6/conf/$ifname/autoconf"
else
    ip netns exec $ue_id bash -c "echo '1' > /proc/sys/net/ipv6/conf/$ifname/disable_ipv6"
fi

if [ "$pdn_id" = "0" ] ; then
    ip netns exec $ue_id ifconfig lo up
fi

ip netns exec $ue_id ifconfig $ifname up txqueuelen 1000
if [ "$ipv4_addr" != "" ] ; then
    ip netns exec $ue_id ifconfig $ifname $ipv4_addr/24
    if [ "$pdn_id" = "0" ] ; then
        ip netns exec $ue_id ip route add default via $ipv4_addr
    fi
    if [ "$mtu" != "" ] ; then
        ip netns exec $ue_id ifconfig $ifname mtu $mtu
    fi
fi
if [ "$ipv6_local_addr" != "" ] ; then
    old_link_local=`ip netns exec $ue_id ip addr show dev $ifname | sed -e's/^.*inet6 \([^ ]*\)\/.*$/\1/;t;d'`
    if [ "$old_link_local" != "" ] ; then
        ip netns exec $ue_id ifconfig $ifname inet6 del $old_link_local/64
    fi
    ip netns exec $ue_id ifconfig $ifname inet6 add $ipv6_local_addr/64
fi

# Give mac address to lteue
if [ "$ipv4_addr" = "" -a "$ipv6_local_addr" = "" ] ; then
    echo "MAC_ADDR="$(ip netns exec $ue_id ip link show dev $ifname | grep -oP "ether \K[\d:a-f]+")
fi

