# ---------------------------------------------------------------------------
# WARNING: The original author's copyright information cannot be deleted.
# Author: seodam147 | Copyright (c) 2026 seodam147. All rights reserved.
# This code is distributed under the MIT License.
# ---------------------------------------------------------------------------

# -*- coding: utf-8 -*-
"""
Windows System Check Tool
=============================================
Windows System Check Tool
=============================================
# [Author/Copyright]
# Author: seodam147 | Copyright (c) 2026 seodam147. All rights reserved.
#
# [Program highlights]
# 1. Performance and stability improvements: 
#    - PowerShell Optimize the number of process executions and improve speed by consolidating call methods.
#    - Base64 encoding/Fundamentally solved the problem of broken Korean characters and special characters by applying a decoding method.
#    - Enhanced background thread error logging (error_log.txt) and exception handling.
#
# 2. Strengthened hardware and storage inspection:
#    - Correct misprint for graphics card VRAM 4GB or more (refer to 64-bit registry).
#    - NIC Team_(LBFO)/SET) Detailed analysis of detection and redundancy connection status.
#    - MPIO(multipath) and disk read/Write error counter (ReliabilityCounter) based health diagnosis.
#    - NAS/SMB Added shared and NFS drive identification features.
#
# 3. Virtualization and service monitoring:
#    - Hyper-V host/Guest detection and guest VM details (status, CPU/memory usage) display.
#    - Docker Added container and Kubernetes (kubelet) execution status monitoring function.
#    - Improved grouping and visualization by service category.
#
# 4. User convenience and UI/UX:
#    - Supports immediate data update by adding a refresh button.
#    - Expand long text when clicked/Supports folding function and mouse wheel scrolling.
#    - Get event log inquiry method-WinEvent(PowerShell)Remove pywin32 dependency by replacing it with .
#
# 5. etc:
#    - Clarification of error message and adjustment of timeout when administrator privileges are insufficient.
#    - Improved real-time screen flickering and added logic to preserve canvas scroll position.
# ---------------------------------------------------------------------------
## ⚖️ Copyright and License & License)

This project complies with the open source licensing policy, protects the rights of the original author, and aims to share and develop software.

### 1. Copyright Notice
The original copyright of this software is [Original author: seodam147]There is.
Copyright (c) 2026 seodam147. All rights reserved.

### 2. License
This project [MIT License]Follow.Use, copy or modify the Software;
Anyone who distributes must comply with the terms of that license.

### 3. Disclaimer
THE SOFTWARE IS PROVIDED “AS IS” WITHOUT WARRANTY OF ANY KIND.arising from the use of the software.
The original author and contributors are not liable for any consequences or damages.

*If you modify or redistribute this project, please be sure to include the above copyright notice and a copy of the license.*

- **Words of strength for developers : seodam147@gmail.com

"""

import os
import sys

# [addition] PyInstallerto "windowed mode (--windowed/--noconsole)" EXEIf you create , there is no console.
# sys.stdout/sys.stderrbecomes None.In this state, print() is called (print in the code,
# Or, if an unhandled exception (including warning output inside the library) tries to output a traceback,
# "AttributeError: 'NoneType' object has no attribute 'write'"Happens, without any guidance
# It may quit immediately after launch or appear to not run at all.Prevent it at the top.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

import re
import base64
import json
import socket
import platform
import subprocess
import threading
import time
import traceback
import concurrent.futures
import webbrowser
import qrcode
from PIL import ImageTk, Image
from collections import deque
from datetime import datetime
VERSION = "1.1.0"  # version control part

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

try:
    import psutil
except ImportError:
    print("psutilIt is not installed.Open a CMD window and run 'pip install psutil'.")
    sys.exit(1)

IS_WINDOWS = platform.system() == "Windows"

# [addition] When an unhandled exception occurs in a background thread (_slow_loop, _cpu_sampler_loop, etc.)
# The default behavior is to print a traceback to the console, but in a windowed EXE, set None to devnull above.
# Even if it is changed, the contents are just thrown away and the cause cannot be determined.as error_log.txt in the same folder as the exe file
# By leaving this, you can later check for issues such as updates quietly stopping only on certain servers.
def _thread_excepthook(args):
    try:
        base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        with open(os.path.join(base_dir, "error_log.txt"), "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now()}] background thread error: {args.exc_value}\n")
            f.write("".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)) + "\n")
    except Exception:
        pass


threading.excepthook = _thread_excepthook

# ---------------------------------------------------------------------------
# color / style definition
# ---------------------------------------------------------------------------
COLOR_BG = "#ffffff"
COLOR_BORDER = "#3b6ea5"
COLOR_TITLE = "#111111"
COLOR_SECTION_TITLE = "#111111"
COLOR_LABEL = "#333333"
COLOR_VALUE = "#111111"
COLOR_CPU_BAR = "#e8791a"
COLOR_RAM_BAR = "#f5c518"
COLOR_DISK_BAR = "#8bc34a"
COLOR_BAR_BG = "#ffffff"
COLOR_BUTTON = "#3f7ede"
COLOR_BUTTON_ACTIVE = "#2f63b8"
COLOR_BUTTON_TEXT = "#ffffff"
COLOR_ERR = "#c0392b"
COLOR_INFO = "#333333"



# [correction] [Console]::SetOut(...)I tried setting the standard output encoding to UTF8, but in reality it was still
# There was a broken server.Windows PowerShell (5.1) while redirected to a pipe
# ConsoleHost The path that handles output encoding internally is [Console]::OutDo not use as is
# In some cases (the host continues to use the original output path it already captured at startup), this script
# from_the_side [Console]::OutEven if you change it later, it may not actually take effect.
# [fundamental modification] PowerShell results are converted to UTF8 bytes to ensure that no code is broken regardless of the code page used.
# After changing it, encode it as Base64 (using only pure ASCII characters) and pass it on, and use Base64 on the Python side.
# Decode and restore the original UTF8 text.Base64 is A-Z/a-z/0-9/+//=I only use this
# What code page (CP949) do the characters have?/CP1252/UTF8 etc.), it is always the same byte value, so
# It can never be broken, no matter what encoding it is misinterpreted.
_PS_UTF8_PREAMBLE = (
    "$OutputEncoding = [System.Text.Encoding]::UTF8;"
    "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8;"
)


def _wrap_ps_base64(cmd):
    """cmd(The final output of the Powershell code) is UTF8 -> Base64Wrap it with , regardless of the code page.
    Always make sure that the original text (including non-ASCII characters such as Korean) can be restored as is.
    [correction] At first, just parentheses ( {cmd} )I wrapped it with , and the cmd strings in this project are
    try/catch, foreach, several $variable = ... It is a complex multi-line code mixed with assignment statements.
    With simple parenthesis grouping, PowerShell may give a syntax error and not run at all.
    (As a result, all views were "Unable to verify"/"A regression with “Log search failure” occurred).
    script block { ... }call operator &The method of executing is a random mixture of several sentences.
    This method allows you to always safely execute the code and pass the output directly to the pipe.
    I replaced it."""
    return (
        f"{_PS_UTF8_PREAMBLE}"
        f"$__ps_result = (& {{ {cmd} }}) | Out-String;"
        "[Console]::Out.Write([Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($__ps_result)))"
    )


def _decode_ps_base64(raw_bytes):
    """PowerShellThis restores the exported Base64 text to its original UTF8 string.
    Base64is pure ASCII, so decoding at this point is always safe."""
    b64_text = raw_bytes.decode("ascii", errors="ignore").strip()
    if not b64_text:
        return ""
    try:
        return base64.b64decode(b64_text, validate=False).decode("utf-8", errors="ignore").strip()
    except Exception:
        # Base64 If the decoding itself fails (e.g.: (Exception: If nothing is output) Even the original text is returned.
        return b64_text


def run_ps(cmd, timeout=10):
    """PowerShell Returns a result string after executing the command.
    [correction] Changed the method of receiving the result by wrapping it in Base64. - Hangul, etc. regardless of code page
    Non-ASCII characters are never broken (see _wrap_ps_base64 comment for details on why)."""
    if not IS_WINDOWS:
        return ""
    try:
        full_cmd = _wrap_ps_base64(cmd)
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", full_cmd],
            stderr=subprocess.DEVNULL, timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        return _decode_ps_base64(out)
    except Exception:
        return ""


def run_ps_detailed(cmd, timeout=10):
    """PowerShell After execution, returns a tuple (standard output, standard error).
    [addition] Standard error is also captured to determine the cause of failure, such as whether administrator privileges are required.
    [correction] Standard output is wrapped in Base64, like run_ps, and restored to prevent Korean characters from being broken."""
    if not IS_WINDOWS:
        return "", ""
    try:
        full_cmd = _wrap_ps_base64(cmd)
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", full_cmd],
            capture_output=True, timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        out = _decode_ps_base64(proc.stdout)
        err = proc.stderr.decode("utf-8", errors="ignore").strip()
        return out, err
    except Exception as e:
        return "", str(e)


_PERM_KEYWORDS = ("access is denied", "access denied", "administrator", "elevat", "no permission", "administrator privilege", "unauthorized")


def _is_permission_error(err_text: str) -> bool:
    """PowerShell Check for keywords indicating insufficient privileges in the standard error string"""
    low = (err_text or "").lower()
    return any(k in low for k in _PERM_KEYWORDS)


# ---------------------------------------------------------------------------
# Data collection functions (run in parallel on a thread pool)
# [Performance improvements] basic, which was previously called individually/resource/ram_bank information in one go
# PowerShell Integrated into process execution (reduces process creation costs).
# ---------------------------------------------------------------------------
def get_system_static_info():
    """System basic information + CPU/GPU Resource information + RAM View bank (slot) information at once"""
    info = {
        "power": "AC Power", "computer_name": socket.gethostname(),
        "cpu_name": platform.processor() or "Unknown",
        "cpu_cores": psutil.cpu_count(logical=False) or 0,
        "cpu_threads": psutil.cpu_count(logical=True) or 0,
        "gpus": [],
        "ram_bank": {"total_slots": 0, "populated": 0, "slots": [], "total_gb": 0.0},
    }
    try:
        info["boot_dt"] = datetime.fromtimestamp(psutil.boot_time())
    except Exception:
        info["boot_dt"] = None

    if not IS_WINDOWS:
        info["os"] = f"{platform.system()} {platform.release()}"
        info["manufacturer"] = "N/A"
        info["last_update"] = "N/A"
        return info

    ver = platform.win32_ver()
    build = ver[1] if len(ver) > 1 else ""

    raw = run_ps(
        "$k='HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion';"
        "$p=Get-ItemProperty $k -ErrorAction SilentlyContinue;"
        "$cs=Get-CimInstance Win32_ComputerSystem -ErrorAction SilentlyContinue;"
        "$hf=(Get-HotFix -ErrorAction SilentlyContinue | Sort-Object InstalledOn -Descending | Select-Object -First 1).InstalledOn;"
        "$hf_str=''; if ($hf) { try { $hf_str = (Get-Date $hf -Format 'yyyy-MM-dd') } catch { $hf_str = $hf -replace ' 00:00:00', '' } };"
        "$b=Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue | Select-Object -First 1;"
        "$bat_pct = if($b){$b.EstimatedChargeRemaining}else{-1};"
        "$cpu=(Get-CimInstance Win32_Processor -ErrorAction SilentlyContinue | Select-Object -First 1).Name;"
        # [correction] GPU Information inquiry - Correcting two problems in a server environment
        # (1) Win32_VideoController.AdapterRAMIt is a 32-bit (uint32) field, so it requires VRAM 4GB or more.
        #     Graphics_card_(server/(common on professional GPUs for workstations) the value is truncated to around 4GB.
        #     displayed incorrectly -> HardwareInformation.qwMemorySize (64-bit,
        #     Correct by matching the exact value) with PNPDeviceID.
        # (2) In some servers, Win32_VideoController may appear empty (Server Core, etc.),
        #     If empty, Win32_PnPSignedDriver(DeviceClass=DISPLAY)Fallback to .
        "$gpuRaw = Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue | Select-Object Name, AdapterRAM, PNPDeviceID;"
        "if (-not $gpuRaw) { $gpuRaw = Get-CimInstance Win32_PnPSignedDriver -ErrorAction SilentlyContinue | "
        "Where-Object { $_.DeviceClass -eq 'DISPLAY' } | "
        "Select-Object @{N='Name';E={$_.DeviceName}}, @{N='AdapterRAM';E={0}}, @{N='PNPDeviceID';E={$_.DeviceID}} };"
        "$gpu=@();"
        "foreach ($g in $gpuRaw) {"
        "  $vram=0; if ($g.AdapterRAM) { $vram=[int64]$g.AdapterRAM };"
        "  try {"
        "    if ($g.PNPDeviceID) {"
        "      $devKey=($g.PNPDeviceID -split '&')[0..1] -join '&';"
        "      $rk=Get-ItemProperty -Path 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Class\\{4d36e968-e325-11ce-bfc1-08002be10318}\\00*' -ErrorAction SilentlyContinue | "
        "      Where-Object { $_.MatchingDeviceId -and ($_.MatchingDeviceId -like ($devKey+'*')) } | Select-Object -First 1;"
        "      if ($rk) { $mp=$rk.PSObject.Properties['HardwareInformation.qwMemorySize']; if ($mp -and $mp.Value) { $vram=[int64]$mp.Value } }"
        "    }"
        "  } catch {};"
        "  $gpu += [PSCustomObject]@{Name=$g.Name; AdapterRAM=$vram};"
        "};"
        "$mem=Get-CimInstance Win32_PhysicalMemory -ErrorAction SilentlyContinue | Select-Object BankLabel, DeviceLocator, Capacity;"
        "$arr=Get-CimInstance Win32_PhysicalMemoryArray -ErrorAction SilentlyContinue | Select-Object -First 1 MemoryDevices;"
        "[PSCustomObject]@{ProductName=$p.ProductName; DisplayVersion=$p.DisplayVersion; ReleaseId=$p.ReleaseId; "
        "Manufacturer=$cs.Manufacturer; LastUpdate=$hf_str; BatPct=$bat_pct; Cpu=$cpu; Gpu=$gpu; Mem=$mem; "
        "TotalSlots=$arr.MemoryDevices} | ConvertTo-Json -Compress -Depth 4",
        timeout=10,
    )

    product_name = display_ver = manu = update = ""
    if raw:
        try:
            d = json.loads(raw)
            product_name = d.get("ProductName") or ""
            display_ver = d.get("DisplayVersion") or d.get("ReleaseId") or ""
            manu = d.get("Manufacturer") or ""
            update = d.get("LastUpdate") or ""

            bat_pct = d.get("BatPct", -1)
            if bat_pct != -1:
                info["power"] = f"Battery in use ({bat_pct}%)"
            else:
                info["power"] = "AC Power (always connected)"

            if d.get("Cpu"):
                info["cpu_name"] = d["Cpu"]

            gpus_all = []
            gpu_data = d.get("Gpu") or []
            if isinstance(gpu_data, dict): gpu_data = [gpu_data]
            for item in gpu_data:
                name = (item.get("Name") or "unknown").strip()
                ram_bytes = item.get("AdapterRAM") or 0
                vram_gb = ram_bytes / (1024 ** 3) if ram_bytes else 0
                gpus_all.append({"name": name, "vram_gb": vram_gb, "type": _classify_gpu(name),
                                  "is_rdp": _is_rdp_virtual_gpu(name)})

            real_gpus = [g for g in gpus_all if not g["is_rdp"]]
            if real_gpus:
                gpus = real_gpus
            elif gpus_all:
                gpus = gpus_all
                for g in gpus:
                    g["type"] = "Remote_session_(not_real_GPU)"
            else:
                gpus = []
            info["gpus"] = gpus

            # [correction] Changed the RAM information parsing stage to exclude the word 'bank' and collect only numbers.
            modules = d.get("Mem") or []
            if isinstance(modules, dict): modules = [modules]
            slots, total_gb = [], 0.0
            for i, m in enumerate(modules, 1):
                # Existing “bank{i}" Instead, insert only pure numeric number strings into the array.
                slots.append(str(i))
                cap = m.get("Capacity") or 0
                try: total_gb += int(cap) / (1024 ** 3)
                except Exception: pass
            total_slots = d.get("TotalSlots") or 0
            info["ram_bank"] = {
                "slots": slots, "populated": len(slots), "total_gb": total_gb,
                "total_slots": int(total_slots) if total_slots else max(len(slots), 0),
            }
        except Exception:
            pass

    # [addition] OS '64 by extracting architecture (number of bits) information-bit' processed into shape
    arch = platform.architecture() # ('64bit', 'WindowsPE') return form
    os_bit_text = f" ({arch[0].lower().replace('bit', '-bit')})" if arch and arch[0] else ""

    os_base = product_name if product_name else f"{platform.system()} {ver[0]}"
    
    # Connect os_bit_text so that it is naturally attached to the end with a parenthesis structure in accordance with the parent code structure.
    info["os"] = f"{os_base} {display_ver} (Build {build}){os_bit_text}" if display_ver else f"{os_base} (Build {build}){os_bit_text}"
    info["manufacturer"] = manu if manu else "Unable_to_verify"
    info["last_update"] = update if update else "Unable_to_verify"
    return info


def get_uptime_texts(boot_dt):
    uptime = datetime.now() - boot_dt
    days = uptime.days
    hours, rem = divmod(uptime.seconds, 3600)
    minutes = rem // 60
    uptime_text = f"{days}Day {hours}hour {minutes}minute"
    boot_text = boot_dt.strftime("%Y-%m-%d  %Hhours%Mminute")
    return uptime_text, boot_text


_IGPU_KEYWORDS = ["intel", "uhd", "iris", "hd graphics", "radeon(tm) graphics", "radeon graphics", "vega",
                  "radeon(tm) vega", "amd radeon(tm) graphics", "microsoft basic", "microsoft remote"]


def _classify_gpu(name: str) -> str:
    lname = name.lower()
    for kw in _IGPU_KEYWORDS:
        if kw in lname: return "On-board Graphics"
    if "nvidia" in lname or "geforce" in lname or "rtx" in lname or "gtx" in lname or "radeon rx" in lname or "radeon pro" in lname:
        return "External Graphics"
    return "Unknown"


# [addition] When viewed from a remote desktop (RDP) session, this virtual display adapter is used instead of the physical GPU.
# Sometimes it gets caught instead (a known behavior on Windows).Marked separately to avoid confusion with actual GPU.
_RDP_VIRTUAL_GPU_KEYWORDS = ["remote display adapter", "rdpdd", "remotefx"]

def _is_rdp_virtual_gpu(name: str) -> bool:
    lname = name.lower()
    return any(kw in lname for kw in _RDP_VIRTUAL_GPU_KEYWORDS)


def _parse_link_speed(speed_str):
    """Get-NetAdapterLinkSpeed ​​string (e.g.: '1 Gbps','100 Mbps')Convert to Mbps number"""
    if not speed_str: return 0.0
    m = re.match(r"([\d.]+)\s*([GMK]?)bps", str(speed_str).strip(), re.IGNORECASE)
    if not m: return 0.0
    val = float(m.group(1))
    unit = m.group(2).upper()
    mult = {"G": 1000.0, "M": 1.0, "K": 0.001}.get(unit, 0.000001)
    return val * mult


_NIC_STATUS_MAP = {
    "up": "Normal", "disconnected": "Failure (disconnection)", "down": "Failure",
    "disabled": "deactivated", "notpresent": "Not installed", "lowerlayerdown": "Failure",
}

def _nic_status_kr(raw_status):
    """Get-NetAdapterStatus value is normal/Failure_(disconnected)/deactivate/Converted to Korean status with details such as not installed.
    [correction] Normal in previous version/Restoring what had been simplified to level 2 to v7 level detail."""
    s = str(raw_status or "").strip().lower().replace(" ", "")
    return _NIC_STATUS_MAP.get(s, str(raw_status) if raw_status else "Unable_to_verify")


def get_network_info():
    """Network connection information + Operating status of each physical LAN card + NIC Check whether team (redundancy) is configured at once.
    [correction] PhysicalAdapter from legacy Win32_NetworkAdapter/Speed The field is NIC for some servers.
    (Broadcom, Intel
    There was.Get-NetAdapter(Accurately configure virtual adapters with the latest, highly reliable API and virtual properties
    distinction) first, and fall back to the legacy WMI method only when it fails or yields no results."""
    info = {"connection": "Unable to verify", "nic": "Unable to confirm", "link_speed_mbps": 0, "nics": [], "team": None}
    if not IS_WINDOWS: return info

    raw = run_ps(
        # 1) recent/Highly reliable method
        "$prim = Get-NetAdapter -ErrorAction SilentlyContinue | Where-Object { "
        "  $_.Status -eq 'Up' -and $_.Virtual -eq $false -and "
        "  $_.InterfaceDescription -notmatch 'Virtual|VMware|Hyper-V|VPN|Pseudo|TAP|Loopback|Microsoft-KM-TEST|Docker|vEthernet|VirtualBox|Hamachi|Tailscale' "
        "} | Select-Object Name, InterfaceDescription, @{N='SpeedStr';E={\"$($_.LinkSpeed)\"}}, MediaType;"
        # 2) fallback: Legacy WMI (excluding the PhysicalAdapter filter as it is unreliable)/Filter only connection status)
        "$fallback = $null;"
        "if (-not $prim) { $fallback = Get-CimInstance Win32_NetworkAdapter -ErrorAction SilentlyContinue | Where-Object { "
        "  $_.NetConnectionStatus -eq 2 -and "
        "  $_.Name -notmatch 'Virtual|VMware|Hyper-V|VPN|Pseudo|TAP|Loopback|Microsoft-KM-TEST|Docker|vEthernet|VirtualBox|Hamachi|Tailscale' "
        "} | Select-Object NetConnectionID, Name, Speed, AdapterType };"
        # 3) Operating status of each physical LAN card
        # [correction] -Physical In some server NIC drivers for switches, the result may appear empty.
        # Available (same cause as connection information inquiry), if empty, Virtual=$false Re-inquiry based on conditions.
        "$ad=Get-NetAdapter -Physical -ErrorAction SilentlyContinue | Select-Object Name, InterfaceDescription, Status;"
        "if (-not $ad) { $ad = Get-NetAdapter -ErrorAction SilentlyContinue | Where-Object { $_.Virtual -eq $false } | Select-Object Name, InterfaceDescription, Status };"
        # 4) Team_(redundant) - Old LBFO first, if not, SET (Server 2022+ Hyper-V Switch Embedded Team) Fallback
        "$tm=$null; try { $tm=Get-NetLbfoTeam -ErrorAction Stop | Select-Object Name, TeamMembers, Status } catch {};"
        "if (-not $tm) { try { $tm2=Get-VMSwitchTeam -ErrorAction Stop | Select-Object Name, NetAdapterInterfaceDescription; "
        "if ($tm2) { $tm = $tm2 | ForEach-Object { [PSCustomObject]@{Name=$_.Name; TeamMembers=$_.NetAdapterInterfaceDescription; Status='SET'} } } } catch {}};"
        "[PSCustomObject]@{Primary=$prim; Fallback=$fallback; Adapters=$ad; Teams=$tm} | ConvertTo-Json -Compress -Depth 4",
        timeout=12,
    )

    if raw:
        try:
            d = json.loads(raw)
            candidates = []

            primary = d.get("Primary")
            if primary:
                if isinstance(primary, dict): primary = [primary]
                for item in primary:
                    conn_id = (item.get("Name") or "").strip()
                    model_name = (item.get("InterfaceDescription") or conn_id or "Unable to verify").strip()
                    speed_mbps = _parse_link_speed(item.get("SpeedStr"))
                    media = str(item.get("MediaType") or "").lower()
                    is_wireless = ("802.11" in media or "wireless" in media or "wi-fi" in conn_id.lower() or "wlan" in conn_id.lower())
                    candidates.append({"name": model_name, "conn_id": conn_id or "-", "speed_mbps": speed_mbps, "is_wireless": is_wireless})

            if not candidates:
                fallback = d.get("Fallback")
                if fallback:
                    if isinstance(fallback, dict): fallback = [fallback]
                    for item in fallback:
                        conn_id = (item.get("NetConnectionID") or "").strip()
                        model_name = (item.get("Name") or conn_id or "Unable to verify").strip()
                        speed_mbps = (item.get("Speed") or 0) / 1_000_000
                        is_wireless = ("wireless" in str(item.get("AdapterType")).lower() or "wi-fi" in conn_id.lower() or "wlan" in conn_id.lower())
                        candidates.append({"name": model_name, "conn_id": conn_id or "-", "speed_mbps": speed_mbps, "is_wireless": is_wireless})

            if candidates:
                wired = [c for c in candidates if not c["is_wireless"]]
                nic = wired[0] if wired else candidates[0]
                info["connection"] = "wireless connection" if nic["is_wireless"] else "wired connection"
                info["nic"] = f'{nic["name"]} ({nic["conn_id"]})' if nic["conn_id"] not in ("-", nic["name"]) else nic["name"]
                info["link_speed_mbps"] = nic["speed_mbps"]

            ads = d.get("Adapters") or []
            if isinstance(ads, dict): ads = [ads]
            for a in ads:
                name = (a.get("InterfaceDescription") or a.get("Name") or "Unable to verify").strip()
                st_kr = _nic_status_kr(a.get("Status"))
                info["nics"].append({"name": name, "status": st_kr})

            teams = d.get("Teams")
            if teams:
                if isinstance(teams, dict): teams = [teams]
                t = teams[0]
                members = t.get("TeamMembers") or []
                if isinstance(members, str): members = [members]
                team_type = "SET(Hyper-V Switch Embedded Team)" if t.get("Status") == "SET" else t.get("Status", "Unable_to_confirm")
                info["team"] = f"{t.get('Name', 'team')} configured ({len(members)} nic, status:{team_type})"
        except Exception:
            pass
    return info


def get_ip_address():
    try: return socket.gethostbyname(socket.gethostname())
    except Exception: return "Unable_to_confirm"


def get_link_speed_tier(speed_mbps):
    if not speed_mbps or speed_mbps <= 0: return "Unable to confirm", "#999999"
    if speed_mbps >= 1000: return f"{speed_mbps / 1000:.0f} Gbps (Gigabit)", "#2ecc71"
    if speed_mbps >= 100: return f"{speed_mbps:.0f} Mbps (Fast Ethernet)", "#f1c40f"
    return f"{speed_mbps:.0f} Mbps (low speed)", "#e74c3c"


def get_disk_info():
    disks = []
    for part in psutil.disk_partitions(all=False):
        if IS_WINDOWS and ("cdrom" in part.opts or part.fstype == ""): continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append({"device": part.device, "total_gb": usage.total / (1024 ** 3), "used_gb": usage.used / (1024 ** 3),
                          "free_gb": usage.free / (1024 ** 3), "percent": usage.percent})
        except Exception: continue
    return disks


_EXTERNAL_BUS_TYPES = ("iscsi", "fibre channel", "fc", "sas", "usb")

# [addition] NAS/SMB/NFS Roughly estimate the storage vendor from a string included in the remote path or server name.
# This is not an exact equipment inquiry API, but a name-based estimate, so “(estimate)” is always indicated in the UI.
_VENDOR_KEYWORDS = (
    ("dellemc", "Dell EMC"), ("dell", "Dell"), ("emc", "Dell EMC"),
    ("netapp", "NetApp"), ("hpe", "HP/HPE"), ("hp", "HP/HPE"), ("ibm", "IBM"),
    ("synology", "Synology"), ("qnap", "QNAP"), ("purestorage", "Pure Storage"),
    ("nimble", "Nimble"), ("lenovo", "Lenovo"), ("huawei", "Huawei"),
    ("synologynas", "Synology"), ("truenas", "TrueNAS"), ("nutanix", "Nutanix"),
)


def _guess_storage_vendor(text):
    t = (text or "").lower()
    for kw, label in _VENDOR_KEYWORDS:
        if kw in t: return label
    return None


# [addition] Get-SmbMappingThe Status of ConvertTo is a uint32 enumeration of the MSFT_SmbMapping class.-Jsonby
# Serializing results in the original numeric code (0) rather than a display string (such as "OK").~6)But it comes out as is.
# (Value based on Microsoft official document: 0=OK, 1=Paused, 2=Disconnected, 3=NetworkError,
#  4=Connecting, 5=Reconnecting, 6=Unavailable)
_SMB_STATUS_MAP = {
    0: "OK", 1: "Paused", 2: "Disconnected",
    3: "NetworkError", 4: "Connecting",
    5: "Reconnecting", 6: "Unavailable, path/Cannot access server)",
}


def _describe_smb_status(raw):
    """SMB Mapping status code 'Code-Convert 'Description' to string.The code value for determining whether it is normal (0) is also returned."""
    raw_str = str(raw).strip()
    try:
        code = int(raw_str)
    except (TypeError, ValueError):
        return (raw_str or "Unable to verify"), None
    return f"{code}-{_SMB_STATUS_MAP.get(code, 'unknown_state')}", code


# [addition] Get-PhysicalDiskHealthStatus/OperationalStatus(Get-SmbMapping.Statusunlike)
# PowerShellThis itself makes the original numeric code "OK"/"Healthy"/"Degraded" in advance with the same English text.
# Since it is converted and returned (extended attribute of Microsoft's official storage module), only numbers appear.
# There is no problem.However, since it is in English, you may not understand the meaning right away, so I only add the Korean explanation next to it.
# (HealthStatus also processes numeric values ​​in official documents in case the numbers come down as is.)
_PHYSICALDISK_HEALTH_KR = {
    "healthy": "Normal", "warning": "warning", "unhealthy": "Abnormal", "unknown": "Unknown",
}
_PHYSICALDISK_HEALTH_CODE_MAP = {
    0: "Healthy", 1: "Warning", 2: "Unhealthy", 5: "Unknown",
}
_PHYSICALDISK_OPSTATUS_KR = {
    "ok": "normal", "other": "Other", "degraded": "Degraded performance", "stressed": "overload",
    "predictive failure": "Failure prediction, replacement recommendation", "error": "Error", "non-recoverable error": "Unrecoverable_error",
    "starting": "Starting", "stopping": "Stopping", "stopped": "stopped", "in service": "Inspection",
    "no contact": "No response", "lost communication": "Communication cut off", "aborted": "aborted",
    "dormant": "dormant", "completed": "Completed", "online": "online", "offline": "offline",
}


def _describe_physicaldisk_health(raw):
    raw_str = str(raw or "").strip()
    if not raw_str: return "-"
    try:
        code = int(raw_str)
    except (TypeError, ValueError):
        kr = _PHYSICALDISK_HEALTH_KR.get(raw_str.lower())
        return f"{raw_str}({kr})" if kr else raw_str
    return _PHYSICALDISK_HEALTH_CODE_MAP.get(code, f"{code}-unknown_code")


def _describe_physicaldisk_opstatus(raw):
    raw_str = str(raw or "").strip()
    if not raw_str: return "-"
    kr = _PHYSICALDISK_OPSTATUS_KR.get(raw_str.lower())
    return f"{raw_str}({kr})" if kr else raw_str


def get_storage_info():
    """Disk SMART/situation + Bus type (internal/external determination) + external(SAN) 원city disk list +
    Multipath (MPIO) connection status + internal disk read/Query write reliability counters at once.
    [correction] Check the bus type of the mounted drive as well. [interior]/[external] Used for distinction.
    [correction] External (SAN) raw disks are no longer filtered by whether they are mounted or not, but are all displayed.
    Mounted on each item/Contains the unmounted status (if mounted) along with the drive letter.
    [addition] dell/HP/IBM When enterprise storage is connected in multipath (MPIO) or LUN format,
    Windows MPIO Driver WMI (root\\wmi, MPIO_DISK_INFO)Serial number for each LUN (disk)
    Check the number of paths and Get-PhysicalDisk“Connected (N routes)” by matching the serial number of /
    ""Released" / "(On servers without the MPIO feature installed, this query is
    Since it will be empty, it will automatically be connected in the traditional way (simple connected)./(displayed)
    [addition] The internal disk is Get-StorageReliabilityCounter(Reads that the disk actually reports/write
    Error counters) are additionally queried to display more detailed operating status.
    [addition] Even servers without raw SAN LUNs can identify commodity storage attached at the file level (NAS).
    SMB mapping (Get-SmbMapping)and other network drives not captured by SMB (mainly NFS,
    Win32_LogicalDisk DriveType=4)together, and also the number of iSCSI initiator sessions."""
    info = {
        "external_storage": [], "disk_health": {}, "permission_warning": False,
        "smb_shares": [], "nfs_or_other_net": [], "iscsi_session_count": 0,
    }
    if not IS_WINDOWS: return info

    out, err = run_ps_detailed(
        "$ext = Get-PhysicalDisk -ErrorAction SilentlyContinue | "
        "Where-Object { $_.BusType -in @('iSCSI','Fibre Channel','FC','SAS','USB') } | "
        "Select-Object DeviceId, FriendlyName, BusType, Size, HealthStatus, OperationalStatus, SerialNumber;"
        "$dh = Get-Partition -ErrorAction SilentlyContinue | Where-Object { $_.DriveLetter } | "
        "Select-Object DriveLetter, DiskNumber, "
        "@{N='Health';E={(Get-Disk -Number $_.DiskNumber -ErrorAction SilentlyContinue).HealthStatus}}, "
        "@{N='BusType';E={(Get-Disk -Number $_.DiskNumber -ErrorAction SilentlyContinue).BusType}};"
        "$mp=@();"
        "try { $mraw = Get-CimInstance -Namespace root\\wmi -ClassName MPIO_DISK_INFO -ErrorAction SilentlyContinue;"
        "  foreach($m in $mraw){ foreach($dinfo in $m.DriveInfo){"
        "    $sn=''; try { $sn=([System.Text.Encoding]::ASCII.GetString($dinfo.SerialNumber)).Trim([char]0).Trim() } catch {};"
        "    $mp += [PSCustomObject]@{SerialNumber=$sn; NumberPaths=$dinfo.NumberPaths} } } "
        "} catch {};"
        "$rel = Get-PhysicalDisk -ErrorAction SilentlyContinue | Get-StorageReliabilityCounter -ErrorAction SilentlyContinue | "
        "Select-Object DeviceId, ReadErrorsTotal, WriteErrorsTotal;"
        "$smb=@(); try { $smb = Get-SmbMapping -ErrorAction SilentlyContinue | "
        "Select-Object LocalPath, RemotePath, Status } catch {};"
        "$netdrv=@(); try { $netdrv = Get-CimInstance -ClassName Win32_LogicalDisk -Filter 'DriveType=4' "
        "-ErrorAction SilentlyContinue | Select-Object DeviceID, ProviderName, VolumeName, FileSystem, Size } catch {};"
        "$iscsiCnt=0; try { $iscsiCnt = @(Get-IscsiSession -ErrorAction SilentlyContinue).Count } catch {};"
        "[PSCustomObject]@{ExternalDisks=$ext; DiskHealth=$dh; Mpio=$mp; Reliability=$rel; "
        "SmbMap=$smb; NetDrives=$netdrv; IscsiSessionCount=$iscsiCnt} | ConvertTo-Json -Compress -Depth 5",
        timeout=15,
    )

    if not out and _is_permission_error(err):
        info["permission_warning"] = True
        return info

    mounted_disk_numbers = set()
    disknum_to_letters = {}  # [addition] disk number -> List of mounted drive letters
    if out:
        try:
            d = json.loads(out)

            # [addition] read/Mapping write error counters based on disk number (DeviceId)
            rel_list = d.get("Reliability") or []
            if isinstance(rel_list, dict): rel_list = [rel_list]
            reliability_by_disknum = {}
            for r in rel_list:
                try: disknum = int(r.get("DeviceId"))
                except Exception: continue
                reliability_by_disknum[disknum] = {
                    "read_errors": r.get("ReadErrorsTotal"), "write_errors": r.get("WriteErrorsTotal"),
                }

            dh_list = d.get("DiskHealth") or []
            if isinstance(dh_list, dict): dh_list = [dh_list]
            for item in dh_list:
                dl = str(item.get("DriveLetter", "")).strip().upper()
                if not dl: continue
                h = str(item.get("Health") or "").strip().lower()
                h_kr = "OK" if h == "healthy" else "Warning" if h == "warning" else "Error" if h == "unhealthy" else (item.get("Health") or "Unable to verify")
                bus = str(item.get("BusType") or "").strip()

                # [addition] internal disk read/One-line determination of operating status based on write error counter
                disknum = None
                try: disknum = int(item.get("DiskNumber"))
                except Exception: pass
                rel = reliability_by_disknum.get(disknum) if disknum is not None else None
                read_err = rel.get("read_errors") if rel else None
                write_err = rel.get("write_errors") if rel else None
                if read_err is None and write_err is None:
                    io_status = "Unable to verify (authorized or unsupported controller)"
                elif (read_err or 0) > 0 or (write_err or 0) > 0:
                    io_status = f"Caution_(reading_error {read_err or 0}count, writing error {write_err or 0}count)"
                else:
                    io_status = "normal_(no read/ writing errors)"

                info["disk_health"][f"{dl}:\\"] = {
                    "health": h_kr, "bus_type": bus or "Unable to verify",
                    "is_external": bus.lower() in _EXTERNAL_BUS_TYPES,
                    "io_status": io_status,
                }
                try:
                    _dn = int(item.get("DiskNumber"))
                    mounted_disk_numbers.add(_dn)
                    disknum_to_letters.setdefault(_dn, []).append(f"{dl}:")
                except Exception: pass

            # [addition] MPIO Mapping the number of paths based on serial number (for enterprise storage LUN matching)
            mpio_list = d.get("Mpio") or []
            if isinstance(mpio_list, dict): mpio_list = [mpio_list]
            mpio_by_serial = {}
            for m in mpio_list:
                sn = str(m.get("SerialNumber") or "").strip()
                if sn: mpio_by_serial[sn] = m.get("NumberPaths")

            ext_list = d.get("ExternalDisks") or []
            if isinstance(ext_list, dict): ext_list = [ext_list]
            for item in ext_list:
                try: dev_num = int(item.get("DeviceId"))
                except Exception: dev_num = None
                # [correction] Mounted items are also displayed together without filtering them out, but the mount status/Contains drive letters separately
                is_mounted = dev_num is not None and dev_num in mounted_disk_numbers
                mount_letters = disknum_to_letters.get(dev_num, []) if dev_num is not None else []
                size_bytes = item.get("Size") or 0
                op_status = str(item.get("OperationalStatus") or "").strip()
                health_status = str(item.get("HealthStatus") or "").strip()
                serial = str(item.get("SerialNumber") or "").strip()
                paths = mpio_by_serial.get(serial)

                # [addition] dell/HP/IBM etc. Multipath (MPIO)/LUN Connection status determination
                # - MPIO If there is route information, it is based on the number of routes. If there is not (MPIO not installed), the existing
                #   OperationalStatus/HealthStatus Connected based on/cleared/Classification of disability issues
                if paths is not None:
                    if paths <= 0:
                        conn_state = "System Issue (no connected path)"
                    elif health_status and health_status.lower() not in ("healthy", "ok", ""):
                        conn_state = f"System Issue_({health_status}, channel {paths}dog)"
                    elif op_status and op_status.lower() not in ("ok", "online", "healthy"):
                        conn_state = f"System Issue_({op_status}, channel {paths}dog)"
                    elif paths == 1:
                        conn_state = "Connected (1 path, no redundancy configured)"
                    else:
                        conn_state = f"Connected_(path {paths})"
                else:
                    if op_status.lower() in ("offline",):
                        conn_state = "Released"
                    elif health_status and health_status.lower() not in ("healthy", "ok", ""):
                        conn_state = f"System Issue_({health_status})"
                    elif op_status and op_status.lower() not in ("ok", "online", "healthy", ""):
                        conn_state = f"System Issue_({op_status})"
                    else:
                        conn_state = "Connected"

                info["external_storage"].append({
                    "name": item.get("FriendlyName") or "Unable to verify", "bus_type": item.get("BusType") or "-",
                    "size_gb": (size_bytes / (1024 ** 3)) if size_bytes else 0,
                    "health": _describe_physicaldisk_health(health_status),
                    "status": _describe_physicaldisk_opstatus(op_status),
                    "conn_state": conn_state, "path_count": paths,
                    "is_mounted": is_mounted, "mount_letters": mount_letters,
                })

            # [addition] SMB mapped to/File server sharing list (Get-SmbMapping)
            smb_list = d.get("SmbMap") or []
            if isinstance(smb_list, dict): smb_list = [smb_list]
            smb_letters_seen = set()
            for s in smb_list:
                local = str(s.get("LocalPath") or "").strip().upper().rstrip("\\")
                remote = str(s.get("RemotePath") or "").strip()
                status_text, status_code = _describe_smb_status(s.get("Status"))
                if local: smb_letters_seen.add(local)
                info["smb_shares"].append({
                    "drive": local or "((no drive letter)", "remote": remote or "Unable to verify",
                    "status": status_text, "status_code": status_code,
                    "vendor_guess": _guess_storage_vendor(remote),
                })

            # [addition] SMBOther network drives not captured (mainly NFS client mounted)
            netdrv_list = d.get("NetDrives") or []
            if isinstance(netdrv_list, dict): netdrv_list = [netdrv_list]
            for nd in netdrv_list:
                dev = str(nd.get("DeviceID") or "").strip().upper().rstrip("\\")
                if dev and dev in smb_letters_seen:
                    continue  # Avoid duplication as it already appears in the SMB list
                remote = str(nd.get("ProviderName") or nd.get("VolumeName") or "").strip()
                size_b = nd.get("Size") or 0
                info["nfs_or_other_net"].append({
                    "drive": dev or "((no drive letter)", "remote": remote or "Unable to verify",
                    "filesystem": nd.get("FileSystem") or "Unable_to_verify",
                    "size_gb": (size_b / (1024 ** 3)) if size_b else 0,
                    "vendor_guess": _guess_storage_vendor(remote),
                })

            info["iscsi_session_count"] = d.get("IscsiSessionCount") or 0
        except Exception:
            pass
    return info
def calculate():
    """
    Calculates the result.
    [Seodam 147]
    """
    pass

def get_docker_guests():
    """Docker EngineWhen running, the current container (name/image/status) list.
    [addition] docker CLIIf it's not in your PATH or you can't connect to the daemon (permissions issues, etc.), just throw an exception:
    It swallows and quietly returns an empty list (even if the Docker Engine service itself is running
    If the current user does not have docker group permissions, CLI access may not be possible)."""
    if not IS_WINDOWS:
        return []
    try:
        proc = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}}\t{{.Image}}\t{{.Status}}"],
            capture_output=True, timeout=8,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        out = proc.stdout.decode("utf-8", errors="ignore").strip()
    except Exception:
        return []
    guests = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 3: continue
        guests.append({"name": parts[0], "image": parts[1], "state": parts[2]})
    return guests


def get_kubelet_extra_info():
    """kubelet(When the Kubernetes node agent is running, the list of pods per cluster
    kubectl/crictl Even if the settings are different and cannot be retrieved reliably, at least the information can be verified.
    This is for show purposes only.
    - kubelet version: Find the path to the executable file registered in the service and click '--version'Direct inquiry to
      (Cluster connection/Almost always viewable without setup)
    - number of containers: crictlThis is in your PATH and has a runtime-endpointis already set
      In the node, the number is searched, but if not, it is skipped without searching (for reference only)."""
    if not IS_WINDOWS:
        return {}
    out = run_ps(
        "$ver='';"
        "try {"
        "  $svcPath=(Get-CimInstance Win32_Service -Filter \"Name='kubelet'\" -ErrorAction Stop).PathName;"
        "  if ($svcPath) {"
        "    $exe=($svcPath -replace '^\"','' -split '\"')[0];"
        "    $ver = ((& $exe --version) 2>$null | Out-String);"
        "  }"
        "} catch {};"
        "$cnt=-1;"
        "try {"
        "  $co = & crictl ps -a -q 2>$null;"
        "  if ($LASTEXITCODE -eq 0 -and $co) { $cnt = ($co | Measure-Object -Line).Lines }"
        "} catch {};"
        "[PSCustomObject]@{Ver=$ver.Trim(); ContainerCount=$cnt} | ConvertTo-Json -Compress",
        timeout=8,
    )
    result = {"version": "", "container_count": None}
    if out:
        try:
            d = json.loads(out)
            result["version"] = (d.get("Ver") or "").strip()
            cnt = d.get("ContainerCount")
            if isinstance(cnt, int) and cnt >= 0:
                result["container_count"] = cnt
        except Exception:
            pass
    return result


def get_virt_and_services_info():
    """Hardware for virtualization determination/BIOS information + View the entire service list at once.
    [Performance improvements] Previously, virtualization detection and installed service list inquiry were performed separately.
    Get-Servicewas called (duplicate), but it is combined into one call and used for both functions together.
    [addition] Docker Engine Once the service is confirmed to be running, the current container (guest) list is also displayed.
    We search together (since it is a docker CLI call, it is processed within this function) - in a background thread
    It runs so the screen doesn't freeze)."""
    info = {"manu": "", "model": "", "bios_ver": "", "services": [], "docker_containers": [], "kubelet_extra": {}}
    if not IS_WINDOWS: return info
    raw = run_ps(
        "$cs=Get-CimInstance Win32_ComputerSystem -ErrorAction SilentlyContinue;"
        "$bios=(Get-CimInstance Win32_BIOS -ErrorAction SilentlyContinue).SMBIOSBIOSVersion;"
        "$svc=Get-Service -ErrorAction SilentlyContinue | Select-Object Name, DisplayName, Status;"
        "[PSCustomObject]@{Manufacturer=$cs.Manufacturer; Model=$cs.Model; Bios=$bios; Services=$svc} | ConvertTo-Json -Compress -Depth 4",
        timeout=10,
    )
    if raw:
        try:
            d = json.loads(raw)
            info["manu"] = (d.get("Manufacturer") or "").lower()
            info["model"] = (d.get("Model") or "").lower()
            info["bios_ver"] = (d.get("Bios") or "").lower()
            svc_list = d.get("Services") or []
            if isinstance(svc_list, dict): svc_list = [svc_list]
            st_map = {"Running": "Running", "Stopped": "Paused", "Paused": "Pause", 4: "Running", 1: "Stopped", 7: "Pause"}
            for s in svc_list:
                st = s.get("Status")
                info["services"].append({
                    "name": (s.get("Name") or "").lower(), "display": s.get("DisplayName") or s.get("Name") or "",
                    "status_kr": st_map.get(st, str(st) if st else "Unable to verify"),
                })
            # [addition] Docker Engine If the service is running, the current container (guest) list is also viewed.
            if any("docker" in s["name"] and s["status_kr"] == "Running" for s in info["services"]):
                info["docker_containers"] = get_docker_guests()
            # [addition] kubeletIf this is running (even if you can't get the pod list), the version/number of containers, etc.
            # Search even minimal information
            if any("kubelet" in s["name"] and s["status_kr"] == "Running" for s in info["services"]):
                info["kubelet_extra"] = get_kubelet_extra_info()
        except Exception:
            pass
    return info


# [addition] Get-VMEven though the State property of is a .NET enum (Microsoft.HyperV.PowerShell.VMState), in reality
# "Running" An environment where it is not the same string but a numeric code (“2”) has been confirmed.Get-SmbMapping
# Since the symptoms are the same, they are mapped to numerical values ​​based on official documents and converted into human-readable text.
# Change it.(Mapping focuses on frequently occurring states, the rest shows the original code as is)
_VM_STATE_MAP = {
    1: "Other", 2: "Running", 3: "Off", 4: "Stopping", 6: "Saved", 9: "Paused",
    10: "Starting", 11: "Reset", 32773: "Saving", 32776: "Pausing", 32777: "Resuming",
    32778: "RunningCritical", 32779: "OffCritical", 32780: "StoppingCritical",
    32781: "SavedCritical", 32782: "PausedCritical",
}


def _describe_vm_state(raw):
    raw_str = str(raw or "").strip()
    if not raw_str:
        return "Unable to verify"
    try:
        code = int(raw_str)
    except (TypeError, ValueError):
        return raw_str  # If it is already a string like “Running”, use it as is.
    return _VM_STATE_MAP.get(code, f"cord{code}")


def get_optional_features_info():
    """Hyper-V/WSL/Windows Containers Check the status of related functions (separate call as it is a slow lookup).
    [correction] Previously, Get-WindowsOptionalFeature(Mainly by checking only the API for the client OS.
    Hyper installed as Server Role-VThere was a problem with not being able to detect .
    vmms(Hyper-V Virtual machine management) uses the running status of the service as the most reliable signal,
    Get-WindowsFeature(API for servers) and Get-WindowsOptionalFeature(API for clients)
    Check with auxiliary signals.
    [addition] This server is Hyper-V When operating as a host, Get-VMTo list of guest virtual machines
    (name/situation/CPU utilization/allocated memory/Number_of_operation_days/(Virtual disk usage estimate) is also searched.
    Hyper-V PowerShell On servers without modules (management tools not installed, etc.), the list is quietly empty.
    It will be processed.
    [addition] Physical disk utilization inside the guest OS (e.g.: C: 23%)Without login credentials
    There is no way to look it up on the host (requires separate authentication, such as PowerShell Direct).Instead, to the guest
    An alternative to getting it right from the host without having to log in, the first virtual
    Disk_(VHD)/VHDX) The "actual file size" of the file / Approximate usage by viewing the “maximum size” ratio
    Use this as an estimate.However, this value is meaningful only for dynamically expanding disks (fixed
    Size disk is always 100%(close to meaningless), even if you delete the file from inside the guest
    TRIM/UNMAPThe VHD file size may not be reduced until this is actually reflected, so
    These are "estimates" and not real-time values."""
    info = {"permission_warning": False}
    if not IS_WINDOWS: return info
    out, err = run_ps_detailed(
        "$res=[ordered]@{};"
        "try { Import-Module ServerManager -ErrorAction Stop;"
        "  $res['HyperVServer']=\"$((Get-WindowsFeature -Name Hyper-V -ErrorAction SilentlyContinue).InstallState)\";"
        "  $res['ContainersServer']=\"$((Get-WindowsFeature -Name Containers -ErrorAction SilentlyContinue).InstallState)\";"
        "} catch {};"
        "$feats=@('Microsoft-Hyper-V-All','Microsoft-Windows-Subsystem-Linux','VirtualMachinePlatform','Containers');"
        "foreach($f in $feats){ $s=(Get-WindowsOptionalFeature -Online -FeatureName $f -ErrorAction SilentlyContinue).State; $res[$f]=\"$s\" };"
        "$res['vmms']=\"$((Get-Service -Name vmms -ErrorAction SilentlyContinue).Status)\";"
        # [addition] Hyper-V List of guest VMs if operating as a host + View representative virtual disk usage estimates
        "$vms=@(); try { Import-Module Hyper-V -ErrorAction Stop;"
        "  $vms = Get-VM -ErrorAction Stop | ForEach-Object {"
        "    $vm = $_; $diskPct = $null; $diskType = '';"
        "    try {"
        "      $hdd = Get-VMHardDiskDrive -VMName $vm.Name -ErrorAction Stop | Select-Object -First 1;"
        "      if ($hdd) {"
        "        $vhd = Get-VHD -Path $hdd.Path -ErrorAction Stop;"
        "        $diskType = \"$($vhd.VhdType)\";"
        "        if ($vhd.VhdType -eq 'Dynamic' -and $vhd.Size -gt 0) {"
        "          $diskPct = [math]::Round(($vhd.FileSize / $vhd.Size) * 100, 2)"
        "        }"
        "      }"
        "    } catch {};"
        "    [PSCustomObject]@{"
        "      Name=$vm.Name; State=$vm.State; CPUUsage=$vm.CPUUsage; MemoryAssigned=$vm.MemoryAssigned;"
        "      UptimeStr=$(if($vm.Uptime){ '{0}d' -f $vm.Uptime.Days } else { '' });"
        "      DiskPct=$diskPct; DiskType=$diskType"
        "    }"
        "  }"
        "} catch {};"
        "$res['Vms']=$vms;"
        "[PSCustomObject]$res | ConvertTo-Json -Compress -Depth 4",
        timeout=35,
    )
    if not out and _is_permission_error(err):
        info["permission_warning"] = True
        return info
    if out:
        try:
            d = json.loads(out)
            info["hyperv_server_state"] = str(d.get("HyperVServer") or "").lower()
            info["containers_server_state"] = str(d.get("ContainersServer") or "").lower()
            info["hyperv_client_state"] = str(d.get("Microsoft-Hyper-V-All") or "").lower()
            info["wsl_state"] = str(d.get("Microsoft-Windows-Subsystem-Linux") or "").lower()
            info["vmp_state"] = str(d.get("VirtualMachinePlatform") or "").lower()
            info["containers_client_state"] = str(d.get("Containers") or "").lower()
            info["vmms_status"] = str(d.get("vmms") or "").lower()

            # [addition] Parsing the guest virtual machine list
            vms_raw = d.get("Vms") or []
            if isinstance(vms_raw, dict): vms_raw = [vms_raw]
            guests = []
            for v in vms_raw:
                mem_bytes = v.get("MemoryAssigned") or 0
                guests.append({
                    "name": v.get("Name") or "Unable to verify",
                    "state": _describe_vm_state(v.get("State")),
                    "cpu_pct": v.get("CPUUsage"),
                    "mem_gb": (mem_bytes / (1024 ** 3)) if mem_bytes else 0,
                    "uptime": v.get("UptimeStr") or "",
                    "disk_pct": v.get("DiskPct"),
                    "disk_type": v.get("DiskType") or "",
                })
            info["hyperv_vms"] = guests
        except Exception:
            pass
    return info


def classify_virtualization(hw_svc_info, feat_info):
    """service based + hardware based + Windows function/Comprehensive service-based virtualization detection results"""
    detected_list = []
    services = hw_svc_info.get("services", [])
    running_map = {s["name"]: s["status_kr"] for s in services if s.get("name")}

    def _svc_status(keyword):
        for name, st in running_map.items():
            if keyword in name: return st
        return None

    # Service-based detection - Actual service status (running/stopped) is reflected as is.
    # [addition] vCenter Server(Windows Installed type) is also detected by the existence of a service.vCenter is this server
    # Rather than running the guest on its own, it remotely connects separate ESXi hosts./With certified API
    # It’s a management structure, Hyper-V/DockerYou can't just get the guest list locally like
    # It only shows whether it is in operation or not.(vpxd = VMware VirtualCenter Server the actual service name of the service;
    # Windows Installation_type/Appliance Commonly Used Name)
    for keyword, label in [("kubelet", "Kubernetes (K8s)"), ("docker", "Docker Engine"),
                            ("citrix", "Citrix Hypervisor"), ("vpxd", "vCenter Server (Windows)")]:
        st = _svc_status(keyword)
        if st:
            entry = {"name": label, "status": st}
            # [addition] Docker EngineIf it is running, it also displays a list of current containers (guests)
            if label == "Docker Engine":
                entry["guests"] = hw_svc_info.get("docker_containers") or []
            # [addition] KubernetesEven if you can't reliably get the pod list (per cluster)
            # kubectl/crictl settings are different), kubelet version/You can check the number of containers, etc.
            # Display at least minimal information (Citrix is ​​not a XenServer host, but rather a
            # Excluded because installed Citrix-related services were detected and there was no target information)
            if label == "Kubernetes (K8s)":
                entry["extra_info"] = hw_svc_info.get("kubelet_extra") or {}
            detected_list.append(entry)

    manu, model, bios_ver = hw_svc_info.get("manu", ""), hw_svc_info.get("model", ""), hw_svc_info.get("bios_ver", "")

    # hardware/Manufacturer-based detection - Like a service, it cannot be confirmed whether it is running, so it is marked as “detected”
    if "nutanix" in manu or "nutanix" in model: detected_list.append({"name": "Nutanix (AHV)", "status": "Detected"})
    if "proxmox" in manu or "proxmox" in model: detected_list.append({"name": "Proxmox VE", "status": "Detected"})

    # VMware: BIOS ESXi (host) and Workstation as version strings/Fusion(desktop guest)
    # caution: 100% This is not a definitive distinction, but a heuristic determination that may vary depending on the type of VMware deployment.
    if "vmware" in manu or "vmware" in model:
        if bios_ver.startswith("vmw"):
            detected_list.append({"name": "VMware ESXi (guest)", "status": "Detected"})
        else:
            detected_list.append({"name": "VMware Workstation/Fusion (guest)", "status": "Detected"})

    if "virtualbox" in manu or "virtualbox" in model: detected_list.append({"name": "Oracle VirtualBox (guest)", "status": "Detected"})
    if "xen" in manu: detected_list.append({"name": "Xen (guest)", "status": "Detected"})
    if "microsoft" in manu and "virtual machine" in model: detected_list.append({"name": "Azure/Hyper-V VM (guest)", "status": "Detected"})

    # public cloud / KVM Guest detection
    if "amazon" in manu or "ec2" in model: detected_list.append({"name": "AWS EC2 (guest)", "status": "Detected"})
    if "google" in manu or "google compute engine" in model: detected_list.append({"name": "Google Compute Engine (guest)", "status": "Detected"})
    if "qemu" in manu or "kvm" in model or "red hat" in manu: detected_list.append({"name": "KVM/QEMU (guest)", "status": "Detected"})
    if "parallels" in manu: detected_list.append({"name": "Parallels (guest)", "status": "Detected"})

    # [correction] Hyper-V / container / WSL: vmms Uses whether a service is running as a priority signal
    if feat_info.get("permission_warning"):
        detected_list.append({"name": "Virtualization function (Hyper-V etc) OK", "status": "Insufficient privileges (administrator privileges required)"})
    else:
        vmms_status = feat_info.get("vmms_status", "")
        hv_server_state = feat_info.get("hyperv_server_state", "")
        hv_client_state = feat_info.get("hyperv_client_state", "")
        if vmms_status == "running":
            # [addition] Hyper-V If operating as a host, a list of guest virtual machines is also displayed.
            detected_list.append({"name": "Hyper-V", "status": "Running", "guests": feat_info.get("hyperv_vms") or []})
        elif hv_server_state == "installed" or "enabled" in hv_client_state:
            detected_list.append({"name": "Hyper-V", "status": "Installed (Service Stopped)"})

        containers_server_state = feat_info.get("containers_server_state", "")
        containers_client_state = feat_info.get("containers_client_state", "")
        if "enabled" in containers_client_state or containers_server_state == "installed":
            detected_list.append({"name": "Windows Containers", "status": "Running"})

        wsl_on = "enabled" in feat_info.get("wsl_state", "")
        vmp_on = "enabled" in feat_info.get("vmp_state", "")
        if wsl_on:
            # WSL2To operate, the VirtualMachinePlatform function must be turned on (distribution-specific version needs to be checked separately)
            detected_list.append({"name": "WSL2" if vmp_on else "WSL1", "status": "Running"})

    return detected_list


_SERVICE_CATEGORY_KEYWORDS = {
    "DB and management": ["sql server", "mysql", "postgresql", "mariadb", "mongodb", "oracle", "redis", "mssql", "sqlite"],
    "Web_service": ["world wide web", "iis", "apache", "tomcat", "nginx", "node.js", "nodejs", "pm2", "php"],
    "Backup": ["veeam", "backup exec", "acronis", "netbackup", "windows server backup", "wbengine", "commvault"],
    "Log_backup": ["splunk", "graylog", "nxlog", "winlogbeat", "logstash", "filebeat", "syslog"],
    "development / build / management": ["docker", "jenkins", "gitlab", "iis express", "sonarqube", "nexus", "artifactory", "rabbitmq", "elasticsearch", "kafka", "zookeeper", "teamcity", "github-runner", "azure-pipelines", "bamboo"],
}


def classify_installed_services(hw_svc_info):
    """Sort services by category in the entire service list (get_virt_and_services_info results)"""
    results = []
    seen = set()
    for s in hw_svc_info.get("services", []):
        disp = s.get("display") or s.get("name") or ""
        low = disp.lower()
        for cat, kws in _SERVICE_CATEGORY_KEYWORDS.items():
            if any(kw in low for kw in kws):
                if (cat, disp) not in seen:
                    seen.add((cat, disp))
                    results.append({"category": cat, "name": disp, "status": s.get("status_kr", "Unable to verify")})
                break
    return results


def get_system_log(max_items=3):
    """latest error/Alert event query.
    [correction] The existing pywin32 (win32evtlog.ReadEventLog) method works on some servers.
    "(6, 'ReadEventLog', 'An error occurred: 'The handle is invalid.')".
    PowerShell Get-WinEvent(Replaced with the latest Windows event log API-based (more stable) method,
    Now you don't need pywin32 installation.
    [correction] LevelDisplayName("Error"/"Warning") Instead of a string, it is always the same regardless of the OS language.
    Level property with numeric value (2=error, 3=warning - Windows to filter by event log standard values)
    change.LevelDisplayName can be a localized string depending on the OS display language (e.g.: English
    "Error" in Windows/"Warning"may be displayed differently), so that it operates regardless of language.
    This is to do so."""
    result = {"Application": [], "System": []}
    if not IS_WINDOWS: return result

    raw = run_ps(
        "$logs=@('Application','System');"
        "$out = foreach ($ln in $logs) {"
        "  $ev = Get-WinEvent -LogName $ln -MaxEvents 80 -ErrorAction SilentlyContinue | "
        "        Where-Object { $_.Level -in @(2,3) } | "
        "        Select-Object -First 3 Level, ProviderName, Id;"
        "  [PSCustomObject]@{LogName=$ln; Events=$ev}"
        "};"
        "$out | ConvertTo-Json -Compress -Depth 4",
        timeout=12,
    )
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, dict): data = [data]
            for entry in data:
                log_name = entry.get("LogName")
                if log_name not in result: continue
                events = entry.get("Events") or []
                if isinstance(events, dict): events = [events]
                items = []
                for ev in events[:max_items]:
                    # [correction] Level 2=error, 3=Warning (Windows event log standard, regardless of OS language)
                    try: level = int(ev.get("Level"))
                    except (TypeError, ValueError): level = None
                    tag = "Danger" if level == 2 else "Warning" if level == 3 else None
                    if not tag: continue
                    provider = ev.get("ProviderName") or "Unable to verify"
                    eid = ev.get("Id")
                    items.append(f"[{tag}] text:{provider} (ID:{eid})")
                result[log_name] = items if items else ["recent risk/No warning items"]
        except Exception:
            result["Application"] = result["System"] = ["Failed to retrieve logs (PowerShell result parsing error)"]
    else:
        result["Application"] = result["System"] = ["Failed to retrieve logs (PowerShell execution failure or timeout)"]
    return result


# ---------------------------------------------------------------------------
# UI widget
# ---------------------------------------------------------------------------
class PercentBar(tk.Canvas):
    def __init__(self, parent, width=340, height=22, color=COLOR_CPU_BAR, **kw):
        super().__init__(parent, width=width, height=height, bg=COLOR_BAR_BG,
                          highlightthickness=1, highlightbackground="#999999", **kw)
        self.width, self.height, self.color = width, height, color
        self._percent, self._label_text = 0, ""
        self.bind("<Configure>", self._on_resize)

    def _on_resize(self, event):
        if event.width > 1: self.width = event.width
        if event.height > 1: self.height = event.height
        self._redraw()

    def set_value(self, percent, label_text):
        self._percent, self._label_text = max(0, min(100, percent)), label_text
        self._redraw()

    def _redraw(self):
        self.delete("all")
        fill_w = int(self.width * self._percent / 100)
        if fill_w > 0: self.create_rectangle(0, 0, fill_w, self.height, fill=self.color, width=0)
        font_size = 9 if self.height >= 16 else 7
        self.create_text(8, self.height / 2, anchor="w", text=self._label_text, font=("Clear Gothic", font_size, "bold"), fill="#111111")


class SpeedDot(tk.Canvas):
    def __init__(self, parent, size=14, **kw):
        super().__init__(parent, width=size, height=size, bg=COLOR_BG, highlightthickness=0, **kw)
        self.size = size

    def set_color(self, color):
        self.delete("all")
        pad = 1
        self.create_oval(pad, pad, self.size - pad, self.size - pad, fill=color, outline="#666666")


class ExpandableValue(tk.Frame):
    """Read-only value display widget.
    [addition] If the value is longer than the box width, it will automatically display up to 2 lines.
    Click to expand and show the entire contents, and click again to display the original size (1~2fold it into a line.
    (full grid/The panel layout structure remains the same, only the vertical scroll area is increased)"""
    COLLAPSED_MAX_LINES = 2
    EXPANDED_MAX_LINES = 10

    def __init__(self, parent, font=("Clear Gothic", 9), fg=COLOR_VALUE, bg=COLOR_BG, justify="left"):
        super().__init__(parent, bg=bg)
        self._expanded = False
        self._full_text = ""
        self.text = tk.Text(self, font=font, fg=fg, bg=bg, relief="flat", bd=0,
                             wrap="word", height=1, width=1, padx=0, pady=0,
                             highlightthickness=0, cursor="xterm", takefocus=0)
        self.text.pack(fill="x", expand=True)
        self.text.tag_config("val", justify=justify)
        self.text.config(state="disabled")
        # With per-instance binding (which takes precedence over class default binding)
        # Make sure that the outer dashboard canvas always scrolls, rather than scrolling inside this small Text widget.
        # [correction] In_the_past <Button-1>Intercept and unfold as is/I just folded it (a problem occurred where I couldn't drag to select it),
        # Now, when you press it, you leave the default Text behavior (drag selection), and when you release it, you actually drag it.
        # Make sure you have text selected - If it is a drag selection, leave it as is (copy possible), if it is a simple click, expand it./fold run
        self.text.bind("<ButtonRelease-1>", self._on_release)
        self.text.bind("<MouseWheel>", self._on_mousewheel_redirect)

    def _on_release(self, event):
        try:
            has_selection = bool(self.text.tag_ranges("sel"))
        except Exception:
            has_selection = False
        if not has_selection:
            self._toggle()

    def _toggle(self, event=None):
        self._expanded = not self._expanded
        self._resize()

    def _on_mousewheel_redirect(self, event):
        root = self.winfo_toplevel()
        canvas = getattr(root, "canvas", None)
        if canvas is not None:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            # [addition] Forces the scrollbar thumb to resynchronize its position so that it is immediately visible to wheel movement.
            vscroll = getattr(root, "vscroll", None)
            if vscroll is not None:
                vscroll.set(*canvas.yview())
            canvas.update_idletasks()
        return "break"

    def set_value(self, value):
        self._full_text = "-" if value in (None, "") else str(value)
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", self._full_text, "val")
        self.text.config(state="disabled")
        self.after_idle(self._resize)

    def _resize(self):
        try:
            self.text.update_idletasks()
            res = self.text.count("1.0", "end", "displaylines")
            if isinstance(res, tuple): total_lines = res[0] if res else 1
            elif res is None: total_lines = 1
            else: total_lines = int(res)
        except Exception:
            total_lines = 1
        cap = self.EXPANDED_MAX_LINES if self._expanded else self.COLLAPSED_MAX_LINES
        self.text.config(height=max(1, min(total_lines, cap)))


# ---------------------------------------------------------------------------
# main application
# ---------------------------------------------------------------------------
class SystemCheckApp(tk.Tk):
    CPU_AVG_WINDOW_SEC = 180
    FAST_REFRESH_MS = 2000

    def __init__(self):
        super().__init__()
        self.title("System Check Tool")
        self.geometry("980x1080")
        self.minsize(760, 720)
        self.configure(bg=COLOR_BG)
        self.resizable(True, True)

        self._cpu_samples = deque(maxlen=self.CPU_AVG_WINDOW_SEC)
        self._ram_samples = deque(maxlen=self.CPU_AVG_WINDOW_SEC)
        self._sample_lock = threading.Lock()

        threading.Thread(target=self._cpu_sampler_loop, daemon=True).start()

        self._slow_cache = None
        self._loaded_slow = False
        self._loaded_fast = False
        self._marked_ready = False
        self._net_last_io = None
        self._net_last_time = None
        # [addition] When updating in real time (2 seconds), if the disk bar is erased and redrawn every time, the screen blinks and
        # The scroll position is also disturbed, and the disk configuration (number of/If the order is the same, only the value of the existing widget
        # Cache for updates.(Redraw only when the configuration itself changes)
        self._disk_row_widgets = {}
        self._disk_row_order = []
        self._disk_issue_prev = None
        self._manual_refresh_running = False

        self._build_ui()

        # [addition] Mouse wheel scrolling is captured throughout the app to always scroll the main dashboard canvas
        self.bind_all("<MouseWheel>", self._on_mousewheel)

        threading.Thread(target=self._slow_loop, daemon=True).start()
        self._fast_tick()

    def _on_mousewheel(self, event):
        if hasattr(self, "canvas"):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            # [addition] Forces the scrollbar thumb to resynchronize its position so that it is immediately visible to wheel movement.
            if hasattr(self, "vscroll"):
                self.vscroll.set(*self.canvas.yview())
            self.canvas.update_idletasks()

    def _build_ui(self):
        # [addition] Apply custom styles to make scrollbars visually appealing
        # (vista/winnative Since the theme is native rendering, coloring is ignored, so switch to the clam theme)
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Vertical.TScrollbar",
            background=COLOR_BUTTON,      # Thumb (drag bar) color
            troughcolor="#e0e0e0",        # Track (background) color - Contrast with white background
            bordercolor="#e0e0e0",
            arrowcolor="#ffffff",
            gripcount=0,
            relief="flat",
            width=14)                     # Thickness (thicker than default)
        style.map("Vertical.TScrollbar",
            background=[("active", COLOR_BUTTON_ACTIVE)])

        title_frame = tk.Frame(self, bg=COLOR_BG)
        title_frame.pack(fill="x", padx=20, pady=(15, 10))
        tk.Label(title_frame, text="System check tool", font=("Clear Gothic", 16, "bold"), bg=COLOR_BG, fg=COLOR_TITLE).pack(side="left")
        # [addition] refresh button - Click to renew immediately without waiting for the next automatic renewal
        # Changed the method to include the Korean word “Refresh” in two lines inside the square button (the size remains compact, similar to the previous version).
                # 1. Create a blank image (for precise size control)
        self.pixel_img = tk.PhotoImage(width=1, height=1)

        # 2. Create an arrow-only button without borders and backgrounds
        self.refresh_btn = tk.Button(
            title_frame, 
            text="⟳",                  
            command=self._on_refresh_clicked,
            
            relief="flat",             
            bd=0,                      
            bg=title_frame["bg"],      # The button background is transparent to match the title bar background.
            
            # [correction] Set the usual arrow color to the existing square box color (COLOR_BUTTON)
            fg=COLOR_BUTTON,           
            
            # Color response when clicked
            activebackground=title_frame["bg"], 
            activeforeground=COLOR_BUTTON_ACTIVE, 
            
            font=("Arial", 17, "bold"), 
            image=self.pixel_img,
            compound="center",        
            width=25,                  
            height=25,                 
            justify="center", 
            cursor="hand2"
        )
        self.refresh_btn.pack(side="left", padx=(5, 3), pady=(4, 0), anchor="c")
        self.status_label = tk.Label(title_frame, text="Loading information...", font=("Clear Gothic", 10), bg=COLOR_BG, fg=COLOR_BUTTON)
        self.status_label.pack(side="left", padx=(0, 0), pady=(4, 0))
        # [correction] Apply version and copyright indication together
        tk.Label(title_frame, text=f"v{VERSION} I made it! © 2026 seodam147",
                 font=("Clear Gothic", 9), bg=COLOR_BG, fg="gray").pack(side="right", padx=15)

        outer = tk.Frame(self, bg=COLOR_BG, highlightthickness=2, highlightbackground=COLOR_BORDER)
        outer.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        content = tk.Frame(outer, bg=COLOR_BG)
        content.pack(fill="both", expand=True, padx=15, pady=15)

        # [addition] Allows scrolling with the mouse wheel if the content is longer than the window height
        # canvas + Scrollbar configuration.The actual panels are placed in a grid frame within this canvas.
        # [correction] The scroll bar's own shape is not exposed on the screen (pack is omitted), and only the wheel scroll function is maintained.
        self.canvas = tk.Canvas(content, bg=COLOR_BG, highlightthickness=0)
        vscroll = ttk.Scrollbar(content, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vscroll.set)
        self.vscroll = vscroll  # [addition] Reference retention to force synchronization of scrollbar positions when mouse wheel scrolls
        # vscroll.pack(side="right", fill="y")  # [correction] Hide scrollbar appearance - Scroll function continues to operate as yview_scroll
        self.canvas.pack(side="left", fill="both", expand=True)

        grid = tk.Frame(self.canvas, bg=COLOR_BG)
        self._grid_window = self.canvas.create_window((0, 0), window=grid, anchor="nw")

        def _on_grid_configure(event):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        grid.bind("<Configure>", _on_grid_configure)

        def _on_canvas_configure(event):
            self.canvas.itemconfig(self._grid_window, width=event.width)
        self.canvas.bind("<Configure>", _on_canvas_configure)

        self.panel_basic = self._make_panel(grid, "System basic information", 0, 0)
        self.panel_resource = self._make_panel(grid, "Resource usage", 0, 1)
        self.panel_network = self._make_panel(grid, "Network", 1, 0)
        self.panel_disk = self._make_panel(grid, "Disks and Storage", 1, 1)
        self.panel_virt = self._make_panel(grid, "Virtualization and Services", 2, 0)
        self.panel_log = self._make_panel(grid, "System log", 2, 1, header_button=("Open Event Viewer", self.open_event_viewer))

        grid.grid_columnconfigure(0, weight=1, uniform="col")
        grid.grid_columnconfigure(1, weight=1, uniform="col")
        for i in range(3): grid.grid_rowconfigure(i, weight=1)

        self._build_basic_panel()
        self._build_resource_panel()
        self._build_network_panel()
        self._build_disk_panel()
        self._build_virt_panel()
        self._build_log_panel()

        bottom_bar = tk.Frame(self, bg=COLOR_BG, height=50)
        bottom_bar.pack(fill="x", pady=(0, 20))
        bottom_bar.pack_propagate(False)

        # [addition] Bottom left guidance button (fixed to the left, unrelated to other buttons)
        self._make_button(bottom_bar, "Raedme", self.open_readme, width=10).place(x=24, rely=0.5, anchor="w")

        # Management_tools/Save_picture/The exit button is fixed exactly in the center of the entire bottom_bar.
        btn_inner = tk.Frame(bottom_bar, bg=COLOR_BG)
        btn_inner.place(relx=0.5, rely=0.5, anchor="center")
        self._make_button(btn_inner, "Administrative", self.open_admin_tools).pack(side="left", padx=24)
        self._make_button(btn_inner, "Save image file", self.save_as_image).pack(side="left", padx=24)
        self._make_button(btn_inner, "End", self.destroy).pack(side="left", padx=24)

    def _make_panel(self, parent, title, row, col, header_button=None):
        frame = tk.Frame(parent, bg=COLOR_BG, highlightthickness=1, highlightbackground=COLOR_BORDER)
        frame.grid(row=row, column=col, sticky="nsew", padx=8, pady=8)
        header = tk.Frame(frame, bg=COLOR_BG)
        header.pack(fill="x", padx=15, pady=(12, 8))
        tk.Label(header, text=title, font=("Clear Gothic", 11, "bold"), bg=COLOR_BG, fg=COLOR_SECTION_TITLE).pack(side="left")
        if header_button:
            tk.Button(header, text=header_button[0], command=header_button[1], bg=COLOR_BUTTON, fg=COLOR_BUTTON_TEXT,
                      font=("Clear Gothic", 8, "bold"), relief="raised", bd=2, activebackground=COLOR_BUTTON_ACTIVE,
                      activeforeground=COLOR_BUTTON_TEXT, padx=6, pady=1, cursor="hand2").pack(side="right")
        body = tk.Frame(frame, bg=COLOR_BG)
        body.pack(fill="both", expand=True, padx=15, pady=(0, 12))
        return body

    def _make_button(self, parent, text, command, width=14):
        return tk.Button(parent, text=text, command=command, bg=COLOR_BUTTON, fg=COLOR_BUTTON_TEXT, font=("Clear Gothic", 9, "bold"),
                          relief="raised", bd=3, activebackground=COLOR_BUTTON_ACTIVE, activeforeground=COLOR_BUTTON_TEXT,
                          width=width, pady=4, cursor="hand2")

    def _add_row(self, parent, label, value, pady=3, label_width=15, label_padx=(0, 10)):
        row = tk.Frame(parent, bg=COLOR_BG)
        row.pack(fill="x", pady=pady)
        tk.Label(row, text=label, width=label_width, anchor="w", font=("Clear Gothic", 9),
                 bg=COLOR_BG, fg=COLOR_LABEL).pack(side="left", padx=label_padx)
        val = ExpandableValue(row, font=("Clear Gothic", 9, "bold"), fg=COLOR_VALUE)
        val.pack(side="left", fill="x", expand=True)
        val.set_value(value)
        return val

    @staticmethod
    def _set_row(widget, text):
        widget.set_value(text)

    def _build_basic_panel(self):
        p = self.panel_basic
        # pady Modify the value from 5 to 1
        self.v_computer = self._add_row(p, "Computer name", "-", pady=1)
        self.v_os = self._add_row(p, "Operating system", "-", pady=1)
        self.v_uptime = self._add_row(p, "Usage time", "-", pady=1)
        self.v_boot = self._add_row(p, "Boot time", "-", pady=1)
        self.v_update = self._add_row(p, "Recent updates", "-", pady=1)
        self.v_manu = self._add_row(p, "Manufacturer", "-", pady=1)
        self.v_power = self._add_row(p, "PowerSource", "-", pady=1)
        self.v_ram_bank = self._add_row(p, "Memory", "-", pady=1)

    def _build_resource_panel(self):
        p = self.panel_resource
        self.bar_cpu = PercentBar(p, color=COLOR_CPU_BAR)
        self.bar_cpu.pack(fill="x", pady=(0, 2))  # Reduce top graph gap
        self.bar_ram = PercentBar(p, color=COLOR_RAM_BAR)
        self.bar_ram.pack(fill="x", pady=(0, 4))

        # pady=1 addition
        self.v_cpu_name = self._add_row(p, "CPU Model", "-", pady=1, label_width=12, label_padx=(0, 5))
        self.v_cpu_cores = self._add_row(p, "CPU Topology", "-", pady=1, label_width=12, label_padx=(0, 5))
        self.v_cpu_usage = self._add_row(p, "CPU Usage", "-", pady=1, label_width=12, label_padx=(0, 5))
        self.v_ram_detail = self._add_row(p, "Memory", "-", pady=1, label_width=12, label_padx=(0, 5))

        self.gpu_container = tk.Frame(p, bg=COLOR_BG)
        self.gpu_container.pack(fill="x", pady=(1, 0))

    def _build_network_panel(self):
        p = self.panel_network
        self.v_ip = self._add_row(p, "I P address", "-", pady=1)
        self.v_conn = self._add_row(p, "Connection", "-", pady=1)
        self.v_nic = self._add_row(p, "NIC Model", "-", pady=1)
        self.v_speed = self._add_row(p, "Average speed", "-", pady=1)
        row = tk.Frame(p, bg=COLOR_BG)
        row.pack(fill="x", pady=1)
        tk.Label(row, text="LAN port status", width=15, anchor="w", font=("Clear Gothic", 9), bg=COLOR_BG, fg=COLOR_LABEL).pack(side="left", padx=(0, 10))
        self.link_dot = SpeedDot(row)
        self.link_dot.pack(side="left", padx=(0, 6))
        self.v_link_speed = ExpandableValue(row, font=("Clear Gothic", 9, "bold"), fg=COLOR_VALUE)
        self.v_link_speed.pack(side="left", fill="x", expand=True)
        self.v_link_speed.set_value("-")

        # [addition] List of operating status for each physical LAN card
        tk.Label(p, text="NIC status", font=("Clear Gothic", 9, "bold"), bg=COLOR_BG, fg=COLOR_LABEL, anchor="w").pack(fill="x", pady=(6, 0))
        self.nic_status_container = tk.Frame(p, bg=COLOR_BG)
        self.nic_status_container.pack(fill="x", pady=(1, 0))

        # [addition] Redundancy (NIC Team) Configuration Information - Show only when detected
        self.v_nic_team = tk.Label(p, text="", font=("Clear Gothic", 9), bg=COLOR_BG, fg=COLOR_LABEL, anchor="w")
        self.v_nic_team.pack(fill="x", pady=(2, 0))

    def _build_disk_panel(self):
        p = self.panel_disk
        self.disk_container = tk.Frame(p, bg=COLOR_BG)
        self.disk_container.pack(fill="both", expand=True)
        tk.Label(p, text="External attached storage", font=("Clear Gothic", 9, "bold"),
                 bg=COLOR_BG, fg=COLOR_LABEL, anchor="w").pack(fill="x", pady=(2, 0))
        self.san_container = tk.Frame(p, bg=COLOR_BG)
        self.san_container.pack(fill="both", expand=True)

        # [addition] disk list + Under the two externally connected storage items, only problematic disks are summarized and displayed in one line.
        tk.Label(p, text="Disk Anomalies items", font=("Clear Gothic", 9, "bold"),
                 bg=COLOR_BG, fg=COLOR_LABEL, anchor="w").pack(fill="x", pady=(8, 0))
        self.disk_issue_container = tk.Frame(p, bg=COLOR_BG)
        self.disk_issue_container.pack(fill="both", expand=True)
   
    
    def _build_virt_panel(self):
        p = self.panel_virt
        # Create a virtualized container (important: where self.virt_container is defined)
        self.virt_container = tk.Frame(p, bg=COLOR_BG)
        self.virt_container.pack(fill="both", expand=True)

        # Service List Title
        tk.Label(p, text="Running Service", font=("Clear Gothic", 9, "bold"), bg=COLOR_BG, fg=COLOR_LABEL, anchor="w").pack(fill="x", pady=(6, 2))
        self.svc_container = tk.Frame(p, bg=COLOR_BG)
        self.svc_container.pack(fill="both", expand=True)

    def _build_log_panel(self):
        p = self.panel_log
        for title, attr_name in [("[application]", "log_app_text"), ("[system]", "log_sys_text")]:
            tk.Label(p, text=title, font=("Clear Gothic", 9, "bold"), bg=COLOR_BG, fg=COLOR_LABEL, anchor="w").pack(fill="x", pady=(8 if "System" in title else 0, 2))
            text_widget = tk.Text(p, height=4, bg=COLOR_BG, fg=COLOR_INFO, font=("Clear Gothic", 8), relief="flat", wrap="word", cursor="xterm")
            text_widget.pack(fill="x")
            text_widget.bind("<Key>", lambda e: "break")
            text_widget.bind("<<Paste>>", lambda e: "break")
            setattr(self, attr_name, text_widget)

    def _fill_selectable_text(self, widget, lines_with_tags):
        widget.config(state="normal")
        widget.delete("1.0", "end")
        for text, tag in lines_with_tags:
            start = widget.index("end-1c")
            widget.insert("end", text + "\n")
            if tag: widget.tag_add(tag, start, widget.index("end-1c"))
        widget.tag_config("err", foreground=COLOR_ERR)
        widget.tag_config("warn", foreground="#b8860b")
        widget.config(state="disabled")

    def _cpu_sampler_loop(self):
        while True:
            try:
                cpu_val = psutil.cpu_percent(interval=1)
                ram_val = None
                try: ram_val = psutil.virtual_memory().percent
                except Exception: pass
                with self._sample_lock:
                    self._cpu_samples.append(cpu_val)
                    if ram_val is not None: self._ram_samples.append(ram_val)
            except Exception:
                time.sleep(1)

    def _slow_loop(self):
        # [correction] In order to reduce system load, it is automatically searched only once for the first time after running the program.
        # There will be no automatic recurring renewals thereafter.Subsequent updates will only occur when you press the refresh button.
        # It runs (CPU/RAM/Real-time values ​​such as disk usage are continuously reflected with light 2-second interval updates).
        self._run_slow_refresh_once()

    def _run_slow_refresh_once(self):
        """[addition] 5Automatic renewal of minute intervals Separate one-time tasks into separate methods - refresh
        When the button is pressed, the same task can be immediately executed one more time in a background thread.
        (the screen doesn't freeze)."""
        results = {}
        # [Performance improvements] Existing 10 tasks (running approximately 10 PowerShell processes) -> 6integrated into the opening
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            future_to_key = {
                executor.submit(get_system_static_info): "system_static",
                executor.submit(get_network_info): "network",
                executor.submit(get_storage_info): "storage",
                executor.submit(get_virt_and_services_info): "virt_svc",
                executor.submit(get_optional_features_info): "features",
                executor.submit(get_system_log): "logs",
            }

            for future in concurrent.futures.as_completed(future_to_key):
                key = future_to_key[future]
                try:
                    results[key] = future.result()
                except Exception as e:
                    print(f"Job error ({key}): {e}")
                    results[key] = None

        # Batch update on main thread (GUI) after collecting all data
        if results:
            self.after(0, lambda: self._apply_slow_data(results))

    def _on_refresh_clicked(self):
        """[addition] When you click the refresh button, without waiting for the next automatic renewal (up to 5 minutes)
        Update immediately.Prevents duplicate execution if it is already refreshing."""
        if getattr(self, "_manual_refresh_running", False):
            return
        self._manual_refresh_running = True
        self.status_label.config(text="Refreshing...")
        threading.Thread(target=self._manual_refresh_worker, daemon=True).start()

    def _manual_refresh_worker(self):
        try:
            self._run_slow_refresh_once()
        finally:
            self._manual_refresh_running = False
            self.after(0, self._mark_ready_if_loaded)

    def _apply_slow_data(self, data):
        # Remember the position before starting the update, and return it to the original position after you finish drawing.
        scroll_pos = self.canvas.yview()[0] if hasattr(self, "canvas") else None

        self._slow_cache = data
        # Even if individual information collection items fail (None), each item is supplemented with default values ​​so that the entire update does not die.
        b = data.get("system_static") or {
            "computer_name": "Unable_to_verify", "os": "Unable_to_verify", "last_update": "Unable_to_verify",
            "manufacturer": "Unable to confirm", "power": "Unable_to_verify", "boot_dt": None,
            "cpu_name": "Unable_to_verify", "cpu_cores": 0, "cpu_threads": 0, "gpus": [],
            "ram_bank": {"total_slots": 0, "populated": 0, "slots": [], "total_gb": 0.0},
        }
        n = data.get("network") or {"connection": "Unable to verify", "nic": "Unable_to_verify", "link_speed_mbps": 0, "nics": [], "team": None}
        storage = data.get("storage") or {
            "external_storage": [], "disk_health": {}, "permission_warning": False,
            "smb_shares": [], "nfs_or_other_net": [], "iscsi_session_count": 0,
        }
        virt_svc = data.get("virt_svc") or {"manu": "", "model": "", "bios_ver": "", "services": [], "docker_containers": [], "kubelet_extra": {}}
        features = data.get("features") or {"permission_warning": False}
        logs = data.get("logs") or {"Application": [], "System": []}

        virt = classify_virtualization(virt_svc, features)
        svc = classify_installed_services(virt_svc)
        ram_bank = b.get("ram_bank") or {"total_slots": 0, "populated": 0, "slots": [], "total_gb": 0.0}

        self._set_row(self.v_computer, b["computer_name"])
        self._set_row(self.v_os, b["os"])
        self._set_row(self.v_update, str(b["last_update"]))
        self._set_row(self.v_manu, b["manufacturer"])

        # [correction] Apply separate power and fan states
        self._set_row(self.v_power, b["power"])

        # [addition] RAM Slot information
        populated = ram_bank.get("populated", 0)
        slots = ram_bank.get("slots", [])
        if populated:
            if slots:
                formatted_slots = []
                for s in slots:
                    s_str = str(s).strip()
                    # 'Remove all messy duplicate words such as 'bank', 'bank', 'slot', 'dimm', etc.
                    cleaned_s = s_str.lower().replace("bank", "").replace("bank", "").replace("slot", "").replace("dimm", "").strip()
                    # Combine DIMMs only before the number
                    formatted_slots.append(f"DIMM {cleaned_s.upper()}")
                
                dimm_txt = ", ".join(formatted_slots)
            else:
                dimm_txt = "Unable_to_verify"
                
            # [Edit wording] Adjust overall output text format
            ram_bank_text = f"gun {populated} mounted ({dimm_txt})"
        else:
            ram_bank_text = "Unable_to_verify"
            
        self._set_row(self.v_ram_bank, ram_bank_text)

        # [correction] CPU Apply model and core separation
        self._set_row(self.v_cpu_name, b['cpu_name'])
        self._set_row(self.v_cpu_cores, f"{b['cpu_cores']} core / {b['cpu_threads']} thread")

        for w in self.gpu_container.winfo_children(): w.destroy()
        if not b.get("gpus"): self._add_row(self.gpu_container, "GPU", "Unable_to_verify", label_width=12, label_padx=(0, 5))
        else:
            for i, g in enumerate(b["gpus"], 1):
                lbl = f"GPU{i} ({g['type']})" if g["type"] != "Unknown" else f"GPU{i}"
                val = g["name"] + (f" - VRAM approximately {g['vram_gb']:.1f}GB" if g["vram_gb"] > 0 else "")
                self._add_row(self.gpu_container, lbl, val, label_width=12, label_padx=(0, 5))

        self._set_row(self.v_conn, n["connection"])
        self._set_row(self.v_nic, n["nic"])
        t_text, t_color = get_link_speed_tier(n.get("link_speed_mbps"))
        self.link_dot.set_color(t_color); self._set_row(self.v_link_speed, t_text)

        # [addition] Displays operating status for each physical LAN card
        for w in self.nic_status_container.winfo_children(): w.destroy()
        nics = n.get("nics") or []
        if not nics:
            tk.Label(self.nic_status_container, text="Unable_to_verify", font=("Clear Gothic", 9), bg=COLOR_BG, fg=COLOR_LABEL, anchor="w").pack(fill="x")
        else:
            for nic in nics:
                row2 = tk.Frame(self.nic_status_container, bg=COLOR_BG); row2.pack(fill="x", pady=1)
                name_val = ExpandableValue(row2, font=("Clear Gothic", 9), fg=COLOR_LABEL)
                name_val.pack(side="left", fill="x", expand=True)
                name_val.set_value(nic["name"])
                status_color = COLOR_BUTTON if nic["status"] == "Normal" else COLOR_ERR
                tk.Label(row2, text=nic["status"], font=("Clear Gothic", 9, "bold"), bg=COLOR_BG, fg=status_color).pack(side="right")

        # [addition] Whether redundancy (NIC Team) is configured or not - Show briefly only when configured
        team_info = n.get("team")
        self.v_nic_team.config(text=(f"redundancy: {team_info}" if team_info else ""))

        # [correction] Show all raw SAN LUNs without filtering by whether they are mounted or not (mounted)/(including the not mounted state),
        # NAS (SMB) even without raw LUNs/NFS) It shows the connection information together.
        for w in self.san_container.winfo_children(): w.destroy()
        if storage.get("permission_warning"):
            tk.Label(self.san_container, text="failed : Insufficient privileges (requires execution with administrator privileges)", font=("Clear Gothic", 9),
                     bg=COLOR_BG, fg=COLOR_ERR, anchor="w").pack(fill="x")
        else:
            ext_disks = storage.get("external_storage") or []
            smb_shares = storage.get("smb_shares") or []
            other_net = storage.get("nfs_or_other_net") or []
            iscsi_cnt = storage.get("iscsi_session_count") or 0

            if ext_disks or smb_shares or other_net or iscsi_cnt:
                # [correction] Display connection summary in two lines + "Remove the boldface to distinguish it from the “Externally attached storage” title.
                multipath_cnt = sum(1 for d in ext_disks if (d.get("path_count") or 0) and d["path_count"] > 1)
                line1 = f"Connection summary : multi_pass {multipath_cnt} LUN {len(ext_disks)} ,"
                line2 = f"shared_folder {len(smb_shares)} nfs/etc {len(other_net)}"
                if iscsi_cnt: line2 += f", iSCSI session {iscsi_cnt} "
                tk.Label(self.san_container, text=line1, font=("Clear Gothic", 9), bg=COLOR_BG,
                         fg=COLOR_LABEL, anchor="w", wraplength=380, justify="left").pack(fill="x")
                tk.Label(self.san_container, text=line2, font=("Clear Gothic", 9), bg=COLOR_BG,
                         fg=COLOR_LABEL, anchor="w", wraplength=380, justify="left").pack(fill="x", pady=(0, 4))

            if not ext_disks and not smb_shares and not other_net:
                tk.Label(self.san_container, text="No external storage connected(SAN)/NAS)", font=("Clear Gothic", 9),
                         bg=COLOR_BG, fg=COLOR_LABEL, anchor="w", wraplength=380, justify="left").pack(fill="x")
            else:
                for d in ext_disks:
                    # [addition] dell/HP/IBM etc. Multipath (MPIO)/LUN Connection status (connected/cleared/Disability problem) indication
                    conn_state = d.get("conn_state", "-")
                    fg_color = COLOR_ERR if "Failure" in conn_state else COLOR_LABEL
                    mount_letters = d.get("mount_letters") or []
                    mount_txt = f"mounted_({', '.join(mount_letters)})" if d.get("is_mounted") else "Not mounted"
                    e = ExpandableValue(self.san_container, font=("Clear Gothic", 9), fg=fg_color)
                    e.pack(fill="x", pady=(3, 1))
                    e.set_value(f"[external] {d['name']} [{d['bus_type']}, {d['size_gb']:.1f}GB, "
                                f"situation:{d['status']}/{d['health']}, connection:{conn_state}, {mount_txt}]")

                # [addition] SMBNAS mapped to/File server sharing
                for s in smb_shares:
                    vendor_txt = f", Estimated Device:{s['vendor_guess']}(Estimate)" if s.get("vendor_guess") else ""
                    # [correction] statusis now "6-Since it is a description string such as "Cannot be used (...)", the color judgment is
                    # Set to the original code value (status_code) (0=normal, other=problem)
                    is_problem = s.get("status_code") is not None and s["status_code"] != 0
                    fg_color = COLOR_ERR if is_problem else COLOR_LABEL
                    e = ExpandableValue(self.san_container, font=("Clear Gothic", 9), fg=fg_color)
                    e.pack(fill="x", pady=(3, 1))
                    e.set_value(f"[NAS/SMB] {s['remote']} -> {s['drive']} [situation:{s['status']}{vendor_txt}]")

                # [addition] SMBOther network drives not captured (mainly NFS)
                for nfs in other_net:
                    vendor_txt = f", Estimated Device:{nfs['vendor_guess']}(Estimate)" if nfs.get("vendor_guess") else ""
                    e = ExpandableValue(self.san_container, font=("Clear Gothic", 9), fg=COLOR_LABEL)
                    e.pack(fill="x", pady=(3, 1))
                    e.set_value(f"[NFS/etc] {nfs['remote']} -> {nfs['drive']} "
                                f"[{nfs['filesystem']}, {nfs['size_gb']:.1f}GB{vendor_txt}]")

        # Virtualization Solution Dynamic Presentation Logic
        if hasattr(self, 'virt_container'):
            for w in self.virt_container.winfo_children(): w.destroy()
            if not virt:
                tk.Label(self.virt_container, text="No virtualization detected", font=("Clear Gothic", 9), bg=COLOR_BG, fg=COLOR_LABEL, anchor="w").pack(fill="x", pady=1)
            else:
                for v in virt:
                    row = tk.Frame(self.virt_container, bg=COLOR_BG); row.pack(fill="x", pady=1)
                    tk.Label(row, text=v['name'], font=("Clear Gothic", 9, "bold"), bg=COLOR_BG, fg=COLOR_LABEL).pack(side="left")

                    status_color = COLOR_ERR if v['status'] in ("Stopped", "Paused", "Insufficient privileges (administrator privileges required)") else COLOR_BUTTON
                    tk.Label(row, text=v['status'], font=("Clear Gothic", 9, "bold"), bg=COLOR_BG, fg=status_color).pack(side="right")

                    # [addition] When operating as a host, guests (virtual machines)/container) lists are indented and displayed together.
                    guests = v.get("guests") or []
                    host_total_gb = (b.get("ram_bank") or {}).get("total_gb") or 0
                    if guests:
                        for g in guests:
                            g_state = g.get("state", "")
                            # [correction] Hyper-VBoth are recognized as "Running" for Docker and "Up 3 hours" for Docker.
                            g_color = COLOR_BUTTON if g_state.lower().startswith(("running", "up")) else COLOR_LABEL
                            if "image" in g:
                                # Docker Containers remain the same as before
                                bits = [g_state or "Unable_to_verify"]
                                if g.get("image"): bits.append(f"image:{g['image']}")
                                g_label = f"    └ {g.get('name') or 'Unable_to_verify'} ({', '.join(bits)})"
                            else:
                                # [correction] "status cpu% : memory% : Leave out the status text from "Run",
                                # CPU/Memory usage is displayed up to 2 decimal places.
                                # (Memory is measured in proportion to the total memory of the host instead of absolute capacity. %(marked with)
                                cpu_val = g.get("cpu_pct")
                                cpu_txt = f"{float(cpu_val):.2f}%" if cpu_val is not None else "Unable_to_verify"
                                mem_gb = g.get("mem_gb") or 0
                                mem_txt = f"{(mem_gb / host_total_gb * 100):.2f}%" if host_total_gb else "Unable_to_verify"
                                # [addition] Guest internal disk usage cannot be viewed without logging in.
                                # Instead, the VM's first virtual disk (VHD/VHDX) Approximately as a percentage of file size
                                # Display usage estimates instead (values ​​that are meaningful only on dynamically expanding disks)
                                # If it is a fixed size disk or the query fails, the number of operation days is displayed as before)
                                disk_pct = g.get("disk_pct")
                                if disk_pct is not None:
                                    last_bit = f"DISK {disk_pct:.2f}%"
                                else:
                                    last_bit = f"behavior {g.get('uptime') or 'Unable_to_verify'}"
                                detail = f"CPU {cpu_txt} : RAM {mem_txt} : {last_bit}"
                                g_label = f"    └ {g.get('name') or 'Unable_to_verify'} ({detail})"
                            tk.Label(self.virt_container, text=g_label, font=("Clear Gothic", 9), bg=COLOR_BG,
                                     fg=g_color, anchor="w", wraplength=380, justify="left").pack(fill="x", pady=(0, 1))
                    elif v.get("status") == "Running" and v.get("name") in ("Hyper-V", "Docker Engine"):
                        # [addition] If the host is running but the guest list is empty
                        # (If there are no actual guests, or the management tool/CLI (If access is not possible and the search itself is not possible)
                        empty_msg = ("No guest machines (or Hyper-V Management tools not installed)" if v["name"] == "Hyper-V"
                                     else "No running containers (or no docker CLI access)")
                        tk.Label(self.virt_container, text=f"    └ {empty_msg}",
                                 font=("Clear Gothic", 9), bg=COLOR_BG, fg=COLOR_LABEL, anchor="w",
                                 wraplength=380, justify="left").pack(fill="x", pady=(0, 1))

                    # [addition] Kubernetes(kubelet)Instead of a list of pods, the minimum verifiable information
                    # (kubelet version and, if possible, the number of containers based on crictl)
                    extra = v.get("extra_info")
                    if extra:
                        lines = []
                        if extra.get("version"):
                            lines.append(f"kubelet version: {extra['version']}")
                        cnt = extra.get("container_count")
                        if cnt is not None:
                            lines.append(f"Number of containers (pods): {cnt}  (by crictl")
                        else:
                            lines.append("Number of containers (pods): Unable_to_verify (crictl not installed or inaccessible)")
                        for line in lines:
                            tk.Label(self.virt_container, text=f"    └ {line}", font=("Clear Gothic", 9),
                                     bg=COLOR_BG, fg=COLOR_LABEL, anchor="w",
                                     wraplength=380, justify="left").pack(fill="x", pady=(0, 1))

        for w in self.svc_container.winfo_children(): w.destroy()
        if not svc: tk.Label(self.svc_container, text="No services detected", font=("Clear Gothic", 9), bg=COLOR_BG, fg=COLOR_LABEL, anchor="w").pack(fill="x")
        else:
            for s in svc:
                row = tk.Frame(self.svc_container, bg=COLOR_BG); row.pack(fill="x", pady=2)
                # [correction] Fixed an issue where the category label was displayed right next to the service name when it was long.
                # -> widthImprove readability by providing ample space and spacing with padx.
                tk.Label(row, text=f"[{s['category']}]", width=10, anchor="w", font=("Clear Gothic", 8, "bold"), bg=COLOR_BG, fg=COLOR_LABEL).pack(side="left", padx=(0, 10))
                name_val = ExpandableValue(row, font=("Clear Gothic", 8), fg=COLOR_VALUE)
                name_val.pack(side="left", fill="x", expand=True)
                name_val.set_value(s["name"])
                tk.Label(row, text=s["status"], width=8, anchor="e", font=("Clear Gothic", 8, "bold"), bg=COLOR_BG, fg=COLOR_ERR if "Error" in s["status"] else COLOR_LABEL).pack(side="right")

        get_tags = lambda lst: [(l, "err" if l.startswith("[danger]") else "warn" if l.startswith("[warning]") else None) for l in lst]
        self._fill_selectable_text(self.log_app_text, get_tags(logs.get("Application", [])))
        self._fill_selectable_text(self.log_sys_text, get_tags(logs.get("System", [])))

        self._loaded_slow = True
        self._mark_ready_if_loaded()

        # [addition] Restore to scroll position before update (use after_idle to apply after layout is actually reflected)
        if scroll_pos is not None:
            self.after_idle(lambda: self.canvas.yview_moveto(scroll_pos))

    def _fast_tick(self):
        try:
            data = {"ip": get_ip_address()}
            with self._sample_lock:
                data["cpu_percent"] = self._cpu_samples[-1] if self._cpu_samples else 0.0
            vm = psutil.virtual_memory()
            data.update({"ram_percent": vm.percent, "ram_total_gb": vm.total / (1024 ** 3), "ram_used_gb": (vm.total - vm.available) / (1024 ** 3), "ram_free_gb": vm.available / (1024 ** 3)})
            data["disks"] = get_disk_info()
            data["boot_dt"] = (self._slow_cache.get("system_static") or {}).get("boot_dt") if self._slow_cache else None

            io_now, now_t = psutil.net_io_counters(), time.time()
            if self._net_last_io and self._net_last_time:
                elapsed = max(now_t - self._net_last_time, 0.001)
                data["sent_mbps"] = max((io_now.bytes_sent - self._net_last_io.bytes_sent) * 8 / 1_000_000 / elapsed, 0.0)
                data["recv_mbps"] = max((io_now.bytes_recv - self._net_last_io.bytes_recv) * 8 / 1_000_000 / elapsed, 0.0)
            else:
                data["sent_mbps"] = data["recv_mbps"] = 0.0
            self._net_last_io, self._net_last_time = io_now, now_t

            self._apply_fast_data(data)
        finally:
            self.after(self.FAST_REFRESH_MS, self._fast_tick)
    
    def _apply_fast_data(self, data):
        # [addition] This is a safety measure in case the disk configuration actually changes and needs to be redrawn.
        # Here too, the scroll position before updating is remembered and restored after completion.
        scroll_pos = self.canvas.yview()[0] if hasattr(self, "canvas") else None

        if data["boot_dt"]:
            up, bt = get_uptime_texts(data["boot_dt"])
            self._set_row(self.v_uptime, up); self._set_row(self.v_boot, bt)

        self.bar_cpu.set_value(data["cpu_percent"], f"CPU {data['cpu_percent']:.2f}%")
        self.bar_ram.set_value(data["ram_percent"], f"RAM {data['ram_percent']:.2f}%")

        with self._sample_lock:
            cpu_avg = sum(self._cpu_samples) / len(self._cpu_samples) if self._cpu_samples else 0.0
            ram_avg = sum(self._ram_samples) / len(self._ram_samples) if self._ram_samples else 0.0
        self._set_row(self.v_cpu_usage, f"{cpu_avg:.1f}% (average)")

        self._set_row(self.v_ram_detail, f"gun {data['ram_total_gb']:.2f}GB, use {data['ram_used_gb']:.2f}GB, spare {data['ram_free_gb']:.2f}GB (average {ram_avg:.2f}%)")

        self._set_row(self.v_ip, data["ip"])
        self._set_row(self.v_speed, f"Sent {data['sent_mbps']:.1f} Mbps | Received {data['recv_mbps']:.1f} Mbps")

        storage = (self._slow_cache.get("storage") if self._slow_cache else None) or {}
        disk_health_map = storage.get("disk_health", {})

        n_disks = len(data["disks"])
        # [addition] In case the number of disks is large, the bar chart height is dynamically reduced and displayed inside a box.
        bar_h = 20 if n_disks <= 4 else (15 if n_disks <= 7 else 10)
        row_pad = (6, 2) if n_disks <= 4 else (3, 1)
        self._disk_problem_list = []

        new_order = [d["device"] for d in data["disks"]]
        # [correction] In the past, the entire disk bar was erased and redrawn every two seconds, causing the screen to blink.
        # The scroll position was also messed up.Disk configuration (number of/If the order is the same as before, the existing widget
        # Only updates values ​​and redraws only when the configuration actually changes.
        rebuild = new_order != self._disk_row_order
        if rebuild:
            for w in self.disk_container.winfo_children(): w.destroy()
            self._disk_row_widgets = {}

        for d in data["disks"]:
            device = d['device']
            meta = disk_health_map.get(device, {})
            health_txt = meta.get("health", "Unable_to_verify")
            # [addition] internal/External disk identification tag (based on bus type)
            tag = "[external]" if meta.get("is_external") else "[internal]"
            value_text = f"{tag} {device} [Total: {d['total_gb']:.2f}GB, use: {d['used_gb']:.2f}GB, spare: {d['free_gb']:.2f}GB, status: {health_txt}]"

            if rebuild:
                desc = ExpandableValue(self.disk_container, font=("Clear Gothic", 9), fg=COLOR_LABEL)
                desc.pack(fill="x", pady=row_pad)
                bar = PercentBar(self.disk_container, color=COLOR_DISK_BAR, height=bar_h)
                bar.pack(fill="x")
                self._disk_row_widgets[device] = (desc, bar)
            else:
                desc, bar = self._disk_row_widgets[device]
            desc.set_value(value_text)
            bar.set_value(d["percent"], f"{d['percent']:.1f}%")

            # [correction] read/The write operation status is not displayed for each item, but only disks with problems are collected.
            # We only collect them here to provide a one-line summary in "Disk Health Anomalies" below.
            if not meta.get("is_external"):
                io_status = meta.get("io_status", "Unable_to_verify")
                issues = []
                if health_txt in ("Warning", "Error"):
                    issues.append(f"disk status {health_txt}")
                if io_status.startswith("Caution") and "(" in io_status:
                    issues.append(io_status[io_status.find("(") + 1: io_status.rfind(")")])
                if issues:
                    self._disk_problem_list.append((device, ", ".join(issues)))

        self._disk_row_order = new_order

        # [addition] disk list + Under the two externally connected storage items, only the disks with problems are summarized.
        # [correction] If it is the same as the previous display, it will not be redrawn to reduce unnecessary flickering.
        if self._disk_problem_list != self._disk_issue_prev:
            self._disk_issue_prev = list(self._disk_problem_list)
            for w in self.disk_issue_container.winfo_children(): w.destroy()
            if not self._disk_problem_list:
                tk.Label(self.disk_issue_container, text="No Faulty Disk", font=("Clear Gothic", 9),
                         bg=COLOR_BG, fg=COLOR_LABEL, anchor="w").pack(fill="x")
            else:
                for device, issue_desc in self._disk_problem_list:
                    tk.Label(self.disk_issue_container, text=f"{device} / {issue_desc} / Replacement required", font=("Clear Gothic", 9, "bold"),
                             bg=COLOR_BG, fg=COLOR_ERR, anchor="w", wraplength=380, justify="left").pack(fill="x", pady=2)

        self._loaded_fast = True
        self._mark_ready_if_loaded()

        if scroll_pos is not None:
            self.after_idle(lambda: self.canvas.yview_moveto(scroll_pos))

    def _mark_ready_if_loaded(self):
        if self._loaded_slow and self._loaded_fast:
            self._marked_ready = True
            # [addition] When manually updating with the refresh button, it is not overwritten with “View Completed”.
            # (2Real-time updates every second prevent this phrase from being reverted)
            if not getattr(self, "_manual_refresh_running", False):
                self.status_label.config(text="Search_complete")
        elif not self._marked_ready:
            self.status_label.config(text="Loading information...")

    def open_readme(self):
        win = tk.Toplevel(self)
        win.title("guide - Program Information")
        win.configure(bg=COLOR_BG)
        win.geometry("580x700")
        win.resizable(False, False)
        
        win.transient(self)
        win.grab_set()

        readme_text = (
            "I created this tool with a simple idea: while working in the server room, I wondered\n"
            "if I could view all the monthly server check items with just a single click instead of\n"
            "manually running commands and navigating through menus every time.\n"
            "While it might be a small tool, I hope it brings a bit of convenience to your daily\n"
            "routine. The source code is provided so you can modify and adapt it to your needs.\n"
            "If you do modify or redistribute it keeping a credit to the original author would be\n"
            "greatly appreciated.\n"
            "Thank you.\n\n"
            "Contact: seodam147@gmail.com\n\n"
            "License\n"
            "Copyright (c) 2026 seodam147. All rights reserved.\n"
            "Licensed under the **MIT License**. (Free to use, modify, and distribute with credit).\n"
            "This tool is developed under and complies with the MIT License. For details\n"
            "please open and review the License.\n\n"
            "*THE SOFTWARE IS PROVIDED 'AS IS', WITHOUT WARRANTY OF ANY KIND.\n"
            "It is strongly recommended to test and run this tool on a non-production PC\n"
            "before deploying or using it in a live server environment.\n\n"
            "☕ Support the Project\n"
            "If this tool helped you achieve a trouble-free workday, consider supporting\n"
            "continuous updates with a warm cup of coffee!\n\n"
            
        )

        lbl_txt = tk.Label(
            win, text=readme_text, font=("Clear Gothic", 10),
            bg=COLOR_BG, fg=COLOR_LABEL, justify="left", anchor="nw"
        )
        lbl_txt.pack(fill="x", padx=20, pady=(20, 10))

        # 2. QR code creat
        qr_data = "https://ko-fi.com/seodam147"
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=5,
            border=2,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)

        qr_img = qr.make_image(fill_color="black", back_color="white")
        # Tkinter to ImageTk change
        self.qr_photo = ImageTk.PhotoImage(qr_img)

        # 3. QR UI
        qr_frame = tk.Frame(win, bg=COLOR_BG)
        qr_frame.pack(pady=10)

        qr_label = tk.Label(qr_frame, image=self.qr_photo, bg=COLOR_BG)
        qr_label.pack()

        tk.Label(
            win, text="[ Scan QR Code to Support ]",
            font=("Clear Gothic", 8, "bold"), bg=COLOR_BG, fg=COLOR_BUTTON
        ).pack(pady=(5, 15))
        
        link_btn = tk.Button(
            win, 
            text="🌐 Open Support Page in Browser", 
            command=lambda: webbrowser.open("https://ko-fi.com/seodam147"),
            bg=COLOR_BG, 
            fg="#0066CC",  # link style blue
            font=("Clear Gothic", 9, "underline"),
            bd=0,
            cursor="hand2"
        )
        link_btn.pack(pady=(0, 10))

        #self._make_button(win, "Close", win.destroy, width=10).pack(pady=16) #Exception handling due to duplicate close button
        # 1. Internal function that pops up the license window
        def show_license():
            lic_win = tk.Toplevel(win)
            lic_win.title("MIT License")
            lic_win.geometry("600x430")
            
            lic_text = tk.Text(lic_win, wrap="word", font=("Clear Gothic", 9), padx=15, pady=15)
            lic_text.pack(fill="both", expand=True)
            
            mit_license = """MIT License

Copyright (c) 2026 seodam147

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE."""
            lic_text.insert("1.0", mit_license)
            lic_text.config(state="disabled")
            
            # Create_close_button
            lic_btn_frame = tk.Frame(lic_win, bg=COLOR_BG)
            lic_btn_frame.pack(pady=10)
            
            # Close button placement
            self._make_button(lic_btn_frame, "Close", lic_win.destroy, width=10).pack()
            
        # 2. Create a frame to align the bottom buttons horizontally
        btn_frame = tk.Frame(win, bg=COLOR_BG)
        btn_frame.pack(pady=16)

        # 3. Place license button and close button inside frame
        self._make_button(btn_frame, "License", show_license, width=10).pack(side="left", padx=5)
        self._make_button(btn_frame, "Close", win.destroy, width=10).pack(side="left", padx=5)

    def open_admin_tools(self):
        if IS_WINDOWS:
            try: os.startfile("compmgmt.msc")
            except Exception as e: messagebox.showerror("Error", f"Cannot open Administrative Tools: {e}")
        else: messagebox.showinfo("Information", "This feature is only supported on Windows.")

    def open_event_viewer(self):
        if IS_WINDOWS:
            try: os.startfile("eventvwr.msc")
            except Exception as e: messagebox.showerror("Error",f"Cannot open Event Viewer: {e}")
        else: messagebox.showinfo("Information", "This feature is only supported on Windows.")

    def save_as_image(self):
        try: from PIL import ImageGrab
        except ImportError:
            messagebox.showerror("Error", "Pillow is not installed.Please run 'pip install Pillow' and try again.")
            return
        fp = filedialog.asksaveasfilename(parent=self, title="Save as picture file", initialfile=f"System_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
                                          defaultextension=".png", filetypes=[("PNG File", "*.png"), ("JPEG", "*.jpg;*.jpeg"), ("All files", "*.*")])
        if not fp: return
        self.update()
        x, y = self.winfo_rootx(), self.winfo_rooty()
        try:
            img = ImageGrab.grab(bbox=(x, y, x + self.winfo_width(), y + self.winfo_height()))
            if os.path.splitext(fp)[1].lower() in (".jpg", ".jpeg") and img.mode == "RGBA": img = img.convert("RGB")
            img.save(fp)
            messagebox.showinfo("Save complete", f"The image has been saved.:\n{fp}")
        except Exception as e: messagebox.showerror("Error", f"An error occurred while saving: {e}")

if __name__ == "__main__":
    try:
        app = SystemCheckApp()
        app.mainloop()
    except Exception as e:
        # [addition] So that the EXE does not just turn off without any notice even if an exception occurs during startup.
        # First, an error window appears, and if that fails (e.g.: Tk Self-initialization failure) is left in the log file.
        try:
            messagebox.showerror("Startup error", f"An error occurred while starting the program:\n{e}")
        except Exception:
            pass
        try:
            base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            with open(os.path.join(base_dir, "error_log.txt"), "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now()}] startup error: {e}\n")
                f.write(traceback.format_exc() + "\n")
        except Exception:
            pass
