#!/usr/bin/env python3
"""
Android Device Manager Pro v10.0
Advanced Android device management tool with real-time operations
Author: Shrabon Gomez
"""

import os
import sys
import time
import json
import shutil
import hashlib
import threading
import queue
import tempfile
import zipfile
import tarfile
import platform
import datetime
import subprocess
import itertools
import signal
import atexit
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed

# ================= CONSTANTS & CONFIGURATION =================
VERSION = "10.0"
AUTHOR = "SHRABON GOMEZ"
GITHUB = "github.com/sharbongomes2003"
TELEGRAM = "t.me/Shrabongomez"
FACEBOOK = "https://www.facebook.com/share/1B4TRBkyN3/"
PASSWORD = "SHRABON2.0"

# ================= COLOR MANAGEMENT =================
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    FAINT = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    BLINK = "\033[5m"
    
    # Regular Colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # Bright Colors
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"
    
    # Background Colors
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"
    
    # Bright Background Colors
    BG_BRIGHT_BLACK = "\033[100m"
    BG_BRIGHT_RED = "\033[101m"
    BG_BRIGHT_GREEN = "\033[102m"
    BG_BRIGHT_YELLOW = "\033[103m"
    BG_BRIGHT_BLUE = "\033[104m"
    BG_BRIGHT_MAGENTA = "\033[105m"
    BG_BRIGHT_CYAN = "\033[106m"
    BG_BRIGHT_WHITE = "\033[107m"

# Short color variables for compatibility
Z = Colors.RESET
R = Colors.BRIGHT_RED
G = Colors.BRIGHT_GREEN
Y = Colors.BRIGHT_YELLOW
B = Colors.BRIGHT_BLUE
M = Colors.BRIGHT_MAGENTA
C = Colors.BRIGHT_CYAN
W = Colors.BRIGHT_WHITE
H = Colors.BRIGHT_GREEN  # Alias

# ================= DATACLASSES & ENUMS =================
class DeviceState(Enum):
    DISCONNECTED = "disconnected"
    BOOTLOADER = "bootloader"
    FASTBOOT = "fastboot"
    ADB = "adb"
    RECOVERY = "recovery"
    SIDELOAD = "sideload"
    SYSTEM = "system"

class SlotInfo(Enum):
    A = "a"
    B = "b"
    UNKNOWN = "unknown"

class PartitionType(Enum):
    NORMAL = "normal"
    DYNAMIC = "dynamic"
    SUPER = "super"
    LOGICAL = "logical"

@dataclass
class DeviceInfo:
    serial: str
    state: DeviceState
    product: str = ""
    model: str = ""
    device: str = ""
    bootloader_version: str = ""
    baseband_version: str = ""
    secure_boot: bool = False
    unlocked: bool = False
    slot_current: SlotInfo = SlotInfo.UNKNOWN
    slot_suffix: str = ""
    is_ab: bool = False
    dynamic_partitions: bool = False
    super_partition_size: int = 0

@dataclass
class PartitionInfo:
    name: str
    type: PartitionType
    size: int
    logical: bool = False
    slot_suffix: str = ""
    mounted: bool = False

@dataclass
class FlashOperation:
    partition: str
    image_path: str
    slot: SlotInfo = SlotInfo.UNKNOWN
    verify: bool = True
    force: bool = False

# ================= UTILITY FUNCTIONS =================
def xox(text: str, delay: float = 0.001) -> None:
    """Print text with typing effect"""
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        if delay > 0:
            time.sleep(delay)
    print()

def clear_screen() -> None:
    """Clear terminal screen"""
    os.system('cls' if platform.system() == 'Windows' else 'clear')

def print_progress_bar(iteration: int, total: int, prefix: str = '', 
                      suffix: str = '', length: int = 50, fill: str = '█') -> None:
    """Display progress bar"""
    percent = f"{100 * (iteration / float(total)):.1f}"
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    sys.stdout.write(f'\r{prefix} |{bar}| {percent}% {suffix}')
    sys.stdout.flush()
    if iteration == total:
        print()

def calculate_file_hash(filepath: str, algorithm: str = 'md5') -> str:
    """Calculate file hash for verification"""
    hash_func = getattr(hashlib, algorithm)()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hash_func.update(chunk)
    return hash_func.hexdigest()

def format_size(size_bytes: int) -> str:
    """Format bytes to human readable size"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"

def check_binary_exists(binary: str) -> bool:
    """Check if binary exists in PATH"""
    return shutil.which(binary) is not None

def run_command(cmd: List[str], timeout: int = 30, 
                capture_output: bool = True, 
                check: bool = False) -> subprocess.CompletedProcess:
    """Run shell command with timeout and error handling"""
    try:
        result = subprocess.run(
            cmd,
            timeout=timeout,
            capture_output=capture_output,
            text=True,
            check=check
        )
        return result
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Command timed out after {timeout} seconds")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Command failed with exit code {e.returncode}: {e.stderr}")
    except FileNotFoundError:
        raise RuntimeError(f"Command not found: {cmd[0]}")

def validate_image_file(filepath: str, expected_types: List[str] = None) -> bool:
    """Validate Android image file"""
    if not os.path.exists(filepath):
        return False
    
    # Check file signature
    with open(filepath, 'rb') as f:
        header = f.read(8)
        
        # Android sparse image
        if header[:4] == b'\x3A\xFF\x26\xED':
            return True
        
        # Android boot image
        if header[:8] == b'ANDROID!':
            return True
        
        # Check file extension
        ext = os.path.splitext(filepath)[1].lower()
        if ext in ['.img', '.bin', '.mbn']:
            return True
            
        # Check for gzipped file
        if header[:2] == b'\x1F\x8B':
            return True
    
    return False

def extract_boot_info(boot_img_path: str) -> Dict[str, Any]:
    """Extract information from boot image"""
    # This is a simplified version
    # In production, use pybootimg or similar library
    info = {
        'name': os.path.basename(boot_img_path),
        'size': os.path.getsize(boot_img_path),
        'valid': False,
        'kernel_size': 0,
        'ramdisk_size': 0,
        'page_size': 4096,
        'cmdline': '',
        'os_version': '',
        'os_patch_level': ''
    }
    
    try:
        with open(boot_img_path, 'rb') as f:
            header = f.read(4096)
            
            if header[:8] == b'ANDROID!':
                info['valid'] = True
                # Parse header (simplified)
                # Actual parsing would use struct.unpack
                info['kernel_size'] = int.from_bytes(header[8:12], 'little')
                info['ramdisk_size'] = int.from_bytes(header[12:16], 'little')
                
    except Exception:
        pass
    
    return info

# ================= ANDROID DEVICE MANAGER =================
class AndroidDeviceManager:
    def __init__(self):
        self.device_info: Optional[DeviceInfo] = None
        self.connected = False
        self.operation_queue = queue.Queue()
        self.log_file = None
        self.start_logging()
        
    def start_logging(self):
        """Start logging operations"""
        log_dir = Path.home() / ".android_device_manager"
        log_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = log_dir / f"operation_{timestamp}.log"
        
        # Write initial log entry
        with open(self.log_file, 'w') as f:
            f.write(f"Android Device Manager Log - {timestamp}\n")
            f.write(f"Version: {VERSION}\n")
            f.write("=" * 80 + "\n")
    
    def log_operation(self, operation: str, status: str, details: str = ""):
        """Log an operation"""
        if self.log_file:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.log_file, 'a') as f:
                f.write(f"[{timestamp}] {operation}: {status}\n")
                if details:
                    f.write(f"  Details: {details}\n")
    
    def check_prerequisites(self) -> bool:
        """Check if all required tools are available"""
        required_binaries = ['adb', 'fastboot']
        missing = []
        
        for binary in required_binaries:
            if not check_binary_exists(binary):
                missing.append(binary)
        
        if missing:
            xox(f"{R}Missing required binaries: {', '.join(missing)}")
            xox(f"{Y}Please install Android SDK Platform Tools")
            xox(f"{C}Download from: https://developer.android.com/studio/releases/platform-tools")
            return False
        
        return True
    
    def detect_device(self) -> bool:
        """Detect connected Android device"""
        try:
            # First try fastboot
            result = run_command(['fastboot', 'devices'])
            if result.stdout.strip():
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if '\tfastboot' in line:
                        serial = line.split('\t')[0]
                        self.device_info = DeviceInfo(
                            serial=serial,
                            state=DeviceState.FASTBOOT
                        )
                        self._populate_fastboot_info()
                        self.connected = True
                        return True
            
            # Try ADB
            result = run_command(['adb', 'devices'])
            if result.stdout.strip():
                lines = result.stdout.strip().split('\n')[1:]  # Skip header
                for line in lines:
                    if '\tdevice' in line:
                        serial = line.split('\t')[0]
                        self.device_info = DeviceInfo(
                            serial=serial,
                            state=DeviceState.ADB
                        )
                        self._populate_adb_info()
                        self.connected = True
                        return True
                        
        except Exception as e:
            self.log_operation("Device Detection", "FAILED", str(e))
        
        self.connected = False
        self.device_info = None
        return False
    
    def _populate_fastboot_info(self):
        """Populate device information from fastboot"""
        if not self.device_info:
            return
        
        try:
            # Get product info
            result = run_command(['fastboot', 'getvar', 'product'])
            if result.returncode == 0:
                self.device_info.product = result.stdout.strip().split(':')[-1].strip()
            
            # Get model info
            result = run_command(['fastboot', 'getvar', 'model'])
            if result.returncode == 0:
                self.device_info.model = result.stdout.strip().split(':')[-1].strip()
            
            # Get current slot
            result = run_command(['fastboot', 'getvar', 'current-slot'])
            if result.returncode == 0:
                slot = result.stdout.strip().split(':')[-1].strip()
                if slot in ['a', 'b']:
                    self.device_info.slot_current = SlotInfo(slot)
                    self.device_info.slot_suffix = f"_{slot}"
                    self.device_info.is_ab = True
            
            # Check for dynamic partitions
            result = run_command(['fastboot', 'getvar', 'partition-type:system'])
            if result.returncode == 0:
                if 'dynamic' in result.stdout.lower():
                    self.device_info.dynamic_partitions = True
            
            # Check if unlocked
            result = run_command(['fastboot', 'getvar', 'unlocked'])
            if result.returncode == 0:
                self.device_info.unlocked = 'yes' in result.stdout.lower()
                
        except Exception as e:
            self.log_operation("Fastboot Info", "ERROR", str(e))
    
    def _populate_adb_info(self):
        """Populate device information from ADB"""
        if not self.device_info:
            return
        
        try:
            # Get device properties
            props = [
                'ro.product.device',
                'ro.product.model',
                'ro.product.name',
                'ro.boot.slot_suffix',
                'ro.boot.dynamic_partitions',
                'ro.boot.verifiedbootstate'
            ]
            
            for prop in props:
                result = run_command(['adb', 'shell', f'getprop {prop}'])
                if result.returncode == 0 and result.stdout.strip():
                    value = result.stdout.strip()
                    
                    if 'slot_suffix' in prop and value:
                        self.device_info.slot_suffix = value
                        self.device_info.is_ab = True
                        self.device_info.slot_current = SlotInfo(value.strip('_'))
                    
                    if 'dynamic_partitions' in prop:
                        self.device_info.dynamic_partitions = value == 'true'
                    
                    if 'verifiedbootstate' in prop:
                        self.device_info.secure_boot = value != 'orange'
                    
                    if 'product.device' in prop:
                        self.device_info.device = value
                    
                    if 'product.model' in prop:
                        self.device_info.model = value
                    
                    if 'product.name' in prop:
                        self.device_info.product = value
                        
        except Exception as e:
            self.log_operation("ADB Info", "ERROR", str(e))
    
    def reboot_to(self, target: str) -> bool:
        """Reboot device to specific mode"""
        if not self.connected:
            return False
        
        try:
            if target == 'bootloader':
                if self.device_info.state == DeviceState.ADB:
                    run_command(['adb', 'reboot', 'bootloader'])
                elif self.device_info.state == DeviceState.FASTBOOT:
                    run_command(['fastboot', 'reboot-bootloader'])
            elif target == 'recovery':
                run_command(['adb', 'reboot', 'recovery'])
            elif target == 'fastbootd':
                run_command(['fastboot', 'reboot', 'fastboot'])
            elif target == 'system':
                run_command(['fastboot', 'reboot'])
            
            # Wait for reboot
            time.sleep(5)
            return self.detect_device()
            
        except Exception as e:
            self.log_operation(f"Reboot to {target}", "FAILED", str(e))
            return False
    
    def flash_partition(self, partition: str, image_path: str, 
                       slot: SlotInfo = SlotInfo.UNKNOWN, 
                       verify: bool = True) -> bool:
        """Flash an image to a partition"""
        if not self.connected or self.device_info.state != DeviceState.FASTBOOT:
            xox(f"{R}Device not in fastboot mode!")
            return False
        
        if not os.path.exists(image_path):
            xox(f"{R}Image file not found: {image_path}")
            return False
        
        try:
            # Prepare partition name
            part_name = partition
            if slot != SlotInfo.UNKNOWN and self.device_info.is_ab:
                part_name = f"{partition}_{slot.value}"
            elif self.device_info.dynamic_partitions and partition in ['system', 'vendor', 'product']:
                part_name = partition
            
            xox(f"{Y}Flashing {part_name} with {os.path.basename(image_path)}...")
            
            # Flash command
            cmd = ['fastboot', 'flash', part_name, image_path]
            result = run_command(cmd, timeout=120, capture_output=False, check=False)
            
            if result.returncode != 0:
                xox(f"{R}Flash failed!")
                return False
            
            if verify:
                xox(f"{C}Verifying flash...")
                # Simple verification - check if device still accessible
                time.sleep(2)
                if not self.detect_device():
                    xox(f"{R}Verification failed - device not detected!")
                    return False
            
            xox(f"{G}Successfully flashed {part_name}!")
            self.log_operation(f"Flash {part_name}", "SUCCESS", 
                             f"Image: {os.path.basename(image_path)}")
            return True
            
        except Exception as e:
            xox(f"{R}Error during flash: {str(e)}")
            self.log_operation(f"Flash {partition}", "FAILED", str(e))
            return False
    
    def flash_recovery(self, recovery_img: str) -> bool:
        """Flash custom recovery"""
        return self.flash_partition('recovery', recovery_img)
    
    def flash_system(self, system_img: str) -> bool:
        """Flash system image (GSI or stock)"""
        slot = self.device_info.slot_current if self.device_info.is_ab else SlotInfo.UNKNOWN
        return self.flash_partition('system', system_img, slot)
    
    def flash_boot(self, boot_img: str) -> bool:
        """Flash boot image"""
        slot = self.device_info.slot_current if self.device_info.is_ab else SlotInfo.UNKNOWN
        return self.flash_partition('boot', boot_img, slot)
    
    def flash_vendor(self, vendor_img: str) -> bool:
        """Flash vendor image"""
        slot = self.device_info.slot_current if self.device_info.is_ab else SlotInfo.UNKNOWN
        return self.flash_partition('vendor', vendor_img, slot)
    
    def erase_partition(self, partition: str) -> bool:
        """Erase a partition"""
        if not self.connected or self.device_info.state != DeviceState.FASTBOOT:
            return False
        
        try:
            xox(f"{Y}Erasing {partition}...")
            cmd = ['fastboot', 'erase', partition]
            result = run_command(cmd, timeout=30)
            
            if result.returncode == 0:
                xox(f"{G}Successfully erased {partition}!")
                return True
            else:
                xox(f"{R}Failed to erase {partition}")
                return False
                
        except Exception as e:
            xox(f"{R}Error erasing partition: {str(e)}")
            return False
    
    def format_partition(self, partition: str, fs_type: str = 'ext4') -> bool:
        """Format a partition"""
        if not self.connected or self.device_info.state != DeviceState.FASTBOOT:
            return False
        
        try:
            xox(f"{Y}Formatting {partition} as {fs_type}...")
            cmd = ['fastboot', 'format', f'--{fs_type}', partition]
            result = run_command(cmd, timeout=60)
            
            if result.returncode == 0:
                xox(f"{G}Successfully formatted {partition}!")
                return True
            else:
                xox(f"{R}Failed to format {partition}")
                return False
                
        except Exception as e:
            xox(f"{R}Error formatting partition: {str(e)}")
            return False
    
    def sideload_rom(self, rom_zip: str) -> bool:
        """Sideload a ROM zip file"""
        if not self.connected or self.device_info.state != DeviceState.ADB:
            # Try to reboot to recovery
            if not self.reboot_to('recovery'):
                return False
        
        try:
            # Check if device is in sideload mode
            result = run_command(['adb', 'devices'])
            if 'sideload' not in result.stdout:
                xox(f"{Y}Entering sideload mode...")
                run_command(['adb', 'sideload'])
                time.sleep(5)
            
            xox(f"{C}Sideloading ROM...")
            cmd = ['adb', 'sideload', rom_zip]
            
            # Use subprocess.Popen for real-time output
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Read output in real-time
            for line in iter(process.stdout.readline, ''):
                line = line.strip()
                if line:
                    if 'error' in line.lower():
                        xox(f"{R}{line}")
                    elif 'progress' in line.lower():
                        xox(f"{C}{line}")
                    else:
                        xox(f"{W}{line}")
            
            process.wait()
            
            if process.returncode == 0:
                xox(f"{G}ROM sideload successful!")
                return True
            else:
                xox(f"{R}Sideload failed!")
                return False
                
        except Exception as e:
            xox(f"{R}Error during sideload: {str(e)}")
            return False
    
    def unbrick_device(self) -> bool:
        """Advanced unbrick procedure"""
        xox(f"{M}Starting advanced unbrick procedure...")
        
        steps = [
            ("Checking device connection", self.detect_device),
            ("Rebooting to bootloader", lambda: self.reboot_to('bootloader')),
            ("Unlocking critical partitions", self._unlock_critical),
            ("Erasing corrupt partitions", self._erase_corrupt_partitions),
            ("Flashing stock images", self._flash_stock_images),
            ("Formatting userdata", lambda: self.format_partition('userdata')),
            ("Rebooting to system", lambda: self.reboot_to('system'))
        ]
        
        for step_name, step_func in steps:
            xox(f"{Y}Step: {step_name}...")
            if not step_func():
                xox(f"{R}Failed at: {step_name}")
                return False
            time.sleep(2)
        
        xox(f"{G}Unbrick procedure completed successfully!")
        return True
    
    def _unlock_critical(self) -> bool:
        """Unlock critical partitions"""
        try:
            result = run_command(['fastboot', 'flashing', 'unlock_critical'])
            return result.returncode == 0
        except:
            return False
    
    def _erase_corrupt_partitions(self) -> bool:
        """Erase potentially corrupt partitions"""
        partitions_to_erase = [
            'boot', 'recovery', 'system', 'vendor', 'cache', 'metadata'
        ]
        
        success = True
        for partition in partitions_to_erase:
            if not self.erase_partition(partition):
                success = False
        
        return success
    
    def _flash_stock_images(self) -> bool:
        """Flash stock images from download directory"""
        download_dir = Path("/storage/emulated/0/Download")
        images = {
            'boot': download_dir / "boot.img",
            'system': download_dir / "system.img",
            'vendor': download_dir / "vendor.img",
            'recovery': download_dir / "recovery.img"
        }
        
        success = True
        for partition, image_path in images.items():
            if image_path.exists():
                xox(f"{C}Flashing stock {partition}...")
                if not self.flash_partition(partition, str(image_path)):
                    success = False
                    xox(f"{Y}Warning: Could not flash {partition}")
        
        return success
    
    def backup_partitions(self, backup_dir: str) -> bool:
        """Backup device partitions"""
        if not self.connected or self.device_info.state != DeviceState.FASTBOOT:
            return False
        
        backup_path = Path(backup_dir)
        backup_path.mkdir(parents=True, exist_ok=True)
        
        # Common partitions to backup
        partitions = ['boot', 'recovery', 'dtbo', 'vbmeta', 'super']
        
        xox(f"{C}Starting partition backup...")
        
        for partition in partitions:
            try:
                xox(f"{Y}Backing up {partition}...")
                backup_file = backup_path / f"{partition}.img"
                
                # Dump partition
                cmd = ['fastboot', 'getvar', f'partition-size:{partition}']
                result = run_command(cmd)
                
                if result.returncode == 0:
                    # Extract size
                    size_line = result.stdout.strip()
                    if ':' in size_line:
                        size_hex = size_line.split(':')[-1].strip()
                        try:
                            size = int(size_hex, 16)
                            xox(f"{C}Partition size: {format_size(size)}")
                            
                            # Dump partition
                            cmd = ['fastboot', 'fetch', partition, str(backup_file)]
                            result = run_command(cmd, timeout=300)
                            
                            if result.returncode == 0:
                                xox(f"{G}Backed up {partition}")
                            else:
                                xox(f"{R}Failed to backup {partition}")
                                
                        except ValueError:
                            xox(f"{Y}Could not parse size for {partition}")
                
            except Exception as e:
                xox(f"{R}Error backing up {partition}: {str(e)}")
                continue
        
        xox(f"{G}Backup completed!")
        return True
    
    def get_device_status(self) -> Dict[str, Any]:
        """Get comprehensive device status"""
        status = {
            'connected': self.connected,
            'state': None,
            'info': None,
            'partitions': [],
            'health': 'unknown'
        }
        
        if self.device_info:
            status['state'] = self.device_info.state.value
            status['info'] = {
                'serial': self.device_info.serial,
                'model': self.device_info.model,
                'product': self.device_info.product,
                'slot': self.device_info.slot_current.value,
                'is_ab': self.device_info.is_ab,
                'dynamic_partitions': self.device_info.dynamic_partitions,
                'unlocked': self.device_info.unlocked
            }
        
        return status

# ================= BANNER & UI FUNCTIONS =================
def print_banner():
    """Print the main banner"""
    clear_screen()
    
    # ASCII Art with colors
    banner_text = f"""
    {Colors.BG_BRIGHT_BLACK}{Colors.BRIGHT_WHITE}
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║   ███████╗██╗  ██╗██████╗  █████╗ ██████╗  ██████╗ ███╗   ██╗║
    ║   ██╔════╝██║  ██║██╔══██╗██╔══██╗██╔══██╗██╔═══██╗████╗  ██║║
    ║   ███████╗███████║██████╔╝███████║██████╔╝██║   ██║██╔██╗ ██║║
    ║   ╚════██║██╔══██║██╔══██╗██╔══██║██╔══██╗██║   ██║██║╚██╗██║║
    ║   ███████║██║  ██║██║  ██║██║  ██║██║  ██║╚██████╔╝██║ ╚████║║
    ║   ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝║
    ║                                                              ║
    ║         {Colors.BRIGHT_CYAN}★ S H R A B O N   G O M E Z   P R O ★{Colors.BRIGHT_WHITE}         ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    {Colors.RESET}
    """
    
    xox(banner_text, 0.0005)
    
    # Information box
    info_box = f"""
    {Colors.BRIGHT_BLUE}╔══════════════════════════════════════════════════════════════╗
    ║{Colors.BRIGHT_CYAN}    Author   : {Colors.BRIGHT_MAGENTA}{AUTHOR:<45}{Colors.BRIGHT_BLUE}║
    ║{Colors.BRIGHT_CYAN}    Github   : {Colors.BRIGHT_GREEN}{GITHUB:<45}{Colors.BRIGHT_BLUE}║
    ║{Colors.BRIGHT_CYAN}    Telegram : {Colors.BRIGHT_GREEN}{TELEGRAM:<45}{Colors.BRIGHT_BLUE}║
    ║{Colors.BRIGHT_CYAN}    Version  : {Colors.BRIGHT_GREEN}{VERSION:<45}{Colors.BRIGHT_BLUE}║
    ║{Colors.BRIGHT_CYAN}    Status   : {Colors.BRIGHT_YELLOW}Professional Edition{Colors.BRIGHT_BLUE:>28}║
    ╚══════════════════════════════════════════════════════════════╝{Colors.RESET}
    """
    
    xox(info_box, 0.001)
    print()

def print_menu():
    """Print the main menu"""
    menu_items = [
        f"{Colors.BRIGHT_CYAN}[1] {Colors.BRIGHT_GREEN}Device Connect & Status",
        f"{Colors.BRIGHT_CYAN}[2] {Colors.BRIGHT_GREEN}Brick Device Unbrick (Advanced)",
        f"{Colors.BRIGHT_CYAN}[3] {Colors.BRIGHT_GREEN}Custom Recovery Flash",
        f"{Colors.BRIGHT_CYAN}[4] {Colors.BRIGHT_GREEN}GSI ROM Flash",
        f"{Colors.BRIGHT_CYAN}[5] {Colors.BRIGHT_GREEN}Custom ROM Flash",
        f"{Colors.BRIGHT_CYAN}[6] {Colors.BRIGHT_GREEN}Backup Partitions",
        f"{Colors.BRIGHT_CYAN}[7] {Colors.BRIGHT_GREEN}Flash Individual Partition",
        f"{Colors.BRIGHT_CYAN}[8] {Colors.BRIGHT_GREEN}Wipe/Format Partitions",
        f"{Colors.BRIGHT_CYAN}[9] {Colors.BRIGHT_GREEN}Reboot Options",
        f"{Colors.BRIGHT_CYAN}[0] {Colors.BRIGHT_RED}Exit Program"
    ]
    
    menu_box_top = f"{Colors.BRIGHT_BLUE}╔══════════════════════════════════════════════════════════════╗"
    menu_box_bottom = f"{Colors.BRIGHT_BLUE}╚══════════════════════════════════════════════════════════════╝{Colors.RESET}"
    
    xox(menu_box_top)
    for item in menu_items:
        xox(f"{Colors.BRIGHT_BLUE}║  {item:<56} {Colors.BRIGHT_BLUE}║")
    xox(menu_box_bottom)
    print()

def password_check():
    """Check password before access"""
    print_banner()
    
    xox(f"{Colors.BRIGHT_YELLOW}[1] Developer Facebook ID for password")
    xox(f"{Colors.BRIGHT_YELLOW}[2] Enter password\n")
    xox(f"{Colors.BRIGHT_CYAN}Facebook Link: {Colors.BRIGHT_GREEN}{FACEBOOK}\n")
    
    attempts = 3
    while attempts > 0:
        pw = input(f"{Colors.BRIGHT_GREEN}Enter Password: {Colors.BRIGHT_WHITE}")
        
        if pw == PASSWORD:
            xox(f"\n{Colors.BRIGHT_GREEN}Access Granted! Loading professional tools...")
            time.sleep(1)
            return True
        else:
            attempts -= 1
            if attempts > 0:
                xox(f"{Colors.BRIGHT_RED}Wrong Password! {attempts} attempts remaining.\n")
            else:
                xox(f"{Colors.BRIGHT_RED}Access Denied! Maximum attempts reached.")
                sys.exit(1)
    
    return False

# ================= MAIN APPLICATION =================
def main():
    """Main application entry point"""
    
    # Check password first
    if not password_check():
        return
    
    # Initialize device manager
    manager = AndroidDeviceManager()
    
    # Check prerequisites
    xox(f"{Colors.BRIGHT_CYAN}Checking system requirements...")
    if not manager.check_prerequisites():
        xox(f"{Colors.BRIGHT_RED}Please install required tools and try again.")
        sys.exit(1)
    
    xox(f"{Colors.BRIGHT_GREEN}System check passed!\n")
    time.sleep(1)
    
    # Main application loop
    while True:
        print_banner()
        print_menu()
        
        # Check device connection
        if manager.detect_device():
            status = manager.get_device_status()
            xox(f"{Colors.BRIGHT_GREEN}Device Connected: {status['info']['model'] if status['info'] else 'Unknown'}")
            xox(f"{Colors.BRIGHT_YELLOW}State: {status['state'].upper() if status['state'] else 'Disconnected'}")
            xox(f"{Colors.BRIGHT_CYAN}Slot: {status['info']['slot'].upper() if status['info'] and status['info']['slot'] else 'N/A'}")
        else:
            xox(f"{Colors.BRIGHT_RED}No device detected! Please connect device.")
        
        print(f"\n{Colors.BRIGHT_YELLOW}{'='*60}{Colors.RESET}")
        choice = input(f"\n{Colors.BRIGHT_GREEN}Select Option: {Colors.BRIGHT_WHITE}")
        
        if choice == "1":
            # Device Connect & Status
            print_banner()
            xox(f"{Colors.BRIGHT_CYAN}Scanning for devices...")
            if manager.detect_device():
                status = manager.get_device_status()
                xox(f"\n{Colors.BRIGHT_GREEN}Device Information:")
                xox(f"{Colors.BRIGHT_YELLOW}{'-'*40}")
                for key, value in status['info'].items():
                    xox(f"{Colors.BRIGHT_CYAN}{key:20}: {Colors.BRIGHT_WHITE}{value}")
            else:
                xox(f"{Colors.BRIGHT_RED}No device found!")
            
            input(f"\n{Colors.BRIGHT_YELLOW}Press Enter to continue...")
        
        elif choice == "2":
            # Brick Device Unbrick
            print_banner()
            xox(f"{Colors.BRIGHT_RED}WARNING: This is an advanced unbrick procedure!")
            xox(f"{Colors.BRIGHT_YELLOW}It may erase all data on your device!")
            
            confirm = input(f"\n{Colors.BRIGHT_RED}Type 'YES' to continue: {Colors.BRIGHT_WHITE}")
            if confirm == "YES":
                xox(f"\n{Colors.BRIGHT_MAGENTA}Starting unbrick procedure...")
                if manager.unbrick_device():
                    xox(f"{Colors.BRIGHT_GREEN}Unbrick successful!")
                else:
                    xox(f"{Colors.BRIGHT_RED}Unbrick failed!")
            else:
                xox(f"{Colors.BRIGHT_YELLOW}Cancelled.")
            
            input(f"\n{Colors.BRIGHT_YELLOW}Press Enter to continue...")
        
        elif choice == "3":
            # Custom Recovery Flash
            print_banner()
            recovery_path = "/storage/emulated/0/Download/recovery.img"
            
            if os.path.exists(recovery_path):
                xox(f"{Colors.BRIGHT_GREEN}Found recovery image: {recovery_path}")
                
                if manager.detect_device() and manager.device_info.state == DeviceState.FASTBOOT:
                    if manager.flash_recovery(recovery_path):
                        xox(f"{Colors.BRIGHT_GREEN}Recovery flashed successfully!")
                    else:
                        xox(f"{Colors.BRIGHT_RED}Failed to flash recovery!")
                else:
                    xox(f"{Colors.BRIGHT_YELLOW}Please reboot device to bootloader first!")
            else:
                xox(f"{Colors.BRIGHT_RED}recovery.img not found in Download folder!")
            
            input(f"\n{Colors.BRIGHT_YELLOW}Press Enter to continue...")
        
        elif choice == "4":
            # GSI ROM Flash
            print_banner()
            system_path = "/storage/emulated/0/Download/system.img"
            
            if os.path.exists(system_path):
                xox(f"{Colors.BRIGHT_GREEN}Found system image: {system_path}")
                
                if manager.detect_device() and manager.device_info.state == DeviceState.FASTBOOT:
                    # Check for dynamic partitions
                    if manager.device_info.dynamic_partitions:
                        xox(f"{Colors.BRIGHT_CYAN}Device uses dynamic partitions.")
                        xox(f"{Colors.BRIGHT_YELLOW}Resizing system partition...")
                        
                        # Resize system_a
                        run_command(['fastboot', 'resize-logical-partition', 'system_a', '0'])
                        
                        # Delete system_a
                        run_command(['fastboot', 'delete-logical-partition', 'system_a'])
                        
                        # Create new system_a
                        run_command(['fastboot', 'create-logical-partition', 'system_a', str(os.path.getsize(system_path))])
                    
                    if manager.flash_system(system_path):
                        xox(f"{Colors.BRIGHT_GREEN}GSI ROM flashed successfully!")
                        
                        # Flash custom vbmeta if exists
                        vbmeta_path = "/storage/emulated/0/Download/vbmeta.img"
                        if os.path.exists(vbmeta_path):
                            xox(f"{Colors.BRIGHT_CYAN}Flashing custom vbmeta...")
                            manager.flash_partition('vbmeta', vbmeta_path)
                            run_command(['fastboot', '--disable-verity', '--disable-verification', 'flash', 'vbmeta', vbmeta_path])
                    else:
                        xox(f"{Colors.BRIGHT_RED}Failed to flash GSI!")
                else:
                    xox(f"{Colors.BRIGHT_YELLOW}Please reboot device to bootloader first!")
            else:
                xox(f"{Colors.BRIGHT_RED}system.img not found in Download folder!")
            
            input(f"\n{Colors.BRIGHT_YELLOW}Press Enter to continue...")
        
        elif choice == "5":
            # Custom ROM Flash
            print_banner()
            rom_path = "/storage/emulated/0/Download/rom.zip"
            
            if os.path.exists(rom_path):
                xox(f"{Colors.BRIGHT_GREEN}Found ROM: {rom_path}")
                xox(f"{Colors.BRIGHT_CYAN}Size: {format_size(os.path.getsize(rom_path))}")
                
                if manager.detect_device():
                    xox(f"{Colors.BRIGHT_YELLOW}Rebooting to recovery...")
                    if manager.reboot_to('recovery'):
                        time.sleep(5)
                        if manager.sideload_rom(rom_path):
                            xox(f"{Colors.BRIGHT_GREEN}Custom ROM flashed successfully!")
                        else:
                            xox(f"{Colors.BRIGHT_RED}Failed to flash ROM!")
                    else:
                        xox(f"{Colors.BRIGHT_RED}Failed to reboot to recovery!")
                else:
                    xox(f"{Colors.BRIGHT_YELLOW}Please connect device first!")
            else:
                xox(f"{Colors.BRIGHT_RED}rom.zip not found in Download folder!")
            
            input(f"\n{Colors.BRIGHT_YELLOW}Press Enter to continue...")
        
        elif choice == "6":
            # Backup Partitions
            print_banner()
            backup_dir = "/storage/emulated/0/Download/backup_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            
            xox(f"{Colors.BRIGHT_CYAN}Backup will be saved to: {backup_dir}")
            
            confirm = input(f"\n{Colors.BRIGHT_YELLOW}Proceed with backup? (y/n): {Colors.BRIGHT_WHITE}")
            if confirm.lower() == 'y':
                if manager.detect_device() and manager.device_info.state == DeviceState.FASTBOOT:
                    if manager.backup_partitions(backup_dir):
                        xox(f"{Colors.BRIGHT_GREEN}Backup completed successfully!")
                    else:
                        xox(f"{Colors.BRIGHT_RED}Backup failed!")
                else:
                    xox(f"{Colors.BRIGHT_YELLOW}Please reboot device to bootloader first!")
            
            input(f"\n{Colors.BRIGHT_YELLOW}Press Enter to continue...")
        
        elif choice == "7":
            # Flash Individual Partition
            print_banner()
            xox(f"{Colors.BRIGHT_CYAN}Available partitions to flash:")
            
            partitions = ['boot', 'recovery', 'system', 'vendor', 'dtbo', 'vbmeta']
            for i, part in enumerate(partitions, 1):
                xox(f"{Colors.BRIGHT_YELLOW}[{i}] {part}")
            
            part_choice = input(f"\n{Colors.BRIGHT_GREEN}Select partition: {Colors.BRIGHT_WHITE}")
            
            try:
                idx = int(part_choice) - 1
                if 0 <= idx < len(partitions):
                    partition = partitions[idx]
                    image_path = f"/storage/emulated/0/Download/{partition}.img"
                    
                    if os.path.exists(image_path):
                        xox(f"{Colors.BRIGHT_GREEN}Found {partition}.img")
                        
                        if manager.detect_device() and manager.device_info.state == DeviceState.FASTBOOT:
                            if manager.flash_partition(partition, image_path):
                                xox(f"{Colors.BRIGHT_GREEN}{partition} flashed successfully!")
                            else:
                                xox(f"{Colors.BRIGHT_RED}Failed to flash {partition}!")
                        else:
                            xox(f"{Colors.BRIGHT_YELLOW}Please reboot device to bootloader first!")
                    else:
                        xox(f"{Colors.BRIGHT_RED}{partition}.img not found in Download folder!")
                else:
                    xox(f"{Colors.BRIGHT_RED}Invalid selection!")
            except ValueError:
                xox(f"{Colors.BRIGHT_RED}Invalid input!")
            
            input(f"\n{Colors.BRIGHT_YELLOW}Press Enter to continue...")
        
        elif choice == "8":
            # Wipe/Format Partitions
            print_banner()
            xox(f"{Colors.BRIGHT_RED}WARNING: This will erase data!")
            
            wipe_options = [
                "Wipe cache",
                "Wipe dalvik/art cache",
                "Format data (factory reset)",
                "Wipe system",
                "Wipe vendor"
            ]
            
            for i, option in enumerate(wipe_options, 1):
                xox(f"{Colors.BRIGHT_YELLOW}[{i}] {option}")
            
            wipe_choice = input(f"\n{Colors.BRIGHT_RED}Select option: {Colors.BRIGHT_WHITE}")
            
            if wipe_choice in ['1', '2', '3', '4', '5']:
                confirm = input(f"{Colors.BRIGHT_RED}Confirm erase? (y/n): {Colors.BRIGHT_WHITE}")
                
                if confirm.lower() == 'y':
                    if manager.detect_device():
                        if manager.device_info.state == DeviceState.FASTBOOT:
                            if wipe_choice == '1':
                                manager.erase_partition('cache')
                            elif wipe_choice == '2':
                                # Requires recovery mode
                                xox(f"{Colors.BRIGHT_YELLOW}This requires recovery mode!")
                            elif wipe_choice == '3':
                                manager.format_partition('userdata')
                            elif wipe_choice == '4':
                                manager.erase_partition('system')
                            elif wipe_choice == '5':
                                manager.erase_partition('vendor')
                        else:
                            xox(f"{Colors.BRIGHT_YELLOW}Please reboot device to bootloader first!")
                    else:
                        xox(f"{Colors.BRIGHT_RED}No device detected!")
            
            input(f"\n{Colors.BRIGHT_YELLOW}Press Enter to continue...")
        
        elif choice == "9":
            # Reboot Options
            print_banner()
            reboot_options = [
                "Reboot to system",
                "Reboot to bootloader",
                "Reboot to recovery",
                "Reboot to fastbootd",
                "Reboot to edl (if supported)"
            ]
            
            for i, option in enumerate(reboot_options, 1):
                xox(f"{Colors.BRIGHT_YELLOW}[{i}] {option}")
            
            reboot_choice = input(f"\n{Colors.BRIGHT_GREEN}Select option: {Colors.BRIGHT_WHITE}")
            
            if reboot_choice == '1':
                if manager.detect_device():
                    manager.reboot_to('system')
                else:
                    xox(f"{Colors.BRIGHT_RED}No device detected!")
            elif reboot_choice == '2':
                if manager.detect_device():
                    manager.reboot_to('bootloader')
                else:
                    xox(f"{Colors.BRIGHT_RED}No device detected!")
            elif reboot_choice == '3':
                if manager.detect_device():
                    manager.reboot_to('recovery')
                else:
                    xox(f"{Colors.BRIGHT_RED}No device detected!")
            elif reboot_choice == '4':
                if manager.detect_device():
                    manager.reboot_to('fastbootd')
                else:
                    xox(f"{Colors.BRIGHT_RED}No device detected!")
            
            input(f"\n{Colors.BRIGHT_YELLOW}Press Enter to continue...")
        
        elif choice == "0":
            # Exit
            print_banner()
            xox(f"{Colors.BRIGHT_GREEN}Thank you for using Android Device Manager Pro!")
            xox(f"{Colors.BRIGHT_CYAN}Goodbye!")
            time.sleep(1)
            clear_screen()
            break
        
        else:
            xox(f"{Colors.BRIGHT_RED}Invalid option! Please try again.")
            time.sleep(1)

# ================= ENTRY POINT =================
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        xox(f"\n{Colors.BRIGHT_YELLOW}Program interrupted by user.")
        clear_screen()
        sys.exit(0)
    except Exception as e:
        xox(f"\n{Colors.BRIGHT_RED}Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        input(f"\n{Colors.BRIGHT_YELLOW}Press Enter to exit...")
        sys.exit(1)