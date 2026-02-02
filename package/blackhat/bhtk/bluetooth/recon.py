#!/usr/bin/env python3
"""Bluetooth Device Reconnaissance"""

import subprocess
from ..utils.colors import Colors
from ..utils.logger import Logger


def get_device_info(mac):
    """Get detailed info about a Bluetooth device"""
    info = {'mac': mac}
    
    try:
        # Use bluetoothctl info
        proc = subprocess.Popen(
            ['bluetoothctl'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        proc.stdin.write(f"info {mac}\n")
        proc.stdin.write("quit\n")
        proc.stdin.flush()
        
        stdout, _ = proc.communicate(timeout=5)
        
        for line in stdout.split('\n'):
            line = line.strip()
            if 'Name:' in line:
                info['name'] = line.split('Name:')[-1].strip()
            elif 'Alias:' in line:
                info['alias'] = line.split('Alias:')[-1].strip()
            elif 'Class:' in line:
                info['class'] = line.split('Class:')[-1].strip()
            elif 'Paired:' in line:
                info['paired'] = 'yes' in line.lower()
            elif 'Trusted:' in line:
                info['trusted'] = 'yes' in line.lower()
            elif 'Blocked:' in line:
                info['blocked'] = 'yes' in line.lower()
            elif 'Connected:' in line:
                info['connected'] = 'yes' in line.lower()
            elif 'UUID:' in line:
                if 'uuids' not in info:
                    info['uuids'] = []
                info['uuids'].append(line.split('UUID:')[-1].strip())
                
    except Exception as e:
        print(Colors.warning(f"Could not get device info: {e}"))
    
    return info


def display_info(info):
    """Display device info"""
    print(f"\n{Colors.CYAN}=== Device Information ==={Colors.RESET}")
    print(f"MAC Address: {info.get('mac', 'Unknown')}")
    print(f"Name: {info.get('name', 'Unknown')}")
    print(f"Alias: {info.get('alias', 'N/A')}")
    print(f"Class: {info.get('class', 'Unknown')}")
    print(f"Paired: {'Yes' if info.get('paired') else 'No'}")
    print(f"Connected: {'Yes' if info.get('connected') else 'No'}")
    
    if info.get('uuids'):
        print(f"\n{Colors.CYAN}Services/UUIDs:{Colors.RESET}")
        for uuid in info['uuids']:
            print(f"  • {uuid}")


def gather(target=None):
    """Gather recon info on a device"""
    if not target:
        print(Colors.error("Target MAC required"))
        return None
    
    print(Colors.info(f"Gathering info on {target}..."))
    info = get_device_info(target)
    display_info(info)
    return info


def interactive():
    """Interactive Bluetooth recon"""
    logger = Logger("bt_recon")
    
    # Option to scan first
    scan_first = input(Colors.prompt("Scan for devices first? [y/N]: ")).strip().lower()
    
    if scan_first == 'y':
        from . import ble_scan
        devices = ble_scan.scan(10)
        ble_scan.display_devices(devices)
        
        if devices:
            print("\nSelect a device by number, or enter MAC:")
            for i, dev in enumerate(devices, 1):
                print(f"  [{i}] {dev.get('mac')} - {dev.get('name')}")
            
            choice = input(Colors.prompt("Selection: ")).strip()
            try:
                idx = int(choice) - 1
                target = devices[idx]['mac']
            except:
                target = choice
        else:
            target = input(Colors.prompt("Target MAC: ")).strip()
    else:
        target = input(Colors.prompt("Target MAC: ")).strip()
    
    if not target:
        print(Colors.error("Target required"))
        return
    
    logger.info(f"BT recon: {target}")
    gather(target)
