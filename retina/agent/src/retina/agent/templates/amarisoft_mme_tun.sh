#!/bin/bash
#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

ifname="$1"     # Interface name
index="$2"      # Network index (PDN index)
apn="$3"        # Access point name
type="$4"       # ipv4 or ipv6

if [ "$type" = "ipv4" ] ; then

    ifaddr="$5" # Interface address
    addr1="$6"  # First IP address
    addr2="$7"  # Last IP address
    mask="$8"   # Mask

    # Extract IP prefix (first two octets)
    tun_ip_prefix=$(echo "$addr1" | awk -F. '{print $1"."$2}')

    # Extract subnet numbers by splitting the IP by dot symbol.
    first_subnet=$(echo "$addr1" | awk -F. '{print $3}')
    last_subnet=$(echo "$addr2" | awk -F. '{print $3}')

    # Compute number of subnets
    NUM_SUBNETS=$((last_subnet - first_subnet + 1))

    echo "*** Configuring IPv4 pdn '$apn' on ${ifname} for ip range $tun_ip_prefix.$first_subnet.1:$tun_ip_prefix.$last_subnet.1"

    for ((subnet = first_subnet; subnet <= last_subnet; subnet++)); do
        ip addr del "$tun_ip_prefix.$subnet.1/24" dev $ifname 2>/dev/null || true
        ip addr add "$tun_ip_prefix.$subnet.1/24" dev $ifname 2>/dev/null || true

        iptables -t nat -A POSTROUTING -s "$tun_ip_prefix.$subnet.0/24" ! -o $ifname -j MASQUERADE 2>/dev/null || true
    done

    # Bring up the interface
    ip link set ${ifname} up >/dev/null 2>&1

    # Accept all traffic coming in via TUN interface
    ipt=$(iptables -w 5 -S | grep "\-A INPUT \-i ${ifname} \-j ACCEPT")
    if [ "$ipt" = "" ] ; then
        iptables -w 5 -I INPUT -i ${ifname} -j ACCEPT 2>/dev/null || true
    fi

    # IPv6 is always disabled after ipv4
    echo '1' > /proc/sys/net/ipv6/conf/"$ifname"/disable_ipv6 2>/dev/null || sysctl -w net.ipv6.conf."$ifname".disable_ipv6=1 2>/dev/null || true
else

    ll="$5"     # ipv6 link local address
    addr0="$6"  # Interface ipv6 address
    addr1="$7"  # first ipv6 prefix
    addr2="$8"  # last ipv6 prefix
    mask="$9"   # Mask

    echo "*** Configuring IPv6 pdn '$apn' on ${ifname}, $addr0/$mask"

    echo '0' > /proc/sys/net/ipv6/conf/"$ifname"/disable_ipv6 2>/dev/null || sysctl -w net.ipv6.conf."$ifname".disable_ipv6=0 2>/dev/null || true

    # Add link local address
    ifconfig ${ifname} inet6 add ${addr0}/${mask} up

    # Add route for all prefixes
    ip -6 route add ${addr1}/${mask} dev ${ifname}

    ipt=$(ip6tables -w 5 -S | grep "\-A INPUT \-i ${ifname} \-j ACCEPT")
    if [ "$ipt" = "" ] ; then
        ip6tables -w 5 -I INPUT -i ${ifname} -j ACCEPT
    fi
fi

echo "*** Configuration for pdn '$apn' on ${ifname}, $ifaddr/$mask DONE"
