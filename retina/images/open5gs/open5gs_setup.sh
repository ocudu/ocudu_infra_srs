#! /bin/bash
#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#


NUM_LOOP_IFACE="${NUM_LOOP_IFACE:-22}"
NUM_SUBNETS="${NUM_SUBNETS:-255}"

TUN_IP_PREFIX="${TUN_IP_PREFIX:-10.45}"
TUN_MASK="${TUN_MASK:-24}"

# create dummy interfaces on localhost ip range for open5gs entities to bind to
###############################################################################
for ((LOIP=2; LOIP <= NUM_LOOP_IFACE; LOIP++)); do
    ip link add name lo$LOIP type dummy
    ip ad ad 127.0.0.$LOIP/24 dev lo$LOIP
    ip link set lo$LOIP up >/dev/null 2>&1
done

# Setup TUN interface
#####################
# Set up TUN device inside the container
(mkdir -p /dev/net && mknod /dev/net/tun c 10 200 >/dev/null 2>&1) || true

# Create the ogstun iface and assign an IP to it
ip tuntap add name ogstun mode tun 2>/dev/null
# Support multiple subnets
for ((SUBNET = 0; SUBNET < NUM_SUBNETS; SUBNET++)); do
    ip addr del "$TUN_IP_PREFIX.$SUBNET.1/$TUN_MASK" dev ogstun 2>/dev/null || true
    ip addr add "$TUN_IP_PREFIX.$SUBNET.1/$TUN_MASK" dev ogstun 2>/dev/null || true

    # Redirect traffict to ogstun interface & route via subnet ip (to reach IPs from outside of the container)
    iptables -t nat -A POSTROUTING -s "$TUN_IP_PREFIX.$SUBNET.0/$TUN_MASK" ! -o ogstun -j MASQUERADE 2>/dev/null || true
    iptables -A INPUT -i ogstun -j ACCEPT 2>/dev/null || true
done
ip link set ogstun up >/dev/null 2>&1

# run mongodb
#############
mkdir -p /var/log/retina/
mkdir -p /data/db && /usr/bin/mongod >/var/log/retina/mongo.log 2>&1 &

# wait for mongodb to be available, otherwise open5gs will not start correctly
while ! (nc -zv 127.0.0.1 27017 >/dev/null 2>&1); do
    sleep 1
done
