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

# Clean up
##########

for ((SUBNET = 0; SUBNET < NUM_SUBNETS; SUBNET++)); do
    iptables -t nat -D POSTROUTING -s "$TUN_IP_PREFIX.$SUBNET.1/$TUN_MASK" ! -o ogstun -j MASQUERADE >/dev/null 2>&1 || true
done
iptables -D INPUT -i ogstun -j ACCEPT >/dev/null 2>&1 || true
ip link delete ogstun >/dev/null 2>&1 || true

for ((LOIP = 2; LOIP <= NUM_LOOP_IFACE; LOIP++)); do
    ip link delete lo$LOIP >/dev/null 2>&1 || true
done
