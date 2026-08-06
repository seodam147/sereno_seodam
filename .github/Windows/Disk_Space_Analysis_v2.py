#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=====================================================================
 Disk Inspector Tool - Windows Performance/Stability Enhanced Edition
=====================================================================
 - Disk capacity/usage bar chart representation
 - Parallel processing via ThreadPoolExecutor for folder scans & duplicate file hashing
 - Stack-based non-recursive directory traversal to prevent recursion depth limit errors
 - Temporary & junk file scanner/cleaner (classified by cache/temp attributes)
 - Duplicate file detection (displays file roles and duplicate groups/attributes)
 - Windows PowerShell-based S.M.A.R.T. disk health check
 - RotatingFileHandler for 'Disk_Check.log' log size management and error logging
 - Horizontal/vertical scrolling for all lists with right-click context menu support
=====================================================================
"""

import os
import time
import sys
import ctypes
import threading
import subprocess
import platform
import hashlib
import queue
import shutil
import string
import json
import logging
import webbrowser
from urllib.parse import quote_plus
from logging.handlers import RotatingFileHandler
from concurrent.futures import ThreadPoolExecutor, as_completed
from send2trash import send2trash
from datetime import datetime
from collections import defaultdict

import tkinter as tk
from tkinter import ttk, messagebox
import tkinter.font as tkfont

try:
    import psutil
except ImportError:
    psutil = None

try:
    from pySMART import DeviceList
except ImportError:
    DeviceList = None

# Logging configuration (max 5MB, retain up to 3 backup files to manage log disk space)
# Log file is generated relative to the executable path to avoid CWD dependencies
_LOG_DIR = os.path.dirname(os.path.abspath(sys.argv[0] if getattr(sys, "frozen", False) else __file__))
_LOG_PATH = os.path.join(_LOG_DIR, "Disk_Check.log")
log_handler = RotatingFileHandler(
    _LOG_PATH,
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
    encoding="utf-8"
)
logging.basicConfig(
    handlers=[log_handler],
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

IS_WINDOWS = platform.system() == "Windows"

APP_TITLE = "Disk Inspector Tool"
WARN_THRESHOLD = 80.0                       # Disk usage warning threshold (%)
CONFIG_FILE = os.path.join(_LOG_DIR, "junk_paths.json")
ANOMALY_THRESHOLD_BYTES = 500 * 1024 * 1024      # 500MB - Threshold for abnormal size in system/program areas
JUNK_SCAN_MIN_AGE_SEC = 3 * 24 * 3600         # Prioritize temp files older than 3 days

# Keywords to search but skip displaying in the main "Folder Size" scan list (System/Installed programs/Games/Utilities)
SKIP_DISPLAY_KEYWORDS = [
    "windows", "program files", "program files (x86)", "programdata",
    "$recycle.bin", "system volume information", "steam", "steamapps",
    "epic games", "riot games", "battle.net", "origin games", "ea games",
    "gog galaxy", "windowsapps", "msocache", "microsoft", "nvidia",
    "amd", "intel", "common files", "installer",
]

# Items to exclude from user profiles list
SKIP_USER_PROFILES = {"default", "default user", "public", "all users", ".NET", "defaultappPool"}


def _get_file_role(filename):
    """Classifies the role/function of a file based on its extension."""
    ext = os.path.splitext(filename)[1].lower()
    role_map = {
        '.png': 'Image File', '.jpg': 'Image File', '.jpeg': 'Image File', '.gif': 'Image File', '.bmp': 'Image File', '.webp': 'Image File', '.ico': 'Image File',
        '.mp4': 'Video File', '.mkv': 'Video File', '.avi': 'Video File', '.mov': 'Video File', '.wmv': 'Video File',
        '.mp3': 'Audio File', '.wav': 'Audio File', '.flac': 'Audio File', '.aac': 'Audio File', '.m4a': 'Audio File',
        '.pdf': 'Document File', '.hwp': 'Document File', '.doc': 'Document File', '.docx': 'Document File', '.xls': 'Document File', '.xlsx': 'Document File', '.ppt': 'Document File', '.pptx': 'Document File', '.txt': 'Document File', '.csv': 'Document File',
        '.zip': 'Archive File', '.rar': 'Archive File', '.7z': 'Archive File', '.tar': 'Archive File', '.gz': 'Archive File',
        '.py': 'Source Code', '.js': 'Source Code', '.html': 'Source Code', '.css': 'Source Code', '.cpp': 'Source Code', '.c': 'Source Code', '.java': 'Source Code', '.json': 'Config File', '.xml': 'Config File',
        '.exe': 'Executable File', '.msi': 'Installer File', '.iso': 'Disk Image'
    }
    return role_map.get(ext, 'General Data File')


def load_custom_junk_paths():
    """Loads custom junk paths from the JSON configuration file."""
    if not os.path.exists(CONFIG_FILE):
        return []
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return [(item["path"], item["desc"]) for item in data.get("custom_paths", [])]
    except Exception as e:
        logging.error(f"Failed to load configuration file: {e}")
        return []                       


def load_custom_backup_paths():
    """Loads custom paths from JSON to treat as 'Device Backup' categories."""
    if not os.path.exists(CONFIG_FILE):
        return []
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return [(item["path"], item["desc"]) for item in data.get("custom_backup_paths", [])]
    except Exception as e:
        logging.error(f"Failed to load config file (backup paths): {e}")
        return []


def assess_delete_target(path):
    """Validates the deletion target path and checks for system protection constraints."""
    norm_lower = os.path.normpath(path).lower().rstrip("\\/")
    basename_lower = os.path.basename(norm_lower)
    
    if is_protected_path(path):
        return {"blocked": True, "type": "System", "reason": "Protected critical system path."}
    
    if os.path.isdir(path):
        item_type = "Folder"
    elif os.path.isfile(path):
        item_type = "File"
    else:
        item_type = "Unknown (Inaccessible)"

    drive, tail = os.path.splitdrive(norm_lower)
    if drive and tail in ("", "\\"):
        return {"type": item_type, "blocked": True, "reason": "Drive root directory cannot be deleted."}

    systemroot = os.environ.get("SystemRoot", r"C:\Windows").lower()
    programfiles = os.environ.get("ProgramFiles", r"C:\Program Files").lower()
    programfiles_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)").lower()
    programdata = os.environ.get("ProgramData", r"C:\ProgramData").lower()
    systemdrive = os.environ.get("SystemDrive", "C:").lower()
    users_root = systemdrive + r"\users"

    critical_paths = {systemroot, programfiles, programfiles_x86, programdata, users_root}
    if norm_lower in critical_paths:
        return {"type": item_type, "blocked": True, "reason": "Essential system folder cannot be deleted."}

    protected_names = {
        "pagefile.sys", "hiberfil.sys", "swapfile.sys",
        "bootmgr", "ntldr", "bootnxt", "$recycle.bin", "system volume information",
    }
    if basename_lower in protected_names:
        return {"type": item_type, "blocked": True, "reason": "Protected system file/folder cannot be deleted."}

    return {"type": item_type, "blocked": False, "reason": None}


def get_junk_locations():
    locations = []
    if IS_WINDOWS:
        localapp = os.environ.get("LOCALAPPDATA", "")
        systemroot = os.environ.get("SystemRoot", r"C:\Windows")
        systemdrive = os.environ.get("SystemDrive", "C:")
        candidates = [
            (os.environ.get("TEMP", ""), "User Temp Files (TEMP)"),
            (os.environ.get("TMP", ""), "User Temp Files (TMP)"),
            (os.path.join(systemroot, "Temp"), "System Temp Files"),
            (os.path.join(systemroot, "Prefetch"), "Prefetch Cache"),
            (os.path.join(systemroot, "SoftwareDistribution", "Download"), "Windows Update Download Cache"),
            (os.path.join(localapp, "Temp"), "User Local Temp Files"),
            (os.path.join(localapp, "Microsoft", "Windows", "Explorer"), "Explorer Thumbnail Cache"),
            (os.path.join(localapp, "Microsoft", "Windows", "WPDNSE"), "External Device (MTP) Transfer Temp Files"),
            (os.path.join(localapp, "Google", "Chrome", "User Data", "Default", "Cache"), "Chrome Browser Cache"),
            (os.path.join(localapp, "Microsoft", "Edge", "User Data", "Default", "Cache"), "Edge Browser Cache"),
            (os.path.join(localapp, "Mozilla", "Firefox", "Profiles"), "Firefox Browser Cache (Profiles)"),
            (os.path.join(localapp, "npm-cache"), "npm Package Cache"),
            (os.path.join(localapp, "pip", "Cache"), "pip Package Cache"),
            (systemdrive + r"\Windows.old", "Previous Windows Installation Backup (Windows.old)"),
        ]
        for path, desc in candidates:
            if path:
                locations.append((path, desc))
    else:
        import tempfile
        locations.append((tempfile.gettempdir(), "Temp Files (TEMP)"))
    
    custom_paths = load_custom_junk_paths()
    locations.extend(custom_paths)
    return locations


def is_safe_to_delete(path):
    """Determines whether a path is safe to mark for cleanup.
    Core system directories (System32, WinSxS, etc.) are strictly blocked."""
    path_lower = path.lower()

    HARD_BLOCK_KEYWORDS = [
        "system32", "syswow64", "winsxs", "\\drivers\\", "\\boot\\",
        "\\assembly\\", "\\catroot", "\\servicing\\", "\\wbem\\",
    ]
    if any(key in path_lower for key in HARD_BLOCK_KEYWORDS):
        return False

    SAFE_KEYWORDS = ["cache", "temp", "tmp", "logs", "download", "thumbnails", "prefetch", "crashdump"]
    if any(key in path_lower for key in SAFE_KEYWORDS):
        return True

    CRITICAL_KEYWORDS = ["windows", "system32", "program files", "drivers", "users"]
    if any(key in path_lower for key in CRITICAL_KEYWORDS):
        return False
    return False


def _io_worker_count():
    """Optimal thread count for I/O bound tasks like directory scanning/hashing."""
    cpu = os.cpu_count() or 4
    return max(4, min(16, cpu * 2))


def human_gb(num_bytes):
    try:
        return f"{num_bytes / (1024 ** 3):.2f}"
    except Exception:
        return "0.00"


def is_admin():
    if not IS_WINDOWS:
        try:
            return os.geteuid() == 0
        except Exception:
            return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin():
    """Attempts to relaunch the application with administrator privileges."""
    try:
        params = " ".join([f'"{a}"' for a in sys.argv])
        if IS_WINDOWS:
            ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
            if int(ret) <= 32:
                logging.warning(f"Relaunch as admin failed or was canceled (Code {ret})")
                return False
            return True
        else:
            os.execvp('sudo', ['sudo', sys.executable] + sys.argv)
            return True
    except Exception as e:
        logging.error(f"Failed to relaunch as admin: {e}")
        messagebox.showerror("Error", f"Failed to restart with administrator privileges.\n{e}")
        return False


def open_in_explorer(path):
    try:
        if not path:
            return
        if IS_WINDOWS:
            if os.path.isdir(path):
                os.startfile(path)
            elif os.path.exists(path):
                subprocess.run(["explorer", "/select,", path])
            else:
                parent = os.path.dirname(path)
                if os.path.isdir(parent):
                    os.startfile(parent)
        else:
            opener = "open" if platform.system() == "Darwin" else "xdg-open"
            target = path if os.path.isdir(path) else os.path.dirname(path)
            subprocess.run([opener, target])
    except Exception as e:
        logging.error(f"Failed to open location ({path}): {e}")
        messagebox.showwarning("Open Failed", f"Cannot open location:\n{path}\n\n{e}")


def list_disks():
    result = []
    if psutil is None:
        return result
    try:
        partitions = psutil.disk_partitions(all=False)
    except Exception as e:
        logging.error(f"Failed to fetch disk partitions: {e}")
        partitions = []
    for p in partitions:
        opts = (p.opts or "").lower()
        if "cdrom" in opts or p.fstype == "":
            continue
        try:
            usage = psutil.disk_usage(p.mountpoint)
        except Exception as e:
            logging.error(f"Failed to fetch disk usage ({p.mountpoint}): {e}")
            continue
        percent = usage.percent
        result.append({
            "device": p.device,
            "mountpoint": p.mountpoint,
            "fstype": p.fstype,
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
            "percent": percent,
            "warn": percent >= WARN_THRESHOLD,
        })
    return result


def _is_skip_display(folder_name):
    lower = folder_name.lower()
    return any(k in lower for k in SKIP_DISPLAY_KEYWORDS)


def _win_long_path(path):
    """Prepends extended path prefix (\\\\?\\) on Windows to bypass the 260 character limit."""
    if not IS_WINDOWS or path.startswith("\\\\?\\"):
        return path
    try:
        abspath = os.path.abspath(path)
    except Exception:
        return path
    if abspath.startswith("\\\\"):
        return "\\\\?\\UNC\\" + abspath.lstrip("\\")
    return "\\\\?\\" + abspath


def _safe_scandir_entries(path):
    """Safely retrieves directory entries, retrying with extended length path if needed."""
    try:
        return list(os.scandir(path))
    except (PermissionError, FileNotFoundError, OSError) as e:
        if IS_WINDOWS:
            long_path = _win_long_path(path)
            if long_path != path:
                try:
                    return list(os.scandir(long_path))
                except (PermissionError, FileNotFoundError, OSError) as e2:
                    logging.warning(f"Failed long path access ({path}): {e2}")
                except Exception as e2:
                    logging.error(f"Exception during long path scan ({path}): {e2}")
        else:
            logging.warning(f"Failed directory access ({path}): {e}")
        return []
    except Exception as e:
        logging.error(f"Exception during directory scan ({path}): {e}")
        return []


def _dir_size(path, stop_event=None):
    """Stack-based non-recursive directory size calculation."""
    total_size = 0
    stack = [path]
    
    while stack:
        if stop_event and stop_event.is_set():
            return 0
        current_path = stack.pop()
        for entry in _safe_scandir_entries(current_path):
            if stop_event and stop_event.is_set():
                return 0
            try:
                if entry.is_file(follow_symlinks=False):
                    total_size += entry.stat().st_size
                elif entry.is_dir(follow_symlinks=False):
                    stack.append(entry.path)
            except (PermissionError, FileNotFoundError, OSError):
                continue
            
    return total_size


def is_protected_path(path):
    if not path:
        return True
    systemdrive = os.environ.get("SystemDrive", "C:")
    protected_roots = [
        os.environ.get("SystemRoot", r"C:\Windows"),
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        os.environ.get("ProgramData", r"C:\ProgramData"),
        systemdrive + r"\Recovery",
        systemdrive + r"\Config.Msi",
    ]
    try:
        target_real_path = os.path.realpath(path).lower()

        drive, tail = os.path.splitdrive(target_real_path)
        tail_norm = tail.strip("\\/")
        if tail_norm in ("$recycle.bin", "system volume information") or \
           tail_norm.startswith("$recycle.bin\\") or tail_norm.startswith("system volume information\\"):
            return True

        for root in protected_roots:
            if not root: 
                continue
            real_root = os.path.realpath(root).lower()
            if target_real_path == real_root or target_real_path.startswith(real_root + os.sep):
                return True
    except (OSError, TypeError):
        return True
    return False
    

# Cloud sync (OneDrive/Dropbox/Google Drive, etc.) "online-only" placeholder attributes
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400
_FILE_ATTRIBUTE_OFFLINE = 0x1000
_FILE_ATTRIBUTE_RECALL_ON_OPEN = 0x40000
_FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x400000
_CLOUD_PLACEHOLDER_MASK = (
    _FILE_ATTRIBUTE_REPARSE_POINT | _FILE_ATTRIBUTE_OFFLINE |
    _FILE_ATTRIBUTE_RECALL_ON_OPEN | _FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS
)


def _is_cloud_placeholder(path):
    """Checks whether a file is an 'online-only' placeholder to avoid triggering downloads."""
    if not IS_WINDOWS:
        return False
    try:
        attrs = os.stat(path).st_file_attributes
        return bool(attrs & _CLOUD_PLACEHOLDER_MASK)
    except (AttributeError, OSError):
        return False


def _is_critical_file(filename, filepath):
    fname_lower = filename.lower()
    critical_extensions = ('.sys', '.dll', '.ocx', '.drv', '.efi', '.cpl', '.msc', '.mun', '.mum', '.cat', '.cer', '.rom', '.ime')
    if fname_lower.endswith(critical_extensions):
        return True
    critical_names = {
        'bootmgr', 'bootnxt', 'ntldr', 'io.sys', 'msdos.sys',
        'hiberfil.sys', 'pagefile.sys', 'swapfile.sys', 'memory.dmp',
        'config.sys', 'autoexec.bat'
    }
    if fname_lower in critical_names:
        return True
    return False    


def _quick_hash(path, chunk_size=4096):
    if _is_cloud_placeholder(path):
        return None
    h = hashlib.md5()
    try:
        with open(path, "rb") as f:
            chunk = f.read(chunk_size)
            h.update(chunk)
        return h.hexdigest()
    except (OSError, PermissionError):
        return None
    except Exception as e:
        logging.error(f"Quick hash calculation error ({path}): {e}")
        return None


def scan_folder_sizes(root_paths, stop_event=None, progress_cb=None):
    results = []

    def process_entry(root, entry):
        if stop_event is not None and stop_event.is_set():
            return []
        local_results = []
        try:
            if not entry.is_dir(follow_symlinks=False):
                return local_results
            name = entry.name
            if progress_cb:
                progress_cb(f"Scanning: {entry.path}")
            if _is_skip_display(name):
                try:
                    with os.scandir(entry.path) as sub_it:
                        for sub_entry in sub_it:
                            if stop_event is not None and stop_event.is_set():
                                break
                            if not sub_entry.is_dir(follow_symlinks=False):
                                continue
                            size = _dir_size(sub_entry.path, stop_event)
                            if size >= ANOMALY_THRESHOLD_BYTES and is_safe_to_delete(sub_entry.path):
                                local_results.append({
                                    "location": root,
                                    "name": sub_entry.name,
                                    "size_bytes": size,
                                    "attr": "Large Cache",
                                    "desc": "Cleanable large cache / temporary file",
                                    "anomaly": True,
                                    "path": sub_entry.path,
                                })
                except (PermissionError, FileNotFoundError, OSError):
                    pass
            else:
                size = _dir_size(entry.path, stop_event)
                local_results.append({
                    "location": root,
                    "name": name,
                    "size_bytes": size,
                    "attr": "Normal Folder",
                    "desc": "Standard directory folder",
                    "anomaly": False,
                    "path": entry.path,
                })
        except (PermissionError, FileNotFoundError, OSError) as e:
            logging.warning(f"Folder access restricted or error ({entry.path}): {e}")
        except Exception as e:
            logging.error(f"Exception during folder processing ({entry.path}): {e}")
        return local_results

    with ThreadPoolExecutor(max_workers=_io_worker_count()) as executor:
        futures = []
        for root in root_paths:
            if stop_event is not None and stop_event.is_set():
                break
            try:
                entries = list(os.scandir(root))
            except (PermissionError, FileNotFoundError, OSError) as e:
                logging.error(f"Root directory scan failed ({root}): {e}")
                continue
            for entry in entries:
                futures.append(executor.submit(process_entry, root, entry))
        
        for future in as_completed(futures):
            if stop_event is not None and stop_event.is_set():
                break
            try:
                res_list = future.result()
                if res_list:
                    results.extend(res_list)
            except Exception as e:
                logging.error(f"Thread execution result error: {e}")
                continue

    return results


def scan_user_data(stop_event=None, progress_cb=None):
    results = []
    user_home = os.path.expanduser("~")
    appdata = os.environ.get("APPDATA", "")
    
    target_items = [
        (os.path.join(user_home, "Desktop"), "General Data"),
        (os.path.join(user_home, "Downloads"), "Downloads"),
        (os.path.join(appdata, "Apple Computer", "MobileSync", "Backup"), "Device Backup"),
        (os.path.join(user_home, "Documents", "Samsung", "Smart Switch", "Backup"), "Device Backup"),
        (os.path.join(user_home, "Documents", "LG Bridge", "Backup"), "Device Backup"),
        (os.path.join(user_home, ".android", "avd"), "Dev Tools"),
        (os.path.join(user_home, "OneDrive"), "Cloud Storage"),
        (os.path.join(user_home, "Dropbox"), "Cloud Storage"),
        (os.path.join(user_home, "Google Drive"), "Cloud Storage"),
        (os.path.join(appdata, "Discord", "Cache"), "Messenger Cache"),
        (os.path.join(user_home, "Documents", "KakaoTalk"), "Messenger Cache"),
        (os.path.join(user_home, "Pictures", "Screenshots"), "Screenshots/Captures"),
        (os.path.join(user_home, "Videos", "Captures"), "Screenshots/Captures"),
        (os.path.join(user_home, "Projects"), "Dev/Projects"),
        (os.path.join(user_home, "Source"), "Dev/Projects"),
    ]
    target_items.extend((path, "Device Backup") for path, _desc in load_custom_backup_paths())
    
    DAYS_THRESHOLD = 30
    MIN_SIZE = 100 * 1024 * 1024
    NEGLECTED_EXTENSIONS = {'.exe', '.msi', '.zip', '.rar', '.iso', '.dmg'}
    DEV_JUNK_NAMES = {"node_modules", "__pycache__", ".venv"}
    
    now = time.time()
    
    for path, category in target_items:
        if stop_event and stop_event.is_set():
            break
        if not os.path.exists(path): 
            continue
        if progress_cb: 
            progress_cb(f"Searching: {category} ({path})")
            
        try:
            with os.scandir(path) as it:
                for entry in it:
                    if stop_event and stop_event.is_set():
                        break  
                    try:
                        stat = entry.stat()
                        is_dev_junk = entry.is_dir(follow_symlinks=False) and entry.name in DEV_JUNK_NAMES
                        is_backup_dir = entry.is_dir(follow_symlinks=False) and category == "Device Backup"
                        is_avd_dir = entry.is_dir(follow_symlinks=False) and category == "Dev Tools"
                        
                        if entry.is_file(follow_symlinks=False):
                            file_age_days = (now - stat.st_mtime) / (24 * 3600)
                            file_ext = os.path.splitext(entry.name)[1].lower()
                            is_old = file_age_days >= DAYS_THRESHOLD and stat.st_size >= MIN_SIZE
                            is_installer = file_ext in NEGLECTED_EXTENSIONS and stat.st_size >= MIN_SIZE
                            
                            if is_old or is_installer:
                                results.append({
                                    "location": path,
                                    "name": entry.name,
                                    "size_bytes": stat.st_size,
                                    "attr": "Unused Large File",
                                    "desc": f"[{category}] Unused 30+ days / Large File",
                                    "path": entry.path
                                })
                        elif is_dev_junk:
                            folder_size = _dir_size(entry.path, stop_event)
                            if stop_event and stop_event.is_set():
                                break
                            results.append({
                                "location": path,
                                "name": entry.name,
                                "size_bytes": folder_size,
                                "attr": "Dev Build Artifact",
                                "desc": f"[{category}] Development build artifact",
                                "path": entry.path
                            })
                        elif is_backup_dir or is_avd_dir:
                            folder_size = _dir_size(entry.path, stop_event)
                            if stop_event and stop_event.is_set():
                                break
                            if folder_size >= MIN_SIZE:
                                attr_name = "Device Backup Data" if is_backup_dir else "Dev Tool Data"
                                desc_text = f"[{category}] Large backup / Virtual device folder"
                                results.append({
                                    "location": path,
                                    "name": entry.name,
                                    "size_bytes": folder_size,
                                    "attr": attr_name,
                                    "desc": desc_text,
                                    "path": entry.path
                                })
                    except OSError:
                        continue
        except OSError as e:
            logging.warning(f"User data path scan failed ({path}): {e}")
            continue
    return results


def scan_junk_files(stop_event=None, progress_cb=None, min_age_sec=JUNK_SCAN_MIN_AGE_SEC):
    """Scans temporary/cache locations for entries older than min_age_sec."""
    results = []
    seen_paths = set()
    now = time.time()

    def _dedupe(p):
        try:
            rp = os.path.realpath(p)
        except OSError:
            rp = p
        if rp in seen_paths:
            return False
        seen_paths.add(rp)
        return True

    for path, desc in get_junk_locations():
        if stop_event is not None and stop_event.is_set():
            break
        if not path or not os.path.exists(path):
            continue
        if progress_cb:
            progress_cb(f"Scanning temp files: {path}")

        try:
            if os.path.isdir(path):
                try:
                    children = list(os.scandir(path))
                except (PermissionError, FileNotFoundError, OSError) as e:
                    logging.warning(f"Temp folder scan restricted ({path}): {e}")
                    continue
                for child in children:
                    if stop_event is not None and stop_event.is_set():
                        break
                    if not _dedupe(child.path):
                        continue
                    try:
                        st = child.stat(follow_symlinks=False)
                        age_sec = now - st.st_mtime
                        if age_sec < min_age_sec:
                            continue
                        if child.is_dir(follow_symlinks=False):
                            size = _dir_size(child.path, stop_event)
                        else:
                            size = st.st_size
                        if size <= 0:
                            continue
                        results.append({
                            "location": path,
                            "name": child.name,
                            "size_bytes": size,
                            "attr": "System Temp Cache",
                            "desc": f"{desc} (Last modified {int(age_sec // 86400)} days ago)",
                            "path": child.path,
                        })
                    except (PermissionError, FileNotFoundError, OSError) as e:
                        logging.warning(f"Temp item scan error ({child.path}): {e}")
                        continue
            else:
                if not _dedupe(path):
                    continue
                st = os.stat(path)
                age_sec = now - st.st_mtime
                if age_sec < min_age_sec:
                    continue
                results.append({
                    "location": os.path.dirname(path),
                    "name": os.path.basename(path),
                    "size_bytes": st.st_size,
                    "attr": "File Temp Cache",
                    "desc": f"{desc} (Last modified {int(age_sec // 86400)} days ago)",
                    "path": path,
                })
        except (PermissionError, FileNotFoundError, OSError) as e:
            logging.warning(f"Temp file scan restricted ({path}): {e}")
            continue
    return results


def find_duplicate_files(root_paths, stop_event=None, progress_cb=None):
    size_map = {}
    seen_files = set()
    MIN_FILE_SIZE = 1 * 1024 * 1024

    for root in root_paths:
        if not os.path.exists(root):
            continue
        def _walk_onerror(e):
            logging.warning(f"Path access error during duplicate check (Skipped): {e}")

        for dirpath, dirnames, filenames in os.walk(root, onerror=_walk_onerror):
            if stop_event is not None and stop_event.is_set():
                return []
            if is_protected_path(dirpath):
                dirnames[:] = []
                continue
            base = os.path.basename(dirpath)
            if _is_skip_display(base):
                dirnames[:] = []
                continue
            if progress_cb:
                progress_cb(f"Duplicate Scan (Collecting files): {dirpath}")
                
            for fname in filenames:
                fpath = os.path.join(dirpath, fname)
                if is_protected_path(fpath):
                    continue
                if _is_critical_file(fname, fpath):
                    continue
                if _is_cloud_placeholder(fpath):
                    continue
                try:
                    real_path = os.path.realpath(fpath)
                    if real_path in seen_files:
                        continue
                    seen_files.add(real_path)
                except OSError:
                    continue
                try:
                    fsize = os.path.getsize(fpath)
                except OSError:
                    continue
                if fsize < MIN_FILE_SIZE:
                    continue
                size_map.setdefault(fsize, []).append(fpath)

    potential_paths = []
    for size, paths in size_map.items():
        if len(paths) >= 2:
            potential_paths.extend(paths)

    if not potential_paths:
        return []

    if progress_cb:
        progress_cb(f"Analyzing candidate files ({len(potential_paths)} total)...")

    if stop_event is not None and stop_event.is_set():
        return []

    partial_hash_map = defaultdict(list)
    with ThreadPoolExecutor(max_workers=_io_worker_count()) as executor:
        future_to_path = {executor.submit(_quick_hash, p): p for p in potential_paths}
        for future in as_completed(future_to_path):
            if stop_event is not None and stop_event.is_set():
                return []
            try:
                q_hash = future.result()
                if q_hash:
                    p = future_to_path[future]
                    partial_hash_map[q_hash].append(p)
            except Exception as e:
                logging.error(f"Duplicate file hashing error: {e}")
                continue

    results = []
    group_id = 0

    for q_hash, q_paths in partial_hash_map.items():
        if len(q_paths) < 2:
            continue
        if stop_event is not None and stop_event.is_set():
            break
            
        exact_hash_map = defaultdict(list)
        with ThreadPoolExecutor(max_workers=_io_worker_count()) as executor:
            future_to_path = {executor.submit(_hash_file, p): p for p in q_paths}
            for future in as_completed(future_to_path):
                if stop_event is not None and stop_event.is_set():
                    break
                try:
                    h = future.result()
                    if h:
                        p = future_to_path[future]
                        exact_hash_map[h].append(p)
                except Exception as e:
                    logging.error(f"Exact file hash calculation error: {e}")
            
        for h, group in exact_hash_map.items():
            if len(group) < 2:
                continue
            group_id += 1
            
            try:
                fsize = os.path.getsize(group[0])
            except OSError:
                fsize = 0

            for p in group:
                file_role = _get_file_role(os.path.basename(p))
                results.append({
                    "location": os.path.dirname(p),
                    "name": os.path.basename(p),
                    "size_bytes": fsize,
                    "attr": file_role,
                    "desc": f"Duplicate Group #{group_id}",
                    "path": p,
                    "group_id": group_id,
                })

    return results
    

def _hash_file(path, chunk_size=65536, partial_bytes=0):
    if _is_cloud_placeholder(path):
        return None
    h = hashlib.md5()
    try:
        with open(path, "rb") as f:
            if partial_bytes > 0:
                chunk = f.read(partial_bytes)
                h.update(chunk)
            else:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    h.update(chunk)
        return h.hexdigest()
    except (PermissionError, FileNotFoundError, OSError):
        return None
    except Exception as e:
        logging.error(f"Full file hash calculation error ({path}): {e}")
        return None


class ScrollableFrame(ttk.Frame):
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)

        self.inner.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas_window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw", width=260)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.inner.bind("<MouseWheel>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"

    def bind_mousewheel(self, widget):
        widget.bind("<MouseWheel>", self._on_mousewheel)
        for child in widget.winfo_children():
            self.bind_mousewheel(child)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<Enter>", self._bind_mousewheel)
        self.canvas.bind("<Leave>", self._unbind_mousewheel)

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _bind_mousewheel(self, _event):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Shift-MouseWheel>", self._on_shift_mousewheel)

    def _unbind_mousewheel(self, _event):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Shift-MouseWheel>")

    def _on_shift_mousewheel(self, event):
        self.canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")


class DiskBarChart(tk.Canvas):
    WIDTH = 260
    HEIGHT = 19

    def __init__(self, parent, disk_info, width=None, **kwargs):
        self.WIDTH = width if width else DiskBarChart.WIDTH
        super().__init__(parent, width=self.WIDTH, height=self.HEIGHT, highlightthickness=1, highlightbackground="#c8ccd2", **kwargs)
        self.draw(disk_info)

    def draw(self, disk_info):
        self.delete("all")
        percent = disk_info["percent"]
        warn = disk_info["warn"]
        fill_width = max(2, int(self.WIDTH * min(percent, 100.0) / 100.0))

        self.create_rectangle(0, 0, self.WIDTH, self.HEIGHT, fill="#e4e6ea", outline="")

        if warn:
            color = "#e5484d"
        elif percent >= 80:
            color = "#f5a623"
        else:
            color = "#3fb950"
        self.create_rectangle(0, 0, fill_width, self.HEIGHT, fill=color, outline="")

        label = f"{percent:.2f}%" + ("  Warning" if warn else "")
        self.create_text(self.WIDTH / 2, self.HEIGHT / 2, text=label, fill="#1a1a1a", font=("Segoe UI", 9, "bold"))


class DiskInspectorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self._apply_modern_theme()

        self.title(APP_TITLE)
        self.geometry("1480x860")
        self.minsize(900, 550)

        self.scanning = False
        self.dup_state = "idle"
        self.stop_event_main = threading.Event()
        self.stop_event_dup = threading.Event()
        self.main_queue = queue.Queue()
        self.dup_queue = queue.Queue()
        self.delete_queue = queue.Queue()
        self._delete_in_progress = False
        self.sort_state = {}

        self.tree_paths = {}
        self.user_paths = {}
        self.dup_paths = {}
        self.dup_groups = {}
        self.junk_paths = {}

        self.stop_event_user = threading.Event()
        self.scanning_main = False
        self.scanning_user = False
        self.disk_list_frame = None
        self.current_active_tree = None

        self._build_ui()
        self._create_context_menu()

        self.after(300, self._prompt_admin)
        self.after(400, self.refresh_disks)
        self.after(150, self._poll_main_queue)
        self.after(150, self._poll_dup_queue)
        self.after(150, self._poll_delete_queue)
        
    def _apply_modern_theme(self):
        style = ttk.Style()
        available_themes = style.theme_names()
        if 'vista' in available_themes:
            style.theme_use('vista')
        elif 'clam' in available_themes:
            style.theme_use('clam')
            
        base_font = ('Segoe UI', 10)
        bold_font = ('Segoe UI', 10, 'bold')
        title_font = ('Segoe UI', 12, 'bold')
        
        style.configure('.', font=base_font)
        style.configure('TButton', padding=6, relief="flat", font=base_font)
        style.configure('Heading.TLabel', font=title_font)
        style.configure('Treeview', rowheight=26, font=base_font)
        style.configure('Treeview.Heading', font=bold_font, background="#f0f2f5")

    def _create_context_menu(self):
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Open in Explorer", command=self._menu_open_in_explorer)

    def _bind_context_menu(self, tree):
        tree.bind("<Button-3>", lambda e: self._on_right_click(e, tree))
        tree.bind("<Button-2>", lambda e: self._on_right_click(e, tree))

    def _on_right_click(self, event, tree):
        iid = tree.identify_row(event.y)
        if iid:
            if iid not in tree.selection():
                tree.selection_set(iid)
            self.current_active_tree = tree
            try:
                self.context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.context_menu.grab_release()

    def _on_double_click(self, event, tree):
        region = tree.identify_region(event.x, event.y)
        if region in ("heading", "separator"):
            try:
                total_w = sum(tree.column(c, "width") for c in tree["columns"])
                x_scroll_px = tree.xview()[0] * total_w
                absolute_x = event.x + x_scroll_px

                current_w = 0
                col_index = 0
                columns = tree["columns"]
                for i, c in enumerate(columns):
                    w = tree.column(c, "width")
                    if current_w <= absolute_x < current_w + w:
                        col_index = i
                        break
                    current_w += w
                else:
                    col_index = len(columns) - 1

                if 0 <= col_index < len(columns):
                    col_name = columns[col_index]
                    font = tkfont.Font(font=("Segoe UI", 9))
                    max_width = font.measure(str(tree.heading(col_name, "text"))) + 30
                    for iid in tree.get_children(""):
                        vals = tree.item(iid, "values")
                        if col_index < len(vals):
                            w = font.measure(str(vals[col_index])) + 30
                            if w > max_width:
                                max_width = w
                    max_width = max(max_width, 90)
                    tree.column(col_name, width=max_width)
                    tree.update_idletasks()
            except Exception as e:
                logging.error(f"Column auto-fit error: {e}")
        else:
            iid = tree.identify_row(event.y)
            if iid:
                tree.selection_set(iid)
                self._open_selected(tree)

    def _menu_open_in_explorer(self):
        if self.current_active_tree:
            self._open_selected(self.current_active_tree)
            
    def open_windows_disk_cleanup(self):
        """Launches Windows Disk Cleanup (cleanmgr.exe)."""
        if not IS_WINDOWS:
            messagebox.showinfo("Notice", "This feature is only supported on Windows.")
            return

        try:
            subprocess.Popen(["cleanmgr.exe"])
        except Exception as e:
            logging.error(f"Failed to execute Windows Disk Cleanup: {e}")
            messagebox.showerror("Error", f"Cannot run Windows Disk Cleanup:\n{e}")

    def _menu_delete_selected(self):
        if self.current_active_tree:
            tree = self.current_active_tree
            if tree is self.tree:
                self.delete_selected_main()
            elif tree is self.custom_tree:
                self._delete_from_tree(self.custom_tree)
            elif tree is self.dup_tree:
                self._delete_from_tree(self.dup_tree)
            elif tree is self.junk_tree:
                self.delete_junk_selected()

    def translate_health_status(self, status_text):
        if not status_text:
            return "Healthy"
        s = str(status_text).lower()
        if any(w in s for w in ["warning", "degraded", "caution"]):
            return "Warning"
        elif any(w in s for w in ["unhealthy", "critical", "bad", "error", "fail"]):
            return "Critical"
        else:
            return "Healthy"

    def get_disk_health_info(self):
        """Retrieves S.M.A.R.T disk health status via PowerShell."""
        health_map = {}
        if IS_WINDOWS:
            try:
                cmd = (
                    "Get-Partition | Where-Object { $_.DriveLetter } | ForEach-Object { "
                    "$p = $_; $d = Get-Disk -Number $p.DiskNumber -ErrorAction SilentlyContinue; "
                    "if ($d) { [PSCustomObject]@{ DriveLetter = $p.DriveLetter; "
                    "HealthStatus = $d.HealthStatus; FriendlyName = $d.FriendlyName } } "
                    "} | ConvertTo-Json -Compress"
                )
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", cmd],
                    capture_output=True,
                    text=True,
                    encoding='cp949',
                    errors='ignore',
                    startupinfo=startupinfo,
                    timeout=5
                )

                if result.returncode == 0 and result.stdout.strip():
                    data = json.loads(result.stdout.strip())
                    if isinstance(data, dict):
                        data = [data]
                    for item in data:
                        letter = item.get("DriveLetter")
                        if not letter:
                            continue
                        key = f"{letter}:".upper()
                        raw_status = item.get("HealthStatus", "Normal")
                        health_map[key] = self.translate_health_status(raw_status)
            except Exception as e:
                logging.error(f"Windows S.M.A.R.T lookup failed: {e}")
        else:
            if DeviceList is not None:
                try:
                    devices = DeviceList()
                    for dev in devices:
                        assessment = getattr(dev, 'assessment', 'UNKNOWN')
                        status = "Healthy"
                        if "FAIL" in str(assessment).upper() or "BAD" in str(assessment).upper():
                            status = "Critical"
                        elif "WARN" in str(assessment).upper():
                            status = "Warning"
                        health_map[dev.name] = status
                except Exception as e:
                    logging.error(f"Linux/macOS pySMART lookup failed: {e}")
            else:
                logging.info("pySMART package unavailable; skipping S.M.A.R.T lookup.")
        return health_map

    def _prompt_admin(self):
        if is_admin():
            self._update_admin_label()
            return
        answer = messagebox.askyesno(
            "Run as Administrator",
            "Would you like to restart this program with administrator privileges?\n\n"
            "Yes: Restart with admin privileges for a comprehensive system scan.\n"
            "No: Continue with standard user rights. Access to protected system folders\n"
            "will be restricted."
        )
        if answer:
            if not is_admin():
                if relaunch_as_admin():
                    self.destroy()
                    sys.exit(0)
                else:
                    messagebox.showwarning(
                        "Warning",
                        "Administrator relaunch was canceled or failed.\n"
                        "Continuing with standard user privileges."
                    )
        else:
            messagebox.showwarning("Warning", "Running with standard user privileges.\nSome system folders may be inaccessible.")
        self._update_admin_label()

    def _update_admin_label(self):
        admin = is_admin()
        text = "Admin Rights: Yes" if admin else "Admin Rights: No (Standard Mode)"
        color = "#1a7f37" if admin else "#b45309"
        self.admin_label.config(text=text, foreground=color)

    def _build_ui(self):
        self._build_bottom_bar()

        paned = ttk.Panedwindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True, side="top")

        left = ttk.Frame(paned)
        right = ttk.Frame(paned)
        paned.add(left, weight=7)
        paned.add(right, weight=1)

        self._build_left(left)
        self._build_right(right)

        self.refresh_disks()
                    
    def _build_left(self, parent):
        self.main_scan_section = ttk.LabelFrame(parent, text="Full Disk Scan")
        self.main_scan_section.pack(fill="x", padx=6, pady=(6, 4))
        
        top_bar = ttk.Frame(self.main_scan_section)
        top_bar.pack(fill="x", padx=6, pady=(6, 4))

        self.scan_btn = ttk.Button(top_bar, text="Start Scan", command=self.toggle_main_scan)
        self.scan_btn.pack(side="left")

        self.status_label = ttk.Label(top_bar, text="Idle", foreground="#555")
        self.status_label.pack(side="left", padx=(10, 0))

        self.admin_label = ttk.Label(top_bar, text="Admin Rights: Checking...")
        self.admin_label.pack(side="right")

        self.custom_section = ttk.LabelFrame(parent, text="User & External Device Data")
        self.custom_section.pack(fill="both", padx=6, pady=(0, 6), side="bottom")

        custom_btn_bar = ttk.Frame(self.custom_section)
        custom_btn_bar.pack(fill="x", padx=6, pady=2)
        
        self.custom_scan_btn = ttk.Button(custom_btn_bar, text="Start Scan", command=self.toggle_user_scan)
        self.custom_scan_btn.pack(side="left")
        
        self.custom_status_label = ttk.Label(custom_btn_bar, text="Idle", foreground="#555")
        self.custom_status_label.pack(side="left", padx=(9, 0))
        
        custom_wrap = ttk.Frame(self.custom_section)
        custom_wrap.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        custom_cols = ("location", "name", "size", "attr", "desc")
        self.custom_tree = ttk.Treeview(custom_wrap, columns=custom_cols, show="headings", height=6, selectmode="browse")
        
        custom_headings = {"location": "Location", "name": "Folder/File Name", "size": "Size (GB)", "attr": "Data Attribute", "desc": "Description"}
        custom_widths = {"location": 240, "name": 140, "size": 85, "attr": 120, "desc": 160}
        
        for col in custom_cols:
            self.custom_tree.heading(col, text=custom_headings[col], command=lambda c=col: self._sort_tree(self.custom_tree, c))
            self.custom_tree.column(col, width=custom_widths[col], anchor="w", stretch=False)
            
        custom_vbar = ttk.Scrollbar(custom_wrap, orient="vertical", command=self.custom_tree.yview)
        custom_hbar = ttk.Scrollbar(custom_wrap, orient="horizontal", command=self.custom_tree.xview)
        self.custom_tree.configure(yscrollcommand=custom_vbar.set, xscrollcommand=custom_hbar.set)

        self.custom_tree.grid(row=0, column=0, sticky="nsew")
        custom_vbar.grid(row=0, column=1, sticky="ns")
        custom_hbar.grid(row=1, column=0, sticky="ew")

        custom_wrap.grid_rowconfigure(0, weight=1)
        custom_wrap.grid_rowconfigure(1, weight=0)
        custom_wrap.grid_columnconfigure(0, weight=1)

        tree_frame = ttk.Frame(parent)
        tree_frame.pack(side="top", fill="both", expand=True, padx=6, pady=(0, 6))

        columns = ("location", "name", "size", "attr", "desc")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        
        headings = {"location": "Location", "name": "Folder/File Name", "size": "Size (GB)", "attr": "Attribute (Type)", "desc": "Description"}
        widths = {"location": 280, "name": 180, "size": 85, "attr": 110, "desc": 180}
        
        for col in columns:
            self.tree.heading(col, text=headings[col], command=lambda c=col: self._sort_tree(self.tree, c))
            self.tree.column(col, width=widths[col], anchor="w", stretch=False)
        
        self.tree.tag_configure("anomaly", foreground="#b30000")
        
        vbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hbar = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")
        hbar.grid(row=1, column=0, sticky="ew")
        
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(1, weight=0)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        self.tree.bind("<Double-1>", lambda e: self._on_double_click(e, self.tree))
        self.custom_tree.bind("<Double-1>", lambda e: self._on_double_click(e, self.custom_tree))
        self._bind_detail_select(self.tree)
        self._bind_detail_select(self.custom_tree)

        self._bind_context_menu(self.tree)
        self._bind_context_menu(self.custom_tree)
        
    def _build_detail_panel(self, parent):
        inner = ttk.Frame(parent)
        inner.pack(fill="both", expand=True, padx=8, pady=8)

        self.detail_labels = {}
        fields = [
            ("location", "Location"),
            ("name", "Name"),
            ("size", "Size (GB)"),
            ("attr", "Attribute"),
        ]
        for key, label_text in fields:
            row = ttk.Frame(inner)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=f"{label_text}:", font=("Segoe UI", 9, "bold"), width=10, anchor="w").pack(side="left")
            val_label = ttk.Label(row, text="-", foreground="#333", wraplength=480, anchor="w", justify="left")
            val_label.pack(side="left", fill="x", expand=True)
            self.detail_labels[key] = val_label

        desc_row = ttk.Frame(inner)
        desc_row.pack(fill="both", expand=True, pady=(4, 4))
        ttk.Label(desc_row, text="Description:", font=("Segoe UI", 9, "bold"), width=10, anchor="nw").pack(side="left", anchor="n")
        self.detail_desc_label = ttk.Label(
            desc_row, text="Click an item in the list to view detailed information.",
            foreground="#333", wraplength=480, anchor="w", justify="left"
        )
        self.detail_desc_label.pack(side="left", fill="both", expand=True)

        btn_bar = ttk.Frame(inner)
        btn_bar.pack(fill="x", pady=(8, 0))
        self.detail_google_btn = ttk.Button(
            btn_bar, text="🔍 Search on Google", command=self._search_selected_on_google, state="disabled"
        )
        self.detail_google_btn.pack(side="left")

        self.detail_google_ai_btn = ttk.Button(
            btn_bar, text="🤖 Google AI Search", command=self._search_selected_on_google_ai, state="disabled"
        )
        self.detail_google_ai_btn.pack(side="left", padx=(5, 0))

        self._selected_detail_name = None

        def _on_detail_resize(event):
            wrap = max(200, event.width - 100)
            for lbl in self.detail_labels.values():
                lbl.configure(wraplength=wrap)
            self.detail_desc_label.configure(wraplength=wrap)
        inner.bind("<Configure>", _on_detail_resize)

    def _bind_detail_select(self, tree):
        tree.bind("<<TreeviewSelect>>", lambda e, t=tree: self._on_tree_select(t))

    def _on_tree_select(self, tree):
        sel = tree.selection()
        if not sel:
            return
        values = tree.item(sel[0], "values")
        if len(values) < 5:
            return
        location, name, size, attr, desc = values[:5]

        self.detail_labels["location"].configure(text=location or "-")
        self.detail_labels["name"].configure(text=name or "-")
        self.detail_labels["size"].configure(text=f"{size} GB" if size else "-")
        self.detail_labels["attr"].configure(text=attr or "-")
        self.detail_desc_label.configure(text=desc or "-")

        self._selected_detail_name = name
        state = "normal" if name else "disabled"
        self.detail_google_btn.configure(state=state)
        self.detail_google_ai_btn.configure(state=state)

    def _search_selected_on_google(self):
        name = self._selected_detail_name
        if not name:
            return
        try:
            webbrowser.open(f"https://www.google.com/search?q={quote_plus(name)}")
        except Exception as e:
            logging.error(f"Failed to open browser for Google Search: {e}")
            messagebox.showerror("Error", "Failed to open default web browser.")

    def _search_selected_on_google_ai(self):
        name = self._selected_detail_name
        if not name:
            return
        query = f"what is {name} folder file can I delete it"
        try:
            webbrowser.open(f"https://www.google.com/search?q={quote_plus(query)}&udm=50")
        except Exception as e:
            logging.error(f"Failed to open browser for Google AI Search: {e}")
            messagebox.showerror("Error", "Failed to open default web browser.")

    def _build_right(self, parent):
        top_pane = ttk.Frame(parent)
        top_pane.pack(fill="both", expand=True, padx=4, pady=(4, 4))

        detail_section = ttk.LabelFrame(top_pane, text="Description / Search")
        detail_section.pack(side="left", fill="both", expand=True, padx=(0, 4))
        self._build_detail_panel(detail_section)

        self.DISK_PANEL_WIDTH = 330
        disk_section = ttk.LabelFrame(top_pane, text="Disk List")
        disk_section.pack(side="right", fill="y", padx=0, pady=0)
        disk_section.configure(width=self.DISK_PANEL_WIDTH)
        disk_section.pack_propagate(False)

        self.disk_scroll = ScrollableFrame(disk_section)
        self.disk_scroll.pack(fill="both", expand=True, padx=6, pady=6)
        self.disk_list_frame = self.disk_scroll.inner

        bottom_pane = ttk.Frame(parent)
        bottom_pane.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        common_cols = ("location", "name", "size", "attr", "desc")
        common_widths = {"location": 180, "name": 130, "size": 85, "attr": 110, "desc": 120}
        common_headings = ("Location", "Folder/File Name", "Size (GB)", "Attribute", "Description")
        tree_height = 5

        dup_section = ttk.LabelFrame(bottom_pane, text="Duplicate Files Scan")
        dup_section.pack(fill="both", padx=0, pady=(0, 4), expand=True)
        
        dup_btn_bar = ttk.Frame(dup_section)
        dup_btn_bar.pack(fill="x", padx=6, pady=(6, 2))
        self.dup_btn = ttk.Button(dup_btn_bar, text="Start Scan", command=self.toggle_dup_scan)
        self.dup_btn.pack(side="left")
        
        self.dup_status_label = ttk.Label(dup_btn_bar, text="Idle", foreground="#555")
        self.dup_status_label.pack(side="left", padx=(10, 0))
        
        dup_wrap = ttk.Frame(dup_section)
        dup_wrap.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        
        self.dup_tree = ttk.Treeview(dup_wrap, columns=common_cols, show="headings", height=tree_height, selectmode="browse")
        for c, t in zip(common_cols, common_headings):
            self.dup_tree.heading(c, text=t, command=lambda col=c: self._sort_tree(self.dup_tree, col))
            self.dup_tree.column(c, width=common_widths[c], anchor="w", stretch=False)
            
        dup_vbar = ttk.Scrollbar(dup_wrap, orient="vertical", command=self.dup_tree.yview)
        dup_hbar = ttk.Scrollbar(dup_wrap, orient="horizontal", command=self.dup_tree.xview)
        self.dup_tree.configure(yscrollcommand=dup_vbar.set, xscrollcommand=dup_hbar.set)
        
        self.dup_tree.grid(row=0, column=0, sticky="nsew")
        dup_vbar.grid(row=0, column=1, sticky="ns")
        dup_hbar.grid(row=1, column=0, sticky="ew")
        
        dup_wrap.grid_rowconfigure(0, weight=1)
        dup_wrap.grid_rowconfigure(1, weight=0)
        dup_wrap.grid_columnconfigure(0, weight=1)
        
        self.dup_tree.bind("<Double-1>", lambda e: self._on_double_click(e, self.dup_tree))
        self._bind_detail_select(self.dup_tree)
        self._bind_context_menu(self.dup_tree)

        junk_section = ttk.LabelFrame(bottom_pane, text="Temporary Files Scan")
        junk_section.pack(fill="both", padx=0, pady=(4, 0), expand=True)
        
        junk_btn_bar = ttk.Frame(junk_section)
        junk_btn_bar.pack(fill="x", padx=6, pady=(6, 2))
        self.junk_scan_btn = ttk.Button(junk_btn_bar, text="Start Scan", command=self.scan_junk_only)
        self.junk_scan_btn.pack(side="left")
        
        self.junk_status_label = ttk.Label(junk_btn_bar, text="Idle", foreground="#555")
        self.junk_status_label.pack(side="left", padx=(10, 0))

        junk_wrap = ttk.Frame(junk_section)
        junk_wrap.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        
        self.junk_tree = ttk.Treeview(junk_wrap, columns=common_cols, show="headings", height=tree_height, selectmode="browse")
        for c, t in zip(common_cols, common_headings):
            self.junk_tree.heading(c, text=t, command=lambda col=c: self._sort_tree(self.junk_tree, col))
            self.junk_tree.column(c, width=common_widths[c], anchor="w", stretch=False)
            
        junk_vbar = ttk.Scrollbar(junk_wrap, orient="vertical", command=self.junk_tree.yview)
        junk_hbar = ttk.Scrollbar(junk_wrap, orient="horizontal", command=self.junk_tree.xview)
        self.junk_tree.configure(yscrollcommand=junk_vbar.set, xscrollcommand=junk_hbar.set)
        
        self.junk_tree.grid(row=0, column=0, sticky="nsew")
        junk_vbar.grid(row=0, column=1, sticky="ns")
        junk_hbar.grid(row=1, column=0, sticky="ew")
        
        junk_wrap.grid_rowconfigure(0, weight=1)
        junk_wrap.grid_rowconfigure(1, weight=0)
        junk_wrap.grid_columnconfigure(0, weight=1)
        
        self.junk_tree.bind("<Double-1>", lambda e: self._on_double_click(e, self.junk_tree))
        self._bind_detail_select(self.junk_tree)
        self._bind_context_menu(self.junk_tree)
        
        self.win_clean_btn = ttk.Button(
            junk_btn_bar, text="Run Disk Cleanup", command=self.open_windows_disk_cleanup
        )
        self.win_clean_btn.pack(side="right")

    def _build_bottom_bar(self):
        bar = ttk.Frame(self)
        bar.pack(fill="x", side="bottom", padx=8, pady=6)

        left_group = ttk.Frame(bar)
        left_group.pack(side="left")
        ttk.Button(left_group, text="Exit", command=self._on_exit).pack(side="left")
        ttk.Button(bar, text="Info", command=self._show_info_popup).pack(side="right")

    def _get_path_map(self, tree):
        if tree is self.tree:
            return self.tree_paths
        if tree is self.custom_tree:
            return self.user_paths
        if tree is self.dup_tree:
            return self.dup_paths
        if tree is self.junk_tree:
            return self.junk_paths
        return {}

    def _sort_tree(self, tree, col):
        items = [(tree.set(iid, col), iid) for iid in tree.get_children("")]
        key = (id(tree), col)
        ascending = not self.sort_state.get(key, False)
        self.sort_state[key] = ascending

        def sort_key(pair):
            val, _ = pair
            if col == "size" or col == "Size (GB)":
                try:
                    return float(val)
                except ValueError:
                    return 0.0
            return str(val).lower()

        items.sort(key=sort_key, reverse=not ascending)
        for index, (_, iid) in enumerate(items):
            tree.move(iid, "", index)

    def _open_selected(self, tree):
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Notice", "Please select an item from the list first.")
            return
        path_map = self._get_path_map(tree)
        path = path_map.get(sel[0])
        if path:
            open_in_explorer(path)
        else:
            messagebox.showinfo("Notice", "Path information could not be found.")

    def refresh_disks(self):
        if not hasattr(self, 'disk_list_frame') or self.disk_list_frame is None:
            return

        for child in self.disk_list_frame.winfo_children():
            child.destroy()
            
        disks = list_disks()
        if not disks:
            ttk.Label(self.disk_list_frame, text="Unable to load disk information.").pack(anchor="w", padx=10, pady=10)
            return
            
        health_map = self.get_disk_health_info()
        chart_width = max(120, self.DISK_PANEL_WIDTH - 60)
        wrap = max(120, self.DISK_PANEL_WIDTH - 40)

        for d in disks:
            row = ttk.Frame(self.disk_list_frame)
            row.pack(fill="x", pady=5, padx=5)

            self.disk_scroll.bind_mousewheel(row)

            title_text = f"{d['device']} [{d['fstype']}]"
            ttk.Label(row, text=title_text, font=("Segoe UI", 9, "bold"), wraplength=wrap, anchor="w", justify="left").pack(anchor="w")

            if d.get("warn"):
                ttk.Label(row, text="⚠ Warning: Disk usage over 80%.", foreground="#b30000", font=("Segoe UI", 9), wraplength=wrap, anchor="w", justify="left").pack(anchor="w")

            info_text = f"Total {human_gb(d['total'])}GB · Used {human_gb(d['used'])}GB"
            ttk.Label(row, text=info_text, foreground="#444", wraplength=wrap, anchor="w", justify="left").pack(anchor="w")

            mountpoint = d.get("mountpoint", "") or d.get("device", "")
            disk_identifier = mountpoint[:2].upper() if len(mountpoint) >= 2 and mountpoint[1] == ":" else mountpoint
            status_val = health_map.get(disk_identifier, "Healthy")
            smart_info = f"Status: {status_val} (S.M.A.R.T.)"
            
            color_map = {
                "Healthy": "#1a7f37",
                "Warning": "#b45309",
                "Critical": "#b30000"
            }
            status_color = color_map.get(status_val, "#1a7f37")
            
            ttk.Label(row, text=smart_info, foreground=status_color, font=("Segoe UI", 9), wraplength=wrap, anchor="w", justify="left").pack(anchor="w")
            
            DiskBarChart(row, d, width=chart_width).pack(anchor="w", pady=(2, 5))        

    def toggle_main_scan(self):
        if self.scanning_main:
            self.stop_event_main.set()
            self.status_label.config(text="Stopping...")
            self.scan_btn.config(text="Start Scan")
            self.scanning_main = False
        else:
            self.scanning_main = True
            self.stop_event_main.clear()
            self.scan_btn.config(text="Stop")
            self.status_label.config(text="Scanning...", foreground="#b45309")
            self.tree.delete(*self.tree.get_children())
            threading.Thread(target=self._main_scan_worker, daemon=True).start()

    def toggle_user_scan(self):
        if self.scanning_user:
            self.stop_event_user.set()
            self.custom_status_label.config(text="Stopping...")
            self.custom_scan_btn.config(text="Start Scan")
            self.scanning_user = False
        else:
            self.scanning_user = True
            self.stop_event_user.clear()
            self.custom_scan_btn.config(text="Stop")
            self.custom_status_label.config(text="Scanning...", foreground="#b45309")
            self.custom_tree.delete(*self.custom_tree.get_children())
            threading.Thread(target=self._user_scan_worker, daemon=True).start()

    def _main_scan_worker(self):
        disks = list_disks()
        roots = [d["mountpoint"] for d in disks]

        def progress(msg):
            self.main_queue.put(("status", f"Scanning..... ({msg[:60]})"))

        folder_results = scan_folder_sizes(roots, self.stop_event_main, progress)
        for r in folder_results:
            self.main_queue.put(("row", r))

        junk_results = scan_junk_files(self.stop_event_main, progress)
        for r in junk_results:
            self.main_queue.put(("row", r))

        self.main_queue.put(("done", None))

    def _insert_main_row(self, r):
        path = r.get("path") or os.path.join(r["location"], r["name"])
        size_gb = human_gb(r["size_bytes"])
        tags = ("anomaly",) if r.get("anomaly") else ()
        iid = self.tree.insert("", "end", values=(r["location"], r["name"], size_gb, r.get("attr", "Normal"), r["desc"]), tags=tags)
        self.tree_paths[iid] = path
        
    def _user_scan_worker(self):
        results = scan_user_data(stop_event=self.stop_event_user) 
        
        def update_ui():
            self.custom_tree.delete(*self.custom_tree.get_children())
            self.user_paths.clear()
            if results:
                for item in results:
                    size_gb = human_gb(item["size_bytes"])
                    iid = self.custom_tree.insert("", "end", values=(item["location"], item["name"], size_gb, item["attr"], item["desc"]))
                    self.user_paths[iid] = item["path"]
                self.custom_status_label.config(text=f"{len(results)} item(s) found", foreground="green")
            else:
                self.custom_status_label.config(text="No results found", foreground="red")
            
            self.scanning_user = False
            self.custom_scan_btn.config(text="Start Scan", state="normal")
            
        self.after(0, update_ui)    

    def toggle_dup_scan(self):
        if self.dup_state == "idle":
            self.dup_state = "running"
            self.stop_event_dup.clear()
            self.dup_btn.config(text="Stop")
            self.dup_status_label.config(text="Scanning.....", foreground="#b45309")
            for iid in self.dup_tree.get_children():
                self.dup_tree.delete(iid)
            self.dup_paths.clear()
            self.dup_groups.clear()
            threading.Thread(target=self._dup_scan_worker, daemon=True).start()
        else:
            self.stop_event_dup.set()
            self.dup_status_label.config(text="Stopping.....")

    def _dup_scan_worker(self):
        disks = list_disks()
        roots = [d["mountpoint"] for d in disks]

        def progress(msg):
            self.dup_queue.put(("status", f"Scanning..... ({msg[:50]})"))

        results = find_duplicate_files(roots, self.stop_event_dup, progress)
        for r in results:
            if self.stop_event_dup.is_set():
                break
            self.dup_queue.put(("row", r))

        if self.stop_event_dup.is_set():
            self.dup_queue.put(("stopped", None))
        else:
            self.dup_queue.put(("done", None))

    def _insert_dup_row(self, r):
        size_gb = human_gb(r["size_bytes"])
        iid = self.dup_tree.insert("", "end", values=(r["location"], r["name"], size_gb, r["attr"], r["desc"]))
        self.dup_paths[iid] = r["path"]
        self.dup_groups[iid] = r.get("group_id")

    def scan_junk_only(self):
        self.junk_scan_btn.config(state="disabled")
        self.junk_status_label.config(text="Scanning.....", foreground="#b45309")
        for iid in self.junk_tree.get_children():
            self.junk_tree.delete(iid)
        self.junk_paths.clear()
        threading.Thread(target=self._junk_scan_worker, daemon=True).start()

    def _junk_scan_worker(self):
        results = scan_junk_files()
        self.main_queue.put(("junk_rows", results))

    def _insert_junk_row(self, r):
        size_gb = human_gb(r["size_bytes"])
        path = r.get("path") or os.path.join(r["location"], r["name"])
        iid = self.junk_tree.insert("", "end", values=(r["location"], r["name"], size_gb, r["attr"], r["desc"]))
        self.junk_paths[iid] = path

    def delete_junk_selected(self):
        self._delete_from_tree(self.junk_tree)

    def delete_selected_main(self):
        self._delete_from_tree(self.tree)

    def _delete_from_tree(self, tree):
        if self._delete_in_progress:
            messagebox.showinfo("Notice", "Previous delete operation is still in progress. Please try again shortly.")
            return

        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Notice", "Please select an item to delete first.")
            return
            
        path_map = self._get_path_map(tree)
        paths = [(iid, path_map.get(iid)) for iid in sel]
        paths = [(iid, p) for iid, p in paths if p]
        if not paths:
            return

        assessed = [(iid, p, assess_delete_target(p)) for iid, p in paths]
        blocked = [(iid, p, info) for iid, p, info in assessed if info["blocked"]]
        deletable = [(iid, p, info) for iid, p, info in assessed if not info["blocked"]]

        kept_for_safety = []
        if tree is self.dup_tree and deletable:
            group_all_iids = defaultdict(list)
            for iid in tree.get_children(""):
                gid = self.dup_groups.get(iid)
                if gid is not None:
                    group_all_iids[gid].append(iid)

            deletable_iid_set = {iid for iid, _, _ in deletable}
            protect_iids = set()
            for gid, all_iids in group_all_iids.items():
                if all_iids and all(iid in deletable_iid_set for iid in all_iids):
                    protect_iids.add(all_iids[0])

            if protect_iids:
                kept_for_safety = [p for iid, p, info in deletable if iid in protect_iids]
                deletable = [(iid, p, info) for iid, p, info in deletable if iid not in protect_iids]

        if not deletable:
            msg_parts = []
            if kept_for_safety:
                msg_parts.append(
                    "The following items were preserved to keep at least one copy in duplicate groups:\n" +
                    "\n".join(f"- {os.path.basename(p)}" for p in kept_for_safety[:10])
                )
            if blocked:
                msg_parts.append(
                    "Selected items protected by system rules cannot be deleted:\n" +
                    "\n".join(f"- {p}\n  ({info['reason']})" for _, p, info in blocked[:10])
                )
            if not msg_parts:
                msg_parts.append("The selected items cannot be deleted.")
            messagebox.showwarning("Deletion Blocked", "\n\n".join(msg_parts))
            return
        
        preview = "\n".join(f"[{info['type']}] {os.path.basename(p)}" for _, p, info in deletable[:5])
        if len(deletable) > 5:
            preview += "\n..."

        warn_block = ""
        if blocked:
            blocked_preview = "\n".join(f"- [{info['type']}] {os.path.basename(p)} ({info['reason']})" for _, p, info in blocked[:5])
            warn_block = f"\n\n⚠ The following {len(blocked)} item(s) were excluded because they are system protected:\n{blocked_preview}"

        safety_block = ""
        if kept_for_safety:
            safety_preview = "\n".join(f"- {os.path.basename(p)}" for p in kept_for_safety[:5])
            safety_block = (
                f"\n\nℹ The following {len(kept_for_safety)} item(s) were automatically excluded to "
                f"preserve at least one original copy:\n{safety_preview}"
            )

        confirm = messagebox.askyesno(
            "Confirm Deletion (Warning)",
            f"Are you sure you want to move the selected {len(deletable)} item(s) to the Recycle Bin?\n\n{preview}{warn_block}{safety_block}"
        )
        if not confirm:
            return

        self._delete_in_progress = True
        try:
            self.config(cursor="watch")
        except Exception:
            pass
        threading.Thread(
            target=self._delete_worker, args=(tree, path_map, deletable), daemon=True
        ).start()

    def _delete_worker(self, tree, path_map, deletable):
        errors = []
        deleted_iids = []
        for iid, path, info in deletable:
            try:
                send2trash(path)
                deleted_iids.append(iid)
            except Exception as e:
                err_msg = f"Failed to delete {os.path.basename(path)}: {e}"
                errors.append(err_msg)
                logging.error(err_msg)
                continue
        self.delete_queue.put((tree, path_map, deleted_iids, errors))

    def _poll_delete_queue(self):
        try:
            while True:
                tree, path_map, deleted_iids, errors = self.delete_queue.get_nowait()
                for iid in deleted_iids:
                    try:
                        tree.delete(iid)
                    except tk.TclError:
                        pass
                    path_map.pop(iid, None)
                    self.dup_groups.pop(iid, None)

                self._delete_in_progress = False
                try:
                    self.config(cursor="")
                except Exception:
                    pass

                if errors:
                    messagebox.showwarning("Completed (Partial Failures)", "Failed to delete some items (See Disk_Check.log):\n" + "\n".join(errors[:10]))
                else:
                    messagebox.showinfo("Completed", "Selected items have been moved to the Recycle Bin.")
        except queue.Empty:
            pass
        self.after(150, self._poll_delete_queue)

    def _poll_main_queue(self):
        try:
            while True:
                kind, payload = self.main_queue.get_nowait()
                if kind == "status":
                    self.status_label.config(text=payload)
                elif kind == "row":
                    self._insert_main_row(payload)
                elif kind == "done":
                    self.scanning = False
                    self.scan_btn.config(text="Start Scan", state="normal")
                    self.status_label.config(text="Scan Complete", foreground="#1a7f37")
                elif kind == "junk_rows":
                    for r in payload:
                        self._insert_junk_row(r)
                    self.junk_scan_btn.config(state="normal")
                    self.junk_status_label.config(text="Scan Complete", foreground="#1a7f37")
        except queue.Empty:
            pass
        self.after(150, self._poll_main_queue)

    def _poll_dup_queue(self):
        try:
            while True:
                kind, payload = self.dup_queue.get_nowait()
                if kind == "status":
                    self.dup_status_label.config(text=payload)
                elif kind == "row":
                    self._insert_dup_row(payload)
                elif kind == "done":
                    self.dup_state = "idle"
                    self.dup_btn.config(text="Start Scan")
                    self.dup_status_label.config(text="Scan Complete", foreground="#1a7f37")
                elif kind == "stopped":
                    self.dup_state = "idle"
                    self.dup_btn.config(text="Start Scan", state="normal")
                    self.dup_status_label.config(text="Stopped", foreground="#888")
        except queue.Empty:
            pass
        self.after(150, self._poll_dup_queue)

    def _show_info_popup(self):
        top = tk.Toplevel(self)
        top.title("Information")
        top.geometry("530x380")
        top.transient(self)
        top.grab_set()

        text = tk.Text(top, wrap="word", padx=14, pady=14, font=("Segoe UI", 10))
        text.pack(fill="both", expand=True)
        content = (
            "[Disk Inspector Tool Guide & Disclaimer]\n\n"
            "1. This program is an auxiliary utility designed to assist with disk space analysis and cleanup.\n\n"
            "2. File/folder deletion errors and logs are recorded in the 'Disk_Check.log' file.\n\n"
            "3. The user assumes full responsibility for any data loss, system instability, or software errors resulting from deletions.\n\n"
            "4. Please make sure to back up essential files before executing deletion operations.\n\n"
            " Author: soedam147 / seodam147@gmail.com\n"
        )
        text.insert("1.0", content)
        text.config(state="disabled")
        ttk.Button(top, text="Close", command=top.destroy).pack(pady=(0, 11))

    def _on_exit(self):
        if messagebox.askyesno("Exit", "Are you sure you want to exit the program?"):
            self.stop_event_main.set()
            self.stop_event_dup.set()
            self.destroy()


def main():
    if psutil is None:
        print("Warning: psutil package is not installed. Run 'pip install psutil' and try again.")
    app = DiskInspectorApp()
    app.mainloop()


if __name__ == "__main__":
    main()