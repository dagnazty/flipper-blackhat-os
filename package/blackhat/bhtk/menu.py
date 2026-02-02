#!/usr/bin/env python3
"""
Interactive Menu System for BlackHat ToolKit
"""

import os
import sys
from .utils.colors import Colors


class Menu:
    """Base menu class"""
    
    def __init__(self, title, options):
        self.title = title
        self.options = options  # List of (name, handler) tuples
    
    def display(self):
        """Display the menu"""
        os.system('clear' if os.name == 'posix' else 'cls')
        
        width = 50
        print(f"{Colors.CYAN}╔{'═' * width}╗{Colors.RESET}")
        print(f"{Colors.CYAN}║{Colors.BOLD}{self.title.center(width)}{Colors.RESET}{Colors.CYAN}║{Colors.RESET}")
        print(f"{Colors.CYAN}╠{'═' * width}╣{Colors.RESET}")
        
        for i, (name, _) in enumerate(self.options, 1):
            line = f"  [{i}] {name}"
            padding = width - len(line)
            print(f"{Colors.CYAN}║{Colors.RESET}{line}{' ' * padding}{Colors.CYAN}║{Colors.RESET}")
        
        # Exit option
        line = "  [0] Back / Exit"
        padding = width - len(line)
        print(f"{Colors.CYAN}║{Colors.RESET}{line}{' ' * padding}{Colors.CYAN}║{Colors.RESET}")
        
        print(f"{Colors.CYAN}╚{'═' * width}╝{Colors.RESET}")
    
    def get_choice(self):
        """Get user choice"""
        try:
            choice = input(f"\n{Colors.GREEN}[>]{Colors.RESET} Select option: ")
            return int(choice)
        except (ValueError, KeyboardInterrupt):
            return -1
    
    def run(self):
        """Run menu loop"""
        while True:
            self.display()
            choice = self.get_choice()
            
            if choice == 0:
                return
            elif 1 <= choice <= len(self.options):
                name, handler = self.options[choice - 1]
                try:
                    handler()
                except Exception as e:
                    print(f"{Colors.RED}[!] Error: {e}{Colors.RESET}")
                input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.RESET}")
            else:
                print(f"{Colors.RED}[!] Invalid option{Colors.RESET}")


class MainMenu(Menu):
    """Main menu for BlackHat ToolKit"""
    
    def __init__(self):
        options = [
            ("WiFi Attacks", self.wifi_menu),
            ("Network Attacks", self.network_menu),
            ("Bluetooth Attacks", self.bluetooth_menu),
            ("Reconnaissance", self.recon_menu),
            ("Automation", self.automation_menu),
            ("System Info", self.system_info),
        ]
        super().__init__("BLACKHAT TOOLKIT v1.0", options)
    
    def wifi_menu(self):
        from .wifi import scanner, deauth, handshake, evil_twin
        menu = Menu("WiFi Attacks", [
            ("Scan Networks", scanner.interactive),
            ("Deauth Attack", deauth.interactive),
            ("Capture Handshake", handshake.interactive),
            ("Evil Twin AP", evil_twin.interactive),
        ])
        menu.run()
    
    def network_menu(self):
        from .network import portscan, arp_spoof, sniffer, harvester
        menu = Menu("Network Attacks", [
            ("Port Scanner", portscan.interactive),
            ("ARP Spoof", arp_spoof.interactive),
            ("Packet Sniffer", sniffer.interactive),
            ("Credential Harvester", harvester.interactive),
        ])
        menu.run()
    
    def bluetooth_menu(self):
        from .bluetooth import ble_scan, recon, spoof
        menu = Menu("Bluetooth Attacks", [
            ("BLE Scanner", ble_scan.interactive),
            ("Device Recon", recon.interactive),
            ("Spoof Device", spoof.interactive),
        ])
        menu.run()
    
    def recon_menu(self):
        from .recon import banner, services, subdomain
        menu = Menu("Reconnaissance", [
            ("Banner Grabber", banner.interactive),
            ("Service Detection", services.interactive),
            ("Subdomain Finder", subdomain.interactive),
        ])
        menu.run()
    
    def automation_menu(self):
        from .automation import workflows
        menu = Menu("Automation", [
            ("Full WiFi Audit", workflows.wifi_audit),
            ("Network Discovery", workflows.network_discovery),
            ("Quick Recon", workflows.quick_recon),
        ])
        menu.run()
    
    def system_info(self):
        """Display system and interface info"""
        from .utils.interfaces import get_wifi_interfaces, get_bt_interfaces
        
        print(f"\n{Colors.CYAN}=== System Information ==={Colors.RESET}\n")
        
        # WiFi interfaces
        print(f"{Colors.GREEN}WiFi Interfaces:{Colors.RESET}")
        wifi_ifaces = get_wifi_interfaces()
        if wifi_ifaces:
            for iface in wifi_ifaces:
                print(f"  • {iface}")
        else:
            print(f"  {Colors.YELLOW}No WiFi interfaces found{Colors.RESET}")
        
        # Bluetooth interfaces  
        print(f"\n{Colors.GREEN}Bluetooth Interfaces:{Colors.RESET}")
        bt_ifaces = get_bt_interfaces()
        if bt_ifaces:
            for iface in bt_ifaces:
                print(f"  • {iface}")
        else:
            print(f"  {Colors.YELLOW}No Bluetooth interfaces found{Colors.RESET}")
        
        print()
