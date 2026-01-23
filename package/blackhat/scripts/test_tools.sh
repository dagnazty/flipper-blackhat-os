#!/bin/bash
# Flipper Blackhat OS - Functional Tool Tests
# Run as root on the device

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS=0
FAIL=0

test_tool() {
    local name="$1"
    local cmd="$2"
    echo -n "Testing $name... "
    if eval "$cmd" &>/dev/null; then
        echo -e "${GREEN}✅ PASS${NC}"
        ((PASS++))
    else
        echo -e "${RED}❌ FAIL${NC}"
        ((FAIL++))
    fi
}

echo "======================================================"
echo "   Flipper Blackhat OS - Functional Tool Tests"
echo "======================================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run as root${NC}"
    exit 1
fi

echo "--- WiFi Tools (Tier 1) ---"
test_tool "aircrack-ng" "aircrack-ng --help"
test_tool "hcxdumptool" "hcxdumptool --help"
test_tool "hcxpcapngtool" "hcxpcapngtool --help"
test_tool "pixiewps" "pixiewps --help"
test_tool "reaver" "reaver --help"
test_tool "wash" "wash --help"
test_tool "mdk4" "mdk4 --help"
test_tool "bettercap" "bettercap -version"
test_tool "macchanger" "macchanger --help"
test_tool "wifite" "wifite --help"

echo ""
echo "--- Network Tools (Tier 2) ---"
test_tool "responder" "responder --help"
test_tool "impacket-smbserver" "impacket-smbserver --help"
test_tool "masscan" "masscan --help"
test_tool "ettercap" "ettercap --help"
test_tool "hydra" "hydra -h"
test_tool "nmap" "nmap --version"
test_tool "netcat" "nc -h"
test_tool "tcpdump" "tcpdump --version"

echo ""
echo "--- Bluetooth Tools (Tier 3) ---"
test_tool "btscanner" "btscanner --help"
test_tool "hciconfig" "hciconfig --help"
test_tool "bluetoothctl" "bluetoothctl --version"

echo ""
echo "--- Kali Top10 Tools ---"
test_tool "metasploit" "msfconsole -h"
test_tool "john" "john --help"
test_tool "sqlmap" "sqlmap --version"
test_tool "wireshark-cli" "tshark --version"
test_tool "burpsuite" "which burpsuite"
test_tool "nikto" "nikto -Version"
test_tool "hashcat" "hashcat --help"

echo ""
echo "======================================================"
echo "                    RESULTS"
echo "======================================================"
echo -e "Passed: ${GREEN}$PASS${NC}"
echo -e "Failed: ${RED}$FAIL${NC}"
echo "Total:  $((PASS + FAIL))"
echo ""

# Quick interface check
echo "--- Interface Detection ---"
echo "WiFi interfaces:"
iw dev 2>/dev/null | grep Interface || echo "  No WiFi interfaces found"
echo ""
echo "Bluetooth interfaces:"
hciconfig 2>/dev/null | grep -E "^hci" || echo "  No Bluetooth interfaces found"
