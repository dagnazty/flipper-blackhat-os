#!/usr/bin/env python3
"""
BlackHat ToolKit - Main Entry Point
Run with: python -m bhtk or bhtk command
"""

import sys
import argparse
from .menu import MainMenu
from . import __version__


def check_root():
    """Ensure running as root"""
    import os
    if os.geteuid() != 0:
        print("\033[91m[!] This toolkit requires root privileges.\033[0m")
        print("    Run with: sudo bhtk")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        prog='bhtk',
        description='BlackHat ToolKit - Pentesting Suite for Flipper Blackhat OS'
    )
    parser.add_argument('-v', '--version', action='version', version=f'bhtk {__version__}')
    
    subparsers = parser.add_subparsers(dest='module', help='Module to run')
    
    # WiFi subcommands
    wifi_parser = subparsers.add_parser('wifi', help='WiFi attack tools')
    wifi_parser.add_argument('action', choices=['scan', 'deauth', 'handshake', 'eviltwin'],
                            help='WiFi action to perform')
    wifi_parser.add_argument('-i', '--interface', help='WiFi interface')
    wifi_parser.add_argument('-t', '--target', help='Target BSSID/MAC')
    
    # Network subcommands
    net_parser = subparsers.add_parser('network', help='Network attack tools')
    net_parser.add_argument('action', choices=['scan', 'arp', 'sniff', 'harvest'],
                           help='Network action to perform')
    net_parser.add_argument('-t', '--target', help='Target IP/range')
    
    # Bluetooth subcommands
    bt_parser = subparsers.add_parser('bluetooth', help='Bluetooth attack tools')
    bt_parser.add_argument('action', choices=['scan', 'recon', 'spoof'],
                          help='Bluetooth action to perform')
    
    # Recon subcommands
    recon_parser = subparsers.add_parser('recon', help='Reconnaissance tools')
    recon_parser.add_argument('action', choices=['banner', 'services', 'subdomain'],
                             help='Recon action to perform')
    recon_parser.add_argument('-t', '--target', help='Target host/domain')
    
    args = parser.parse_args()
    
    check_root()
    
    if args.module is None:
        # No subcommand - launch interactive menu
        menu = MainMenu()
        menu.run()
    else:
        # Direct command mode
        run_direct_command(args)


def run_direct_command(args):
    """Execute direct CLI commands"""
    if args.module == 'wifi':
        from .wifi import scanner, deauth, handshake, evil_twin
        if args.action == 'scan':
            scanner.scan(args.interface)
        elif args.action == 'deauth':
            deauth.attack(args.interface, args.target)
        elif args.action == 'handshake':
            handshake.capture(args.interface, args.target)
        elif args.action == 'eviltwin':
            evil_twin.setup(args.interface)
    
    elif args.module == 'network':
        from .network import portscan, arp_spoof, sniffer, harvester
        if args.action == 'scan':
            portscan.scan(args.target)
        elif args.action == 'arp':
            arp_spoof.attack(args.target)
        elif args.action == 'sniff':
            sniffer.capture()
        elif args.action == 'harvest':
            harvester.run()
    
    elif args.module == 'bluetooth':
        from .bluetooth import ble_scan, recon, spoof
        if args.action == 'scan':
            ble_scan.scan()
        elif args.action == 'recon':
            recon.gather()
        elif args.action == 'spoof':
            spoof.run()
    
    elif args.module == 'recon':
        from .recon import banner, services, subdomain
        if args.action == 'banner':
            banner.grab(args.target)
        elif args.action == 'services':
            services.detect(args.target)
        elif args.action == 'subdomain':
            subdomain.find(args.target)


if __name__ == '__main__':
    main()
