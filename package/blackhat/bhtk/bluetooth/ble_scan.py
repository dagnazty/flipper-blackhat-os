#!/usr/bin/env python3
"""BLE Device Scanner"""

import subprocess
import time
from ..utils.colors import Colors
from ..utils.interfaces import get_bt_interfaces, select_interface
from ..utils.logger import Logger


def scan(duration=10):
    """
    Scan for BLE devices using hcitool or bluetoothctl
    
    Args:
        duration: Scan duration in seconds
    """
    devices = []
    
    print(Colors.info(f"Scanning for BLE devices ({duration}s)..."))
    
    # Try bluetoothctl first
    try:
        # Start scan
        proc = subprocess.Popen(
            ['bluetoothctl'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Send scan command
        proc.stdin.write("scan on\n")
        proc.stdin.flush()
        
        # Wait for scan duration
        time.sleep(duration)
        
        # Stop scan and get devices
        proc.stdin.write("scan off\n")
        proc.stdin.write("devices\n")
        proc.stdin.write("quit\n")
        proc.stdin.flush()
        
        stdout, _ = proc.communicate(timeout=5)
        
        # Parse devices
        for line in stdout.split('\n'):
            if 'Device' in line:
                parts = line.split()
                if len(parts) >= 3:
                    mac = parts[1]
                    name = ' '.join(parts[2:])
                    devices.append({'mac': mac, 'name': name})
                    
    except Exception as e:
        print(Colors.warning(f"bluetoothctl failed, trying hcitool: {e}"))
        
        # Fallback to hcitool
        try:
            # Classic scan
            result = subprocess.run(
                ['hcitool', 'scan', '--flush'],
                capture_output=True, text=True, timeout=duration + 5
            )
            
            for line in result.stdout.split('\n'):
                if '\t' in line:
                    parts = line.strip().split('\t')
                    if len(parts) >= 2:
                        devices.append({'mac': parts[0], 'name': parts[1]})
            
            # BLE scan
            result = subprocess.run(
                ['hcitool', 'lescan', '--duplicates'],
                capture_output=True, text=True, timeout=duration
            )
            
        except subprocess.TimeoutExpired:
            pass
        except FileNotFoundError:
            print(Colors.error("hcitool not found"))
    
    return devices


def display_devices(devices):
    """Display discovered devices"""
    if not devices:
        print(Colors.warning("No devices found"))
        return
    
    print(f"\n{Colors.CYAN}{'MAC Address':<20} {'Name'}{Colors.RESET}")
    print("-" * 50)
    
    for dev in devices:
        mac = dev.get('mac', 'Unknown')
        name = dev.get('name', '<unnamed>')
        print(f"{mac:<20} {name}")
    
    print(f"\n{Colors.info(f'Found {len(devices)} devices')}")


def interactive():
    """Interactive BLE scanner"""
    logger = Logger("ble_scan")
    
    # Check for BT interface
    interfaces = get_bt_interfaces()
    if not interfaces:
        print(Colors.error("No Bluetooth interfaces found"))
        return
    
    print(Colors.info(f"Using interface: {interfaces[0]}"))
    
    # Get scan duration
    duration = input(Colors.prompt("Scan duration (seconds) [10]: ")).strip()
    duration = int(duration) if duration else 10
    
    logger.info(f"BLE scan for {duration}s")
    
    try:
        devices = scan(duration)
        display_devices(devices)
        
        for dev in devices:
            logger.raw(f"{dev.get('mac')} | {dev.get('name')}")
            
    except KeyboardInterrupt:
        print(Colors.warning("\nScan stopped"))
