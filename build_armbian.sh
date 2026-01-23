#!/bin/bash
set -e
cd "$(dirname "$0")"

kver="edge" # Edge or current

cd armbian
git reset --hard
git clean -fd
cd ..

# rm -rf armbian/userpatches/
rsync -av armbian_config/userpatches/ armbian/userpatches/
rsync -av armbian_config/config/ armbian/config/

# Fix: Remove libfuse2t64 from forky/trixie packages (not available for ARM)
sed -i.bak '/libfuse2t64/d' armbian/config/cli/trixie/main/packages.additional
sed -i.bak '/libfuse2t64/d' armbian/config/cli/sid/main/packages.additional

# Add kernel patches
if [[ ${kver} == "edge" ]]; then
    cp patches/linux/0002-rtw88.patch armbian/userpatches/kernel/archive/sunxi-6.16/rtw88.patch
    cp patches/linux/0003-st7701.patch armbian/userpatches/kernel/archive/sunxi-6.16/st7701.patch
elif [[ ${kver} == "current" ]]; then
    cp patches/linux/0003-st7701.patch armbian/userpatches/kernel/archive/sunxi-6.12/st7701.patch
else
    echo "Incorrect Kernel Version"
    exit
fi

# Install packages needed for bh scripts (macOS compatible)
mkdir -p armbian/userpatches/overlay/usr/local/bin
cp package/blackhat/src/blackhat.sh armbian/userpatches/overlay/usr/local/bin/bh
chmod 755 armbian/userpatches/overlay/usr/local/bin/bh
cp package/blackhat/src/evil_portal.py armbian/userpatches/overlay/usr/local/bin/
chmod 755 armbian/userpatches/overlay/usr/local/bin/evil_portal.py
cp package/blackhat/src/telegram.py armbian/userpatches/overlay/usr/local/bin/
chmod 755 armbian/userpatches/overlay/usr/local/bin/telegram.py

mkdir -p armbian/userpatches/overlay/boot/bh
cp package/blackhat/src/blackhat.conf armbian/userpatches/overlay/boot/bh/blackhat.conf
chmod 644 armbian/userpatches/overlay/boot/bh/blackhat.conf

mkdir -p armbian/userpatches/overlay/boot/bh/scripts
cp -a package/blackhat/scripts/. armbian/userpatches/overlay/boot/bh/scripts/

# Install the init script
cp rootfs_overlay/etc/init.d/S51bh_init armbian/userpatches/overlay/usr/local/bin/bh_init
chmod 755 armbian/userpatches/overlay/usr/local/bin/bh_init

# Add additional packages
PKG_CONF="armbian/config/cli/trixie/main/packages.additional"
echo usb-modeswitch >> $PKG_CONF

cd armbian

./compile.sh build \
    BOARD=flipper-blackhat \
    BRANCH=${kver} \
    BUILD_MINIMAL=no \
    KERNEL_CONFIGURE=no \
    ENABLE_EXTENSIONS="kali" \
    KEEP_ORIGINAL_OS_RELEASE=yes \
    RELEASE=forky

echo ************ Built Image ************
echo "sudo dd if=armbian/output/images/Armbian-unofficial_26.02.0-trunk_Flipper-blackhat_forky_edge_6.16.8-kali.img of=/dev/sdd bs=4M conv=fsync status=progress"
echo *************************************
