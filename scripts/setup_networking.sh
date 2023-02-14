#!/usr/bin/env bash
# Sets IP forwarding to 1, which allows forwarding of IP packets to namespaced network interfaces
echo 1 > /proc/sys/net/ipv4/ip_forward

# Modify iptables so that outgoing packets from containers use the IP address of the outgoing interface
sudo iptables -t nat -A POSTROUTING -o bridge0 -j MASQUERADE
sudo iptables -t nat -A POSTROUTING -o enp0s3 -j MASQUERADE

# Set up a network bridge to connect namespaces
ip link add bridge0 type bridge
ip addr add 10.0.0.1/24 dev bridge0
ip link set bridge0 up