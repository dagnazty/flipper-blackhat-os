#!/usr/bin/env python3
"""Interface detection utilities"""

import subprocess
import os
from .colors import Colors


def get_wifi_interfaces():
    """Get list of WiFi interfaces"""
    interfaces = []
    try:
        result = subprocess.run(['iw', 'dev'], capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if 'Interface' in line:
                iface = line.split()[-1]
                interfaces.append(iface)
    except FileNotFoundError:
        pass
    return interfaces


def get_bt_interfaces():
    """Get list of Bluetooth interfaces"""
    interfaces = []
    try:
        result = subprocess.run(['hciconfig'], capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if line.startswith('hci'):
                iface = line.split(':')[0]
                interfaces.append(iface)
    except FileNotFoundError:
        pass
    return interfaces


def get_monitor_interface(interface):
    """Check if interface is in monitor mode or get monitor interface"""
    try:
        result = subprocess.run(['iw', interface, 'info'], 
                               capture_output=True, text=True)
        if 'monitor' in result.stdout.lower():
            return interface
    except:
        pass
    return None


def enable_monitor_mode(interface):
    """Put interface into monitor mode"""
    print(Colors.info(f"Enabling monitor mode on {interface}..."))
    try:
        subprocess.run(['ip', 'link', 'set', interface, 'down'], check=True)
        subprocess.run(['iw', interface, 'set', 'type', 'monitor'], check=True)
        subprocess.run(['ip', 'link', 'set', interface, 'up'], check=True)
        print(Colors.success(f"{interface} is now in monitor mode"))
        return True
    except subprocess.CalledProcessError as e:
        print(Colors.error(f"Failed to enable monitor mode: {e}"))
        return False


def disable_monitor_mode(interface):
    """Put interface back to managed mode"""
    print(Colors.info(f"Disabling monitor mode on {interface}..."))
    try:
        subprocess.run(['ip', 'link', 'set', interface, 'down'], check=True)
        subprocess.run(['iw', interface, 'set', 'type', 'managed'], check=True)
        subprocess.run(['ip', 'link', 'set', interface, 'up'], check=True)
        print(Colors.success(f"{interface} is now in managed mode"))
        return True
    except subprocess.CalledProcessError as e:
        print(Colors.error(f"Failed to disable monitor mode: {e}"))
        return False


def select_interface(interfaces, iface_type=""):
    """Interactive interface selection"""
    if not interfaces:
        print(Colors.error(f"No {iface_type} interfaces found!"))
        return None
    
    if len(interfaces) == 1:
        print(Colors.info(f"Using interface: {interfaces[0]}"))
        return interfaces[0]
    
    print(f"\n{Colors.CYAN}Available {iface_type} interfaces:{Colors.RESET}")
    for i, iface in enumerate(interfaces, 1):
        print(f"  [{i}] {iface}")
    
    try:
        choice = int(input(Colors.prompt("Select interface: ")))
        if 1 <= choice <= len(interfaces):
            return interfaces[choice - 1]
    except (ValueError, KeyboardInterrupt):
        pass
    
    return None
