#!/usr/bin/env python3

import os, sys, subprocess

## runCmd: alias to make running commands easier (a lot of that will happen here)
def runCmd(cmd: str) -> str:
    return subprocess.run(cmd, capture_output=True, text=True, shell=True).stdout.strip()

## getMountpoints: find whether a disk is mounted, and where
def getMountpoints(disk: str) -> list[str]:
    mountpoints = []
    with open("/proc/mounts") as f:
        for line in f:
            device, mountpoint, *_ = line.split()
            if device.startswith(f"/dev/{disk}"):
                mountpoints.append(mountpoint)
    #print(f"MOUNTS: {mountpoints}")
    return mountpoints

## err: print an error and exit with non-zero status
#def err(msg):


def msg(message):
    print(f"{message}{colors["reset"]}")

"""partitioner: prepare a disk for OS installation, then write changes"""
class Partitioner:
    def __init__(self):
        self.disks = []
        self.installTarget = None

    def configure(self):
        ## acquire and print list of disks
        for dev in os.listdir("/sys/block"):
            if dev.startswith(("loop", "ram")):
                continue
            else:
                self.disks.append(dev)

        self.disks.sort()
        #self.disks = runCmd("lsblk -d -n -o NAME").splitlines()
        maxDiskLen = max(len(d) for d in self.disks)

        print(f"{colors["cyanBold"]}disks:\n------")
        for disk in self.disks:
            dCapacity = runCmd(f"lsblk -d -n -o SIZE /dev/{disk}")
            dModel = runCmd(f"lsblk -d -n -o MODEL /dev/{disk}")

            # list disk name, capacity, and model
            print(f"{colors["cyanBold"]}{disk:<{maxDiskLen}}{colors["bold"]}: {dCapacity} total, {dModel}{colors["reset"]}")

            # and mountpoints, if any
            mountpoints = getMountpoints(disk)
            if mountpoints:
                #print(f"{' ' * maxDiskLen}{colors["greenBold"]}mounted {colors["bold"]}at {colors["greenBold"]}" + ", ".join(mountpoints) + colors["reset"])
                print(f"-> {colors["greenBold"]}mounted {colors["bold"]}at {colors["greenBold"]}" + ", ".join(mountpoints) + colors["reset"])
    
        ## prompt for target disk until acceptable input is given
        while True:
            self.installTarget = input(f"\n{colors["bold"]}Which disk yould you like to install to? [{colors["greenBold"]}{self.disks[0]}{colors["bold"]}]: ")
            self.installTarget = self.installTarget.removeprefix("/dev/")
            if self.installTarget in self.disks or self.installTarget == "":
                # only assign default (first drive as sorted alphabetically) if input was empty
                self.installTarget = self.installTarget or self.disks[0]
                return 0                            
            elif self.installTarget not in self.disks:
                print(f"{colors['redBold']}-> {colors['bold']}{self.installTarget} {colors['redBold']}is not a valid disk. See the list above list of recognized disks.")

    def commit(self):
        print(f"{colors["magentaBold"]}WARNING: ALL data on drive {colors["cyanBold"]}/dev/{self.installTarget} {colors["magentaBold"]}will be ERASED.\n")
        doubleCheck = input(f"{colors["cyanBold"]}Really continue? {colors["bold"]}(Y/n): {colors["reset"]}")
        if doubleCheck.lower() == "y":
            # FIXME: perform partitioning & formatting
            print(f"\n{colors["bold"]}Mock run, exiting...{colors["reset"]}")
            runCmd("ls -la")
        else:
            sys.exit(f"\n{colors['redBold']}-> You did not enter {colors['bold']}y{colors['redBold']}, bailing out...{colors['reset']}")

def main():
    ## output colorization (unless NO_COLOR is set)
    global colors
    if os.environ.get('NO_COLOR'):
        colors = {
            "red": '',
            "redBold": '',
            "greenBold": "",
            "cyan": '',
            "cyanBold": '',
            "magenta": '',
            "magentaBold": '',
            "bold": '',
            "reset": ''
            }
    else:
        colors = {
            "red": '\033[0;31m',
            "redBold": '\033[01;31m',
            "greenBold": '\033[01;32m',
            "cyan": '\033[0;36m',
            "cyanBold": '\033[01;36m',
            "magenta": '\033[0;35m',
            "magentaBold": '\033[01;35m',
            "bold": '\033[0;1m',
            "reset": '\033[0m'
            }
        #bgClrBLUE = '\[48;5;24m'
    
    print(f"{colors["greenBold"]}cii{colors["bold"]}: the (unofficial) Chimera Interactive Installer\n")
    print(f"{colors["greenBold"]}Welcome!\n{colors["bold"]}Proceed through each section to install Chimera Linux.\nPermanent changes (e.g. to disk configuration) {colors["greenBold"]}will not take effect{colors["bold"]} until the end of the interactive menus.\n")
    # prepare drive partition for later format and install
    partition = Partitioner()
    partition.configure()       
    partition.commit()


if __name__ == "__main__":
    main()
