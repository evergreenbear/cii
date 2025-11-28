#!/usr/bin/env python3

import os
import sys
import subprocess
import shutil
from pathlib import Path

## TODO: perscribe types to all functions which use them

""" runCmd: alias to make running commands easier (a lot of that will happen here) """
# TODO: determine if last will actually be useful
def runCmd(cmd: str, debug: bool = True):
	if debug:
		print(f"+ RUNNING: {cmd}")
	last = 0
	try:
		with subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) as proc:
			for line in proc.stdout:
				print(line, end="")
				last = len(line.rstrip())
			proc.wait()
			if proc.returncode != 0:
				raise subprocess.CalledProcessError(proc.returncode, cmd)
			return last
	except subprocess.CalledProcessError:
		raise

""" getMountpoints: find whether a disk is mounted, and where """
# FIXME: determine whether to put this in Partitioner
def getMountpoints(disk: str) -> list[str]:
    # sanitize disk name
    disk = disk.replace("/dev/", "")

    # determine mountpoints via /proc/mount
    # determine mountpoints via /proc/mountss
    mountpoints = []
    with open("/proc/mounts") as f:
        for line in f:
            device, mountpoint, *_ = line.split()
            if device.startswith(f"/dev/{disk}"):
                mountpoints.append(mountpoint)
    return mountpoints

def clrScreen():
    print("\033[2J\033[H", end="")

""" getDiskInfo: for each valid disk on the system, acquire its name, capacity, and model info to return as dictionaries"""
def getDiskInfo():
    disks = []
    sys_block = Path("/sys/class/block")

    for dev in sys_block.iterdir():
        name = dev.name

        ## note to self: pathutils.Path() object lets you concatenate paths in this way, which looks like division

        # not a physical disk
        ## FIXME: remove loop0 exception when done testing
        if not (dev / "device").exists():
            if name != "loop0":
                continue

        # capacity, in 512-byte sectors
        size_file = dev / "size"
        try:
            size_bytes = int(size_file.read_text().strip()) * 512
            size_gb = round(size_bytes / (1024 ** 3), 2)
        except (FileNotFoundError, ValueError):
            size_bytes = size_gb = None

        # Model & Vendor
        model_file = dev / "device/model"
        vendor_file = dev / "device/vendor"
        model = model_file.read_text().strip() if model_file.exists() else "Unknown"
        vendor = vendor_file.read_text().strip() if vendor_file.exists() else ""

        disks.append({
            "name": name,
            "vendor": vendor,
            "model": model,
            "size_bytes": size_bytes,
            "size_gb": size_gb
        })

    return disks

## err(): print an error and exit with non-zero status (excepting when a second argument is supplied)
def err(msg="", exit="exit"):
    if msg:
        print(f"{colors['redBold']}-> ERROR: {colors['bold']}{msg}{colors['reset']}")
    if exit == "exit":
        sys.exit(1)

## FIXME: prune if ultimately unused
def msg(message):
    print(f"{message}{colors['reset']}")

"""partitioner: prepare a disk for OS installation, then write changes"""
class Partitioner:
    def __init__(self):
        self.disks = getDiskInfo()
        self.installTarget = None

    """ chooseDisks(): use amount of usable disks on system to determine if a prompt should be given"""
    def chooseDisk(self):
        # only one usable disk on system; go for it
        if len(self.disks) == 1:
            self.installTarget = f"/dev/{self.disks[0]['name']}"
            print(f"{colors['bold']}-> Disk {colors['cyanBold']}{self.installTarget} {colors['bold']}is the only detected disk on the system and has been {colors['cyanBold']}selected for installation{colors['reset']}.")

        # multiple disks, provide an interactive menu for one to be chosen
        else:
           self.promptDisks()

    """ promptDisks(): create a table of usable disks and prompt for which should be used """
    def promptDisks(self):
        print(colors['greenBold'] + "Disks found:" + colors['bold'])

        # table spacing
        name_width = max(len(d['name']) for d in self.disks)
        size_width = max(len(f"{d['size_gb']:.2f} GB") for d in self.disks)
        model_width = max(len(f"{d['vendor']} {d['model']}".strip()) for d in self.disks)
        mp_lists = {d["name"]: getMountpoints(d["name"]) for d in self.disks}
        mp_col = {name: ", ".join(mps) if mps else "" for name, mps in mp_lists.items()}
        mount_width = max(len(v) for v in mp_col.values()) if mp_col else 0

        # table formatting
        print(f"+{'-'*(name_width+2)}+{'-'*(size_width+2)}+{'-'*(model_width+2)}+{'-'*(mount_width+2)}+")
        print(f"| {colors['greenBold']}{'name'.ljust(name_width)}{colors['bold']} | "
            f"{colors['cyanBold']}{'capacity'.ljust(size_width)}{colors['bold']} | "
            f"{'model'.ljust(model_width)} | "
            f"{colors['cyanBold']}{'mounts'.ljust(mount_width)}{colors['bold']} |")
        print(f"+{'-'*(name_width+2)}+{'-'*(size_width+2)}+{'-'*(model_width+2)}+{'-'*(mount_width+2)}+")

        # disk listing
        for d in self.disks:
            model_full = f"{d['vendor']} {d['model']}".strip()
            mpoints = mp_col[d['name']]
            print(
                f"| {colors['greenBold']}{d['name'].ljust(name_width)}{colors['bold']} | "
                f"{colors['cyanBold']}{f'{d['size_gb']:.2f} GB'.rjust(size_width)}{colors['bold']} | "
                f"{model_full.ljust(model_width)} | "
                f"{colors['cyanBold']}{mpoints.ljust(mount_width)}{colors['bold']} |"
            )
        print(f"+{'-'*(name_width+2)}+{'-'*(size_width+2)}+{'-'*(model_width+2)}+{'-'*(mount_width+2)}+")
        print("")

        while True:
            target = input(f"{colors['greenBold']}Which disk would you like to install to?{colors['bold']}: ")
            if target in [d['name'] for d in self.disks]:
                self.installTarget = target
                break
            else:
                print(colors['redBold'] + "Invalid disk. Please try again." + colors['bold'])

    """ wipeDisk(): after prompting, erase disk entirely"""
    def wipeDisk(self):
        if self.installTarget is None:
            err("No disk has been selected to install to!")

        if not self.installTarget.startswith("/dev/"):
            self.installTarget = f"/dev/{self.installTarget}"

        print(f"{colors['magentaBold']}\nWARNING: ALL data on drive {colors['greenBold']}{self.installTarget} {colors['magentaBold']}will be ERASED.")
        print(f"{colors['bold']}If there is any existing data on the drive that is important to you, {colors['redBold']}back it up {colors['reset']}before proceeding!{colors['reset']}")
        doubleCheck = input(f"\n{colors['redBold']}Really continue? {colors['bold']}(Y/n): {colors['reset']}")
        if doubleCheck.lower() == "y":
            ## FIXME: DELETE ME
            if self.installTarget == "/dev/nvme0n1":
                err("don't wipe your shit!!! careful!!!")

            ### DRIVE LAYOUT:
            # /boot/efi: 2gb EFI partition
            # /        : btrfs root, remainder of disk space
            # --> @, @boot, @home, @var_cache, @var_log, @snapshots
            # make sure no data is already on drive

            ## FIXME: recomment in prod, silently fails for loop disk
            #runCmd(f"{suCmd} sfdisk --delete {self.installTarget}")
            runCmd(f"{suCmd} wipefs -a {self.installTarget}")
        else:
            err("You did not enter 'y', bailing out...")

    """ mkPartitions(): automatically partition drive for installation
        FIXME: allow for some kind of manual partitioning, Void Linux or archfi style?
    """
    def mkPartitions(self):
            # ensure we are naming partitions properly
            if self.installTarget[-1].isdigit():
                # {self.installTarget}p[num]; e.g. /dev/nvme0n1p1
                partitionName = f"{self.installTarget}p"
            else:
                # {self.installTarget}[num]; e.g. /dev/sda1
                partitionName = self.installTarget

            # NTS: sfdisk uses sectors; 1 sector = 512 bytes
            sfdisk_input = f"""
            label: gpt
            label-id: 12345678-1234-1234-1234-1234567890ab
            device: {self.installTarget}
            unit: sectors
            first-lba: 2048

            {partitionName}1 : start=     2048, size=4194304, type=C12A7328-F81F-11D2-BA4B-00A0C93EC93B, bootable
            {partitionName}2 : start=  4196352, type=0FC63DAF-8483-4772-8E79-3D69D8477DE4
            """

            subprocess.run(
                [f"{suCmd}", "sfdisk", "--wipe", "always", f"{self.installTarget}"],
                input=sfdisk_input,
                text=True,
                check=True
            )
            print("+ format done, partitioning now...")
            runCmd(f"{suCmd} mkfs.exfat {partitionName}1")
            runCmd(f"{suCmd} mkfs.btrfs {partitionName}2 -f")

            runCmd(f"{suCmd} mount {partitionName}2 /mnt")
            subvols = ["@", "@boot", "@home", "@snapshots", "@var_cache", "@var_log"]
            for subvol in subvols:
                runCmd(f"{suCmd} btrfs su cr /mnt/{subvol}")

            runCmd(f"{suCmd} umount /mnt")
            print("+ partitioning done, disk unmounted")

    def commit(self):
        self.wipeDisk()
        self.mkPartitions()

""" interactiveHub: sequence install menus"""
def interactiveHub():
    clrScreen()
    print(f"\n{colors['greenBold']}cii{colors['bold']}: the (unofficial) Chimera Interactive Installer\n")
    print(f"{colors['greenBold']}Welcome!\n{colors['bold']}Proceed through each section to install Chimera Linux.\nPermanent changes (e.g. to disk configuration) {colors['greenBold']}will not take effect{colors['bold']} until the end of the interactive menus.\n")

    # select drive for installation
    p = Partitioner()
    p.chooseDisk()
    p.commit()

    # bootstrap
    runCmd("curl -L https://raw.githubusercontent.com/chimera-linux/chimera-install-scripts/refs/heads/master/chimera-bootstrap -o /tmp/chimera-bootstrap")

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

    ## dependency satisfaction
    # commands, not package names
    neededCmds = ["curl", "sfdisk", "mkfs.exfat", "mkfs.btrfs", "luanti"]
    missing = []
    for cmd in neededCmds:
        if not shutil.which(cmd):
            missing.append(cmd)
    if missing:
        print(f"\n{colors['bold']}This script requires the following command-line tool(s) to be present on the system, which were not found:")
        for cmd in missing:
            print(f"{colors['redBold']}-> {colors['bold']}{cmd}{colors['reset']}")

            # auto-install missing packages if on a Chimera live ISO (or maybe Alpine too)
            if shutil.which("apk"):
                doInstall = input(f"\n{colors['greenBold']}Install them? ({colors['bold']}Y/n){colors['greenBold']}: {colors['bold']}")
                sys.stdout.write(colors['reset'])
                sys.stdout.flush()

                if doInstall.lower() == "y":
                    try:
                        getPkgs = " ".join(f"cmd:{cmd}" for cmd in missing)
                        runCmd(f"{suCmd} apk --no-interactive add {getPkgs}")
                    except:
                        for pkg in getPkgs.split():
                            if not runCmd(f"apk search {pkg}"):
                                print(f"\n{colors['redBold']}-> Package providing command {colors['bold']}`{pkg.removeprefix('cmd:')}` {colors['redBold']}could not be found!")
                            else:
                                print(f"\n{colors['redBold']}Package {colors['bold']}{pkg.removeprefix('cmd:')}{colors['redBold']} was found but could not be installed. Please do so manually.")
                        err("Something went wrong installing required packages")
                else:
                    err("You did not enter 'y', bailing out...")
            else:
                print(f"\n{colors['bold']}Please install them before running this script.{colors['reset']}")
                err()

    # send things off to user-facing install menus
    interactiveHub()

## necessary global variables
suCmd = "doas" if shutil.which("doas") else "sudo"

if __name__ == "__main__":
    main()
