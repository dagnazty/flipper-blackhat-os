# Flipper Blackhat OS

A WiFi security testing OS built on Linux for penetration testing and network analysis. Designed to work with the Flipper Blackhat.

## Features

### BlackHat ToolKit (BHTK)
A menu-driven Python pentesting suite with integrated attack modules:

| Module | Tools |
|--------|-------|
| **WiFi** | Scanner, Deauth, Handshake Capture, Evil Twin |
| **Network** | Port Scan, ARP Spoof, Sniffer, Credential Harvester |
| **Bluetooth** | BLE Scanner, Device Recon, Spoofing |
| **Recon** | Banner Grab, Service Detection, Subdomain Finder |
| **Automation** | WiFi Audit, Network Discovery, Quick Recon |

```bash
bhtk              # Interactive menu
bhtk wifi scan    # Direct command
```

### Kali Linux Tools
Pre-installed pentesting tools from Kali repositories:
- **WiFi**: aircrack-ng, hcxdumptool, hcxtools, pixiewps, reaver, mdk4, bettercap, macchanger, wifite
- **Network**: responder, impacket-scripts, masscan, ettercap, hydra, nmap, netcat, tcpdump
- **Bluetooth**: btscanner, bluez-tools

## Documentation
For complete functionality reference and usage examples, see [BLACKHAT_REFERENCE.md](BLACKHAT_REFERENCE.md).

## Releases
The best way to get your hands on all the most recent features is the [nightly build](https://github.com/dagnazty/flipper-blackhat-os/actions). Click the most recent build and find the OS artifacts at the bottom. Flash to SD card using `dd` or your preferred imaging tool.

## Build

### Armbian (Recommended)
```bash
git submodule update --init
./build_armbian.sh
```

### Buildroot
Buildroot CI is disabled in this repository. Armbian is the supported build path.

## Credits
- [o7-machinehum](https://github.com/o7-machinehum) - Original Flipper Blackhat hardware and OS
- [Flipper Blackhat Hardware](https://github.com/o7-machinehum/flipper-blackhat)
- [Armbian](https://www.armbian.com/)
- [Kali Linux](https://www.kali.org/)
