#!/bin/bash
###############################################################################
# linux_check.sh - Linux server check script
# Usage : sh linux_check.sh   or   bash linux_check.sh
###############################################################################

# Re-exec under bash if invoked via sh (dash, etc.) so bash features (arrays, etc.) are available
if [ -z "$BASH_VERSION" ]; then
    if command -v bash >/dev/null 2>&1; then
        exec bash "$0" "$@"
    else
        echo "[Error] This script requires bash. Please install bash and run it again. (e.g. yum install -y bash / apt install -y bash)" >&2
        exit 1
    fi
fi

# ===== Color definitions =====
C_RED='\033[0;31m'
C_YELLOW='\033[1;33m'
C_GREEN='\033[0;32m'
C_CYAN='\033[0;36m'
C_BOLD='\033[1m'
C_NC='\033[0m'

TMP_LOG="/tmp/linux_check_$(date +%Y%m%d_%H%M%S).tmp"
: > "$TMP_LOG"

log() {
    echo -e "$1"
    echo -e "$1" | sed -r 's/\x1B\[[0-9;]*[a-zA-Z]//g' >> "$TMP_LOG"
}

section() {
    log ""
    log "${C_BOLD}${C_CYAN}■ $1${C_NC}"
}

has_cmd() { command -v "$1" >/dev/null 2>&1; }

IS_ROOT=0
[ "$(id -u)" -eq 0 ] && IS_ROOT=1

log "${C_BOLD}=========================================================${C_NC}"
log "${C_BOLD} Linux Server Check  ($(date '+%Y-%m-%d %H:%M:%S'))${C_NC}"
log "${C_BOLD}=========================================================${C_NC}"
[ "$IS_ROOT" -eq 0 ] && log "${C_YELLOW}* Not running as root, so some items may have limited checking.${C_NC}"

###############################################################################
section "0. System Info"
###############################################################################
HOSTNAME_VAL=$(hostname 2>/dev/null)

# Cross-scan logic to reliably identify any Linux distribution (old/new, domestic/foreign)
if [ -f /etc/redhat-release ]; then
    # 1. RHEL, CentOS, Rocky, Alma, Oracle Linux, etc.
    OS_VER=$(cat /etc/redhat-release)
elif [ -f /etc/os-release ]; then
    # 2. Modern global distro standard (Ubuntu, Debian, SUSE, Amazon Linux, etc.)
    . /etc/os-release
    OS_VER="$PRETTY_NAME"
elif has_cmd lsb_release; then
    # 3. Fallback for distros with the LSB spec installed
    OS_VER=$(lsb_release -d | awk -F':' '{print $2}' | xargs)
elif [ -f /etc/issue ] && grep -qE "Ubuntu|Debian|Mint" /etc/issue; then
    # 4. Guard for very old Ubuntu/Debian-family systems without /etc/os-release
    OS_VER=$(head -n 1 /etc/issue | sed 's/\\n//g' | sed 's/\\l//g' | xargs)
elif [ -f /etc/debian_version ]; then
    # 5. Guard for a plain old Debian environment
    OS_VER="Debian GNU/Linux $(cat /etc/debian_version)"
else
    # 6. Last resort: auto-discover and clean up vendor/release files
    REL_FILE=$(ls /etc/*-release 2>/dev/null | grep -v "os-release" | head -n 1)
    if [ -n "$REL_FILE" ] && [ -f "$REL_FILE" ]; then
        OS_VER=$(cat "$REL_FILE" | head -n 1)
    else
        OS_VER="Unknown (generic Linux environment)"
    fi
fi

KERNEL_VER=$(uname -r)
ARCH=$(uname -m)
case "$ARCH" in
    x86_64|aarch64) OS_BIT="64bit" ;;
    i386|i686)     OS_BIT="32bit" ;;
    *)             OS_BIT="$ARCH" ;;
esac

# OS Info print
log "  - Hostname       : $HOSTNAME_VAL"
log "  - OS Version     : $OS_VER"
log "  - Kernel         : $KERNEL_VER"
log "  - OS bit         : $OS_BIT"

# --- Hardware Info ---
DMI_CMD="dmidecode"
if [ ! -x "$(command -v dmidecode)" ] && [ -x "/usr/sbin/dmidecode" ]; then DMI_CMD="/usr/sbin/dmidecode"; fi

SYS_VENDOR=""
SYS_PRODUCT=""
SYS_SERIAL=""

if [ "$IS_ROOT" -eq 1 ] && [ -x "$(command -v $DMI_CMD)" ]; then
    SYS_VENDOR=$($DMI_CMD -s system-manufacturer 2>/dev/null | xargs)
    SYS_PRODUCT=$($DMI_CMD -s system-product-name 2>/dev/null | xargs)
    SYS_SERIAL=$($DMI_CMD -s system-serial-number 2>/dev/null | xargs)
fi

[ -z "$SYS_VENDOR" ] && [ -f /sys/class/dmi/id/sys_vendor ] && SYS_VENDOR=$(cat /sys/class/dmi/id/sys_vendor 2>/dev/null | xargs)
[ -z "$SYS_PRODUCT" ] && [ -f /sys/class/dmi/id/product_name ] && SYS_PRODUCT=$(cat /sys/class/dmi/id/product_name 2>/dev/null | xargs)
[ -z "$SYS_SERIAL" ] && [ -f /sys/class/dmi/id/product_serial ] && SYS_SERIAL=$(cat /sys/class/dmi/id/product_serial 2>/dev/null | xargs)

[ -z "$SYS_VENDOR" ] && SYS_VENDOR="Unknown"
[ -z "$SYS_PRODUCT" ] && SYS_PRODUCT="Unknown / possibly a virtual machine"
[ -z "$SYS_SERIAL" ] && SYS_SERIAL="Unable to check (root privileges required)"

BOARD_VENDOR=""
BOARD_PRODUCT=""
if [ "$IS_ROOT" -eq 1 ] && [ -x "$(command -v $DMI_CMD)" ]; then
    BOARD_VENDOR=$($DMI_CMD -s baseboard-manufacturer 2>/dev/null | xargs)
    BOARD_PRODUCT=$($DMI_CMD -s baseboard-product-name 2>/dev/null | xargs)
fi
[ -z "$BOARD_VENDOR" ] && [ -f /sys/class/dmi/id/board_vendor ] && BOARD_VENDOR=$(cat /sys/class/dmi/id/board_vendor 2>/dev/null | xargs)
[ -z "$BOARD_PRODUCT" ] && [ -f /sys/class/dmi/id/board_name ] && BOARD_PRODUCT=$(cat /sys/class/dmi/id/board_name 2>/dev/null | xargs)
[ -z "$BOARD_VENDOR" ] && BOARD_VENDOR="Unknown"
[ -z "$BOARD_PRODUCT" ] && BOARD_PRODUCT="Unknown"

BIOS_VENDOR=""
BIOS_VERSION=""
BIOS_DATE=""
if [ "$IS_ROOT" -eq 1 ] && [ -x "$(command -v $DMI_CMD)" ]; then
    BIOS_VENDOR=$($DMI_CMD -s bios-vendor 2>/dev/null | xargs)
    BIOS_VERSION=$($DMI_CMD -s bios-version 2>/dev/null | xargs)
    BIOS_DATE=$($DMI_CMD -s bios-release-date 2>/dev/null | xargs)
fi
[ -z "$BIOS_VENDOR" ] && [ -f /sys/class/dmi/id/bios_vendor ] && BIOS_VENDOR=$(cat /sys/class/dmi/id/bios_vendor 2>/dev/null | xargs)
[ -z "$BIOS_VERSION" ] && [ -f /sys/class/dmi/id/bios_version ] && BIOS_VERSION=$(cat /sys/class/dmi/id/bios_version 2>/dev/null | xargs)
[ -z "$BIOS_DATE" ] && [ -f /sys/class/dmi/id/bios_date ] && BIOS_DATE=$(cat /sys/class/dmi/id/bios_date 2>/dev/null | xargs)
[ -z "$BIOS_VENDOR" ] && BIOS_VENDOR="Unknown"
[ -z "$BIOS_VERSION" ] && BIOS_VERSION="Unknown"
[ -z "$BIOS_DATE" ] && BIOS_DATE="Unknown"

# Hardware Info Print
ROW_VND=$(printf "  - Server Hardware Vendor    : %s" "$SYS_VENDOR")
ROW_PRD=$(printf "  - Server Hardware Model     : %s" "$SYS_PRODUCT")
ROW_SER=$(printf "  - Unique Serial No. (S/N)   : %s" "$SYS_SERIAL")
ROW_MBD=$(printf "  - Motherboard Model Info    : %s (%s)" "$BOARD_PRODUCT" "$BOARD_VENDOR")
ROW_BIO=$(printf "  - System BIOS Version Info  : %s (Release date: %s / Vendor: %s)" "$BIOS_VERSION" "$BIOS_DATE" "$BIOS_VENDOR")

log "$ROW_VND"
log "$ROW_PRD"
log "$ROW_SER"
log "$ROW_MBD"
log "$ROW_BIO"

# --- System Uptime Print ---
UP_SEC=$(awk '{print int($1)}' /proc/uptime)
UP_DAYS=$((UP_SEC/86400))
UP_HOURS=$(((UP_SEC%86400)/3600))
log "  - Uptime                    : ${UP_DAYS}days ${UP_HOURS}h"

###############################################################################
section "1. CPU Info & Usage Check"
###############################################################################
# [Fixed] Dedupe repeated model names, and join multiple distinct CPU types on one line separated by slashes
CPU_MODEL=$(lscpu 2>/dev/null | awk -F': ' '/Model name/{print $2}' | sort -u | sed 's/^[ \t]*//;s/[ \t]*$//' | paste -sd '/' - | sed 's/\// \/ /g')
[ -z "$CPU_MODEL" ] && CPU_MODEL=$(awk -F: '/model name/{print $2}' /proc/procinfo 2>/dev/null | sort -u | sed 's/^[ \t]*//;s/[ \t]*$//' | paste -sd '/' - | sed 's/\// \/ /g')
[ -z "$CPU_MODEL" ] && CPU_MODEL=$(awk -F: '/model name/{print $2}' /proc/cpuinfo | sort -u | sed 's/^[ \t]*//;s/[ \t]*$//' | paste -sd '/' - | sed 's/\// \/ /g')

VIRT_TYPE=""
has_cmd systemd-detect-virt && VIRT_TYPE=$(systemd-detect-virt 2>/dev/null)
if [ -z "$VIRT_TYPE" ] || [ "$VIRT_TYPE" = "none" ]; then
    CPU_ALLOC_TYPE="Physical CPU"
else
    CPU_ALLOC_TYPE="Virtual CPU (vCPU / ${VIRT_TYPE})"
fi

TOTAL_CPUS=$(lscpu 2>/dev/null | awk -F: '/^CPU\(s\):/{gsub(/ /,"",$2); print $2; exit}')
SOCKETS=$(lscpu 2>/dev/null   | awk -F: '/^Socket\(s\):/{gsub(/ /,"",$2); print $2; exit}')

# Fallback for Total CPUs & Sockets
[ -z "$TOTAL_CPUS" ] && TOTAL_CPUS=$(grep -c '^processor' /proc/cpuinfo)
[ -z "$SOCKETS" ] && SOCKETS=$(grep '^physical id' /proc/cpuinfo | sort -u | wc -l)
[ "$SOCKETS" -eq 0 ] && SOCKETS=1

# Calculate Physical Cores and Threads (Total & Per-Socket breakdown)
SOCKETS=$(lscpu 2>/dev/null  | awk -F: '/^Socket\(s\):/{gsub(/ /,"",$2); print $2; exit}')
[ -z "$SOCKETS" ] && SOCKETS=$(grep '^physical id' /proc/cpuinfo | sort -u | wc -l)
[ "$SOCKETS" -eq 0 ] && SOCKETS=1

CORES_PER_SOCKET=$(lscpu 2>/dev/null | awk -F: '/^Core\(s\) per socket/{gsub(/ /,"",$2); print $2; exit}')
if [ -z "$CORES_PER_SOCKET" ]; then
    CORES_PER_SOCKET=$(awk '/core id/{print $4}' /proc/cpuinfo | sort -u | wc -l)
fi
[ -z "$CORES_PER_SOCKET" ] || [ -z "$CORES_PER_SOCKET" ] && CORES_PER_SOCKET=1

# Total physical cores = Cores per socket × Sockets
TOTAL_CORES=$((CORES_PER_SOCKET * SOCKETS))
TOTAL_THREADS="$TOTAL_CPUS"

# Calculate per-socket thread count
THREADS_PER_SOCKET=$((TOTAL_THREADS / SOCKETS))

SOCKET_DETAIL=""
POPULATED=0
if has_cmd dmidecode && [ "$IS_ROOT" -eq 1 ]; then
    STATUS_LINES=$(dmidecode -t processor 2>/dev/null | grep "Status:")
    if [ -n "$STATUS_LINES" ]; then
        idx=0
        while IFS= read -r line; do
            idx=$((idx+1))
            if echo "$line" | grep -qi "Unpopulated"; then
                SOCKET_DETAIL="${SOCKET_DETAIL}S${idx}:Empty, "
            else
                POPULATED=$((POPULATED+1))
                SOCKET_DETAIL="${SOCKET_DETAIL}S${idx}:Populated, "
            fi
        done <<EOF_STATUS
$STATUS_LINES
EOF_STATUS
        SOCKET_DETAIL=${SOCKET_DETAIL%, }
    fi
fi
[ "$POPULATED" -eq 0 ] && POPULATED="$SOCKETS"
[ -z "$SOCKET_DETAIL" ] && SOCKET_DETAIL="Status check skipped"

# Pre-assemble all output lines with English labels
ROW_MODEL=$(printf "  - CPU Model                : %-s" "$CPU_MODEL")
ROW_TYPE=$(printf "  - Processor Allocation     : %-s" "$CPU_ALLOC_TYPE")

# Concise & informative format including per-socket details, core and thread numbers usiong C_GREEN and C_NC
ROW_CONFIG=$(printf "  - CPU Configuration        : ${C_GREEN}%s${C_NC}Core / ${C_GREEN}%s${C_NC}Thread (%s Sockets, ${C_GREEN}%s${C_NC}Core/${C_GREEN}%s${C_NC}Thread per socket) [%s]" "${TOTAL_CORES}" "${TOTAL_THREADS}" "${SOCKETS}" "${CORES_PER_SOCKET}" "${THREADS_PER_SOCKET}" "${SOCKET_DETAIL}")

log "$ROW_MODEL"
log "$ROW_TYPE"
log "$ROW_CONFIG"

log "  - Measuring CPU usage (takes about 10 seconds, please wait)..."
CPU_LINE1=$(awk '/^cpu /{print $2,$3,$4,$5,$6,$7,$8,$9}' /proc/stat)
set -- $CPU_LINE1
cu1=$1; cn1=$2; cs1=$3; ci1=$4; cio1=$5; cirq1=$6; csirq1=$7; cst1=$8
sleep 10
CPU_LINE2=$(awk '/^cpu /{print $2,$3,$4,$5,$6,$7,$8,$9}' /proc/stat)
set -- $CPU_LINE2
cu2=$1; cn2=$2; cs2=$3; ci2=$4; cio2=$5; cirq2=$6; csirq2=$7; cst2=$8

du=$((cu2-cu1)); dn=$((cn2-cn1)); ds=$((cs2-cs1)); di=$((ci2-ci1))
dio=$((cio2-cio1)); dirq=$((cirq2-cirq1)); dsirq=$((csirq2-csirq1)); dst=$((cst2-cst1))
total=$((du+dn+ds+di+dio+dirq+dsirq+dst))

if [ "$total" -gt 0 ]; then
    pct_user=$(awk -v a="$du" -v t="$total" 'BEGIN{printf "%.2f", (a/t)*100}')
    pct_sys=$(awk -v a="$ds" -v t="$total" 'BEGIN{printf "%.2f", (a/t)*100}')
    pct_io=$(awk -v a="$dio" -v t="$total" 'BEGIN{printf "%.2f", (a/t)*100}')
    pct_idle=$(awk -v a="$di" -v t="$total" 'BEGIN{printf "%.2f", (a/t)*100}')
    pct_total=$(awk -v idle="$pct_idle" 'BEGIN{printf "%.2f", 100-idle}')
else
    pct_user=0.00; pct_sys=0.00; pct_io=0.00; pct_total=0.00
fi

ROW_USAGE=$(printf "  - Average CPU Usage       : %s%% (User: %s%%, Sys: %s%%, IO_Wait: %s%%)" "${pct_total}" "${pct_user}" "${pct_sys}" "${pct_io}")
log "$ROW_USAGE"

###############################################################################
section "2. Memory Info & Usage Check"
###############################################################################
MEM_TOTAL_KB=$(awk '/^MemTotal:/{print $2}' /proc/meminfo)
MEM_AVAIL_KB=$(awk '/^MemAvailable:/{print $2}' /proc/meminfo)
MEM_TOTAL_MB=$((MEM_TOTAL_KB/1024))
MEM_AVAIL_MB=$((MEM_AVAIL_KB/1024))
MEM_USED_MB=$((MEM_TOTAL_MB-MEM_AVAIL_MB))
MEM_USED_PCT=$(awk -v u="$MEM_USED_MB" -v t="$MEM_TOTAL_MB" 'BEGIN{printf "%.2f", (u/t)*100}')

log "  - Total: ${MEM_TOTAL_MB} MB / Used: ${MEM_USED_MB} MB (${MEM_USED_PCT}%) / Available: ${MEM_AVAIL_MB} MB"
log "  - Physical memory bank population:"
if has_cmd dmidecode && [ "$IS_ROOT" -eq 1 ]; then
    BANK_INFO=$(dmidecode -t memory 2>/dev/null | awk '
        /Memory Device$/{loc="";size=""}
        /^[ \t]*Size:/{gsub(/^[ \t]*Size:[ \t]*/,""); size=$0}
        /^[ \t]*Locator:/ && !/Bank Locator/{gsub(/^[ \t]*Locator:[ \t]*/,""); loc=$0}
        /^$/{ if (loc!="" && size!="" && size !~ /No Module/) print loc"|"size }
    ')
    if [ -n "$BANK_INFO" ]; then
        echo "$BANK_INFO" | while IFS='|' read -r loc size; do
            log "    ▶ Bank Location : $loc | Installed Capacity : $size"
        done
    else
        log "    (No populated bank info found)"
    fi
else
    log "    (Unable to check - dmidecode requires root)"
fi

SWAP_TOTAL_KB=$(awk '/^SwapTotal:/{print $2}' /proc/meminfo)
SWAP_FREE_KB=$(awk '/^SwapFree:/{print $2}' /proc/meminfo)
SWAP_TOTAL_MB=$((SWAP_TOTAL_KB/1024))
SWAP_FREE_MB=$((SWAP_FREE_KB/1024))
SWAP_USED_MB=$((SWAP_TOTAL_MB-SWAP_FREE_MB))
log "  - Swap : Total ${SWAP_TOTAL_MB} MB / Used ${SWAP_USED_MB} MB / Free ${SWAP_FREE_MB} MB"

###############################################################################
section "3. GPU Device Check"
###############################################################################
# 1. Pre-scan for GPU chipset devices at the physical bus level (including Intel/AMD integrated graphics)
GPU_DETECTED=$(lspci 2>/dev/null | grep -iE "vga|3d|nvidia|amd|radeon|tesla|quadro|geforce|intel.*graphics")

if [ -n "$GPU_DETECTED" ]; then
    log "  [GPU Hardware Device Info]"
    
    # List actual GPU card hardware plugged into the physical bus with integrated/discrete classification
    echo "$GPU_DETECTED" | while read -r g_line; do
        gpu_bus_name=$(echo "$g_line" | awk -F': ' '{print $2}')
        
        # 외장(Discrete)과 내장(Integrated) 구분 로직
        if echo "$g_line" | grep -q -iE "nvidia|tesla|quadro|geforce"; then
            log "    ▶ External GPU (Discrete): $gpu_bus_name"
        elif echo "$g_line" | grep -q -iE "intel"; then
            log "    ▶ Internal GPU (Integrated): $gpu_bus_name"
        elif echo "$g_line" | grep -q -iE "amd|radeon|ati"; then
            # AMD의 경우 외장인지 내장인지 추가 판별 (보통 3D controller이거나 라데온 외장은 별도 분기 가능)
            if echo "$g_line" | grep -q -i "3d controller"; then
                log "    ▶ External GPU (Discrete - AMD): $gpu_bus_name"
            else
                log "    ▶ GPU Device (AMD/ATI): $gpu_bus_name"
            fi
        else
            log "    ▶ Physical device: $gpu_bus_name"
        fi
    done

    # 2. Precisely trace whether the NVIDIA GPU control tool (nvidia-smi) is present, and its absolute path
    NV_SMI=""
    if [ -x "$(command -v nvidia-smi)" ]; then NV_SMI="nvidia-smi"
    elif [ -x "/usr/bin/nvidia-smi" ]; then NV_SMI="/usr/bin/nvidia-smi"
    elif [ -x "/usr/local/cuda/bin/nvidia-smi" ]; then NV_SMI="/usr/local/cuda/bin/nvidia-smi"; fi

    if [ -n "$NV_SMI" ]; then
        # Use a CSV field query for broad compatibility, accounting for older nvidia-smi versions such as on CentOS 6.9
        NV_RAW=$($NV_SMI --query-gpu=index,name,driver_version,temperature.gpu,power.draw,utilization.gpu,utilization.memory,memory.used,memory.total --format=csv,noheader,nounits 2>/dev/null)
        
        if [ -n "$NV_RAW" ]; then
            log ""
            log "  [NVIDIA GPU Real-Time Specs & Status]"
            # Build the header with left-aligned widths matched precisely so the table doesn't break
            HEADER_STR=$(printf "    %-4s %-22s %-12s %-7s %-9s %-9s %-15s" "IDX" "GPU Model" "Driver" "Temp" "Power" "GPU%%" "VRAM(Used/Total)")
            log "$HEADER_STR"
            log "    ----------------------------------------------------------------------------------------"
            
            echo "$NV_RAW" | while IFS=',' read -r idx name drv temp pwr gpu_util mem_util mem_used mem_total; do
                # Trim whitespace and clean up character count
                idx=$(echo "$idx" | xargs)
                name=$(echo "$name" | xargs | cut -c1-22) # Truncate to 22 chars since an overly long model name would break the table layout
                drv=$(echo "$drv" | xargs)
                temp=$(echo "$temp" | xargs)"°C"
                pwr=$(echo "$pwr" | xargs)"W"
                gpu_util=$(echo "$gpu_util" | xargs)"%"
                
                # Assemble the memory (VRAM) format (e.g. 1024/8192 MB)
                vram_info=$(printf "%.0f/%.0f MB" "$mem_used" "$mem_total")
                
                # Pre-assemble with printf according to the alignment rules, then pass it safely to the log function
                ROW_STR=$(printf "    %-4s %-22s %-12s %-7s %-9s %-9s %-15s" "$idx" "$name" "$drv" "$temp" "$pwr" "$gpu_util" "$vram_info")
                log "$ROW_STR"
                
                # [Threshold alert safeguard] Flag a fault if GPU temperature exceeds 82°C or a hardware error code is detected
                if [ -n "$temp" ] && [ "${temp%°C}" -gt 82 ] 2>/dev/null; then
                    HW_STATUS="Fault"
                    HW_DETAIL_LIST+=("GPU [IDX:$idx] core temperature exceeded threshold (${temp})")
                fi
            done
        else
            log ""
            log "    ⚠️ Notice: The NVIDIA driver kernel module did not load correctly, or the device is temporarily unresponsive."
        fi
    else
        log ""
        # Guidance for when the device is present but the driver/CUDA Toolkit was never built at all
        if echo "$GPU_DETECTED" | grep -q -i "nvidia"; then
            log "    ⚠️ Notice: An NVIDIA GPU card is installed on the motherboard, but the dedicated driver and management tool (nvidia-smi) aren't installed, so real-time temperature can't be measured."
        elif echo "$GPU_DETECTED" | grep -q -iE "amd|radeon"; then
            log "    ℹ️ Notice: An AMD-family GPU device was detected. (Requires rocm-smi integration on CentOS 6.9 environments)"
        fi
    fi
else
  log "  - Accelerator (GPU) : No standalone hardware GPU device is running on this system."
fi

###############################################################################
section "4. Network Status Check"
###############################################################################
log "  [Status of All Installed NICs]"

# Collect physical, bonding, and bridge virtual interfaces, excluding the loopback (lo)
PHYS_IFACES=""
for ifpath in /sys/class/net/*; do
    ifname=$(basename "$ifpath")
    [ "$ifname" = "lo" ] && continue
    
    # [Fixed] Recognize physical (device), bonding, and bridge interfaces, all together
    [ -e "$ifpath/device" ] || [ -e "$ifpath/bonding" ] || [ -e "$ifpath/bridge" ] || [ -e "$ifpath/upper_bond0" ] || continue
    PHYS_IFACES="$PHYS_IFACES $ifname"

    # 1. Check link up/down status
    state=$(cat "$ifpath/operstate" 2>/dev/null)
    case "$state" in
        up)   state_disp="${C_GREEN}[UP]${C_NC}" ;;
        down) state_disp="${C_RED}[DOWN]${C_NC}" ;;
        *)    state_disp="[${state:-UNKNOWN}]" ;;
    esac

    # 2. Check link speed (bridges/virtual devices have variable or no speed, so handle as a guide value)
    speed=$(cat "$ifpath/speed" 2>/dev/null)
    if [ -z "$speed" ] || [ "$speed" -lt 0 ] 2>/dev/null || [ "$speed" -eq 4294967295 ] 2>/dev/null; then
        speed_disp="Virtual/N/A"
    else
        speed_disp="${speed}Mb/s"
    fi

    # 3. Extract IP(s), supporting multiple IPs and bonding/bridge setups (aligns whitespace around the slash)
    ip_addr=$(ip -4 addr show "$ifname" 2>/dev/null | awk '/inet /{print $2}' | cut -d/ -f1 | sort -u | paste -sd '/' - | sed 's/\// \/ /g')
    [ -z "$ip_addr" ] && ip_addr="None"

    # Pre-assemble with printf for readable vertical table alignment
    ROW_STR=$(printf "    - Interface: %-12s | Status : %-15s | Speed: %-13s | IP: %s" "$ifname" "$state_disp" "$speed_disp" "$ip_addr")
    log "$ROW_STR"
done

log ""
log "  [List of Active Physical/Virtual NICs]"
ACTIVE_FOUND=0
for ifname in $PHYS_IFACES; do
    state=$(cat "/sys/class/net/$ifname/operstate" 2>/dev/null)
    if [ "$state" = "up" ]; then
        speed=$(cat "/sys/class/net/$ifname/speed" 2>/dev/null)
        if [ -z "$speed" ] || [ "$speed" -lt 0 ] 2>/dev/null || [ "$speed" -eq 4294967295 ] 2>/dev/null; then
            speed_disp="Virtual/N/A"
        else
            speed_disp="${speed}Mb/s"
        fi
        ROW_ACTIVE=$(printf "    ▶ %-12s : %s" "$ifname" "$speed_disp")
        log "$ROW_ACTIVE"
        ACTIVE_FOUND=1
    fi
done
[ "$ACTIVE_FOUND" -eq 0 ] && log "    (No active NICs)"

log ""
log "  [Network Device Info (Model / Status / Fault Cause)]"
for ifname in $PHYS_IFACES; do
    model="Unknown"
    
    # Guide-mapping for the model name by device type
    if [ -e "/sys/class/net/$ifname/bridge" ]; then
        model="Linux Virtual Network Bridge"
    elif [ -e "/sys/class/net/$ifname/bonding" ]; then
        model="Bonding Virtual Interface"
    elif has_cmd ethtool; then
        busaddr=$(ethtool -i "$ifname" 2>/dev/null | awk -F': ' '/bus-info/{print $2}')
        if [ -n "$busaddr" ] && has_cmd lspci; then
            model=$(lspci -s "$busaddr" 2>/dev/null | cut -d: -f3- | sed 's/^ *//')
            [ -z "$model" ] && model="Unknown"
        fi
    fi
    
    state=$(cat "/sys/class/net/$ifname/operstate" 2>/dev/null)
    if [ "$state" = "up" ]; then
        ROW_DEV=$(printf "    ▶ %-12s [%-45s] : ${C_GREEN}Normal${C_NC}" "$ifname" "$model")
        log "$ROW_DEV"
    else
        carrier=$(cat "/sys/class/net/$ifname/carrier" 2>/dev/null)
        if [ -z "$carrier" ] || [ "$carrier" = "0" ]; then
            cause="Cable not connected or link down"
        else
            cause="Disabled by administrator (admin down)"
        fi
        ROW_DEV=$(printf "    ▶ %-12s [%-45s] : ${C_RED}Fault${C_NC} (Cause: %s)" "$ifname" "$model" "$cause")
        log "$ROW_DEV"
    fi
done

log ""
log "  [Ping Test]"
GATEWAY=$(ip route 2>/dev/null | awk '/^default/{print $3; exit}')
for target in "$GATEWAY" "8.8.8.8"; do
    [ -z "$target" ] && continue
    if ping -c 2 -W 2 "$target" >/dev/null 2>&1; then
        ROW_PING=$(printf "    - %-15s : ${C_GREEN}Normal${C_NC}" "$target")
        log "$ROW_PING"
    else
        ROW_PING=$(printf "    - %-15s : ${C_RED}Fault${C_NC}" "$target")
        log "$ROW_PING"
    fi
done

log ""
log "  [Current Session Info (netstat -na summary)]"
NS_CMD=""
if has_cmd netstat; then
    NS_CMD="netstat -na"
elif has_cmd ss; then
    NS_CMD="ss -ant"
fi
if [ -n "$NS_CMD" ]; then
    NS_OUT=$($NS_CMD 2>/dev/null)
    ESTAB=$(echo "$NS_OUT" | grep -c ESTABLISHED)
    LISTEN=$(echo "$NS_OUT" | grep -c LISTEN)
    TIMEWAIT=$(echo "$NS_OUT" | grep -c TIME_WAIT)
    TOTAL=$(echo "$NS_OUT" | grep -Ec "^(tcp|udp)")
    log "    - Total sessions (tcp/udp): $TOTAL / ESTABLISHED: $ESTAB / LISTEN: $LISTEN / TIME_WAIT: $TIMEWAIT"
else
    log "    (netstat/ss command not found)"
fi

###############################################################################
section "5. Routing Table Info"
###############################################################################
log "  [Configured Routing Table]"
if has_cmd ip; then
    RT_OUT=$(ip route 2>/dev/null)
else
    RT_OUT=$(netstat -rn 2>/dev/null)
    RT_OUT=$(netstat -rn 2>/dev/null)
fi
echo "$RT_OUT" | while read -r line; do
    log "    $line"
done

if echo "$RT_OUT" | grep -q "^default"; then
    log "  - Status : ${C_GREEN}Normal${C_NC} (default gateway configured)"
else
    log "  - Status : ${C_RED}Fault${C_NC} (no default gateway)"
fi

###############################################################################
section "6. Disk Usage & I/O Check"
###############################################################################
log "  [Filesystem (df -h) Status] (shown in red when usage is 80% or higher)"
df -h --output=source,fstype,size,used,avail,pcent,target 2>/dev/null | tail -n +2 | while read -r line; do
    pct=$(echo "$line" | awk '{print $6}' | tr -d '%')
    if [ -n "$pct" ] && [ "$pct" -ge 80 ] 2>/dev/null; then
        log "    ${C_RED}${line}${C_NC}"
    else
        log "    ${line}"
    fi
done

log ""
log "  [VM / Image Storage Space (/mnt, /var/lib/libvirt, etc.)]"
VM_STORAGE=$(df -h 2>/dev/null | awk '$NF ~ /^\/(mnt|var\/lib\/libvirt|vz|data)/{print}')
if [ -n "$VM_STORAGE" ]; then
    echo "$VM_STORAGE" | while read -r line; do
        log "    $line"
    done
else
    log "    (No such mount found)"
fi

log ""
log "  [Average Physical Disk I/O (TPS)]"
if has_cmd iostat; then
    iostat -d 2 2 2>/dev/null | awk -v red="$C_RED" -v nc="$C_NC" '
        /^Device/{blk++; next}
        blk==2 && NF>0 {printf "    - %-12s tps: %.2f\n",$1,$2}
    '
else
    log "    (iostat command not found - install the sysstat package)"
fi

###############################################################################
section "7. Storage Allocation Check"
###############################################################################
log "  [Multipath / LUN Allocation Info]"
if has_cmd multipath; then
    MP_LIST=$(multipath -ll 2>/dev/null | awk '/^[a-zA-Z0-9_-]+ \(/{print $1}')
    if [ -n "$MP_LIST" ]; then
        idx=0
        echo "$MP_LIST" | while read -r mpname; do
            idx=$((idx+1))
            lun_num=$(printf "%05d" "$idx")
            mnt=""
            has_cmd findmnt && mnt=$(findmnt -n -S "/dev/mapper/$mpname" 2>/dev/null | awk '{print $1}')
            [ -z "$mnt" ] && has_cmd lsblk && mnt=$(lsblk -no MOUNTPOINT "/dev/mapper/$mpname" 2>/dev/null | grep -v '^$' | head -1)
            [ -z "$mnt" ] && mnt="(Not mounted)"
            log "    ▶ ${mpname}(LUN-${lun_num}) : $mnt"
        done
    else
        log "    (No multipath devices configured)"
    fi
else
    log "    (Multipath not in use, or device-mapper-multipath not installed)"
fi

log ""
log "  [NFS Mount Info]"
NFS_MOUNTS=$(mount 2>/dev/null | grep -E "type nfs")
if [ -n "$NFS_MOUNTS" ]; then
    echo "$NFS_MOUNTS" | while read -r line; do
        log "    $line"
    done
else
    log "    (No NFS mounts)"
fi

###############################################################################
section "8. Database Status Check"
###############################################################################
declare -A DB_CHECKS=(
    # Databases (foreign and Korean)
    [ "Oracle DB" ]="oracle tnslsnr"
    [ "MySQL / MariaDB" ]="mysqld mariadb"
    [ "PostgreSQL" ]="postgres"
    [ "Tmax Tibero (Korean)" ]="tbboot tbsvr"
    [ "Altibase (Korean)" ]="altibase altiserver"
    [ "Cubrid (Korean)" ]="cubrid"
    [ "Goldilocks (Korean, in-memory)" ]="goldilocks golas"
    [ "Redis" ]="redis-server"
    [ "MongoDB" ]="mongod"
    [ "Microsoft SQL Server" ]="sqlservr"
    [ "IBM DB2" ]="db2sysc"
    [ "Elasticsearch" ]="elasticsearch elastic+ org.elasticsearch"
    [ "Apache Cassandra" ]="cassandra"
    [ "InfluxDB" ]="influxd"
)

FOUND_DB=0
declare -A RUNNING_DB_PROCS

# 1. Running DB Check
for dbname in "${!DB_CHECKS[@]}"; do
    for proc in ${DB_CHECKS[$dbname]}; do
        if pgrep -x "$proc" >/dev/null 2>&1 || pgrep -f "$proc" >/dev/null 2>&1; then
            log "  - DB : $dbname (process: $proc) - ${C_GREEN}Running${C_NC}"
            FOUND_DB=1
            RUNNING_DB_PROCS["$proc"]="$dbname"
            break
        fi
    done
done
[ "$FOUND_DB" -eq 0 ] && log "  - No installed/running DB solution was detected."

# 2. Database Active Port Output (Precise PID Matching))
log ""
log "  [Database Active Network Ports]"

if [ "$FOUND_DB" -eq 1 ]; then
    # Cache network commands based on the environment (ss first, fallback to netstat)
    if command -v ss >/dev/null 2>&1; then
        NET_OUT=$(ss -tlnp 2>/dev/null)
        USE_CMD="ss"
    elif command -v netstat >/dev/null 2>&1; then
        NET_OUT=$(netstat -tlnp 2>/dev/null)
        USE_CMD="netstat"
    else
        log "    (Neither 'ss' nor 'netstat' command found - unable to check ports)"
        USE_CMD=""
    fi

    if [ -n "$USE_CMD" ]; then
        for proc in "${!RUNNING_DB_PROCS[@]}"; do
            dbname="${RUNNING_DB_PROCS[$proc]}"
            
            # Extract all PIDs of the corresponding process
            pids=$(pgrep -x "$proc" 2>/dev/null || pgrep -f "$proc" 2>/dev/null)
            
            found_ports=""
            for pid in $pids; do
                if [ "$USE_CMD" = "ss" ]; then
                    # Match PIDs from ss output and precisely extract only the port numbers (after the last colon)
                    ports=$(echo "$NET_OUT" | grep ",pid=${pid}," | awk '{print $4}' | rev | cut -d: -f1 | rev | grep -E '^[0-9]+$')
                else
                    # Match PIDs from netstat output
                    ports=$(echo "$NET_OUT" | grep "${pid}/" | awk '{print $4}' | rev | cut -d: -f1 | rev | grep -E '^[0-9]+$')
                fi
                found_ports="$found_ports $ports"
            done
            
            #Deduplicate and comma-separate multi-ports
            unique_ports=$(echo "$found_ports" | tr ' ' '\n' | grep -v '^$' | sort -un | tr '\n' ',' | sed 's/,$//')
            
            if [ -n "$unique_ports" ]; then
                log "    - ${C_GREEN}[$dbname] $proc${C_NC} : $unique_ports"
            fi
        done
    fi
fi

###############################################################################
section "9. Virtualization & VM Check"
###############################################################################
# 1. Detect the basic server type (physical vs virtual)
VIRT=""
if has_cmd systemd-detect-virt; then
    VIRT=$(systemd-detect-virt 2>/dev/null)
elif has_cmd virt-what; then
    VIRT=$(virt-what 2>/dev/null | tail -n1)
fi

if [ -z "$VIRT" ] || [ "$VIRT" = "none" ]; then
    log "  - Server Type : [Physical Server (Bare-metal)]"
else
    log "  - Server Type : [Virtual Server (Guest, type: $VIRT)]"
fi

# 2. Detailed KVM hardware and kernel-level check
log "  - KVM Hypervisor Internal Check:"

# 2-1. CPU virtualization technology support
if grep -E -q '(vmx|svm)' /proc/cpuinfo; then
    log "    ▶ CPU Virtualization Acceleration (VT-x/AMD-V) : ${C_GREEN}Supported${C_NC}"
else
    log "    ▶ CPU Virtualization Acceleration (VT-x/AMD-V) : [Not supported, or disabled in BIOS]"
fi

# 2-2. KVM kernel module status
if lsmod | grep -q 'kvm_intel' || lsmod | grep -q 'kvm_amd'; then
    log "    ▶ KVM Kernel Acceleration Module : ${C_GREEN}Loaded (Normal)${C_NC}"
elif lsmod | grep -q 'kvm'; then
    log "    ▶ KVM Base Kernel Module         : [Loaded / need to check acceleration module]"
else
    log "    ▶ KVM Kernel Module              : [Not loaded - KVM acceleration unavailable]"
fi

# 2-3. KVM device file activation status
if [ -c /dev/kvm ]; then
    log "    ▶ /dev/kvm Device File           : ${C_GREEN}Active${C_NC}"
else
    log "    ▶ /dev/kvm Device File           : [Missing, or a permissions error]"
fi

# 3. Check whether KVM management services are installed/running (supports CentOS 6 sysvinit)
KVM_INSTALLED="Not installed"
if has_cmd virsh || (has_cmd rpm && rpm -q libvirt >/dev/null 2>&1) || (has_cmd dpkg && dpkg -l 2>/dev/null | grep -q libvirt-daemon); then
    KVM_INSTALLED="Installed"
fi

KVM_RUNNING=""
if has_cmd systemctl; then
    systemctl is-active libvirtd >/dev/null 2>&1 && KVM_RUNNING=" / Running"
elif [ -x /etc/init.d/libvirtd ]; then
    /etc/init.d/libvirtd status >/dev/null 2>&1 && KVM_RUNNING=" / Running"
fi
log "  - Virtualization Control Tool : [libvirt(virsh) ${KVM_INSTALLED}${KVM_RUNNING}]"

# 4. Check the list of KVM-based guest VMs and their allocated resources
log "  [Guest VM List & Allocated Resources]"
if has_cmd virsh; then
    # Robust text extraction matching the old virsh output format on CentOS 6.9 (strip header and blank lines)
    VM_RAW_LIST=$(virsh list --all 2>/dev/null | tail -n +3 | sed '/^$/d')
    
    if [ -n "$VM_RAW_LIST" ]; then
        # Define column format (ID, Name, State, Allocated CPU, Allocated Memory, Max Allocated Disk)
        # Define column format (ID, Name, State, Allocated CPU, Allocated Memory, Max Allocated Disk)
        HEADER_STR=$(printf "    %-7s %-20s %-12s %-12s %-15s %-15s" "ID" "VM Name" "State" "Alloc. vCPU" "Alloc. Memory" "Alloc. Disk")
        log "$HEADER_STR"
        log "    ------------------------------------------------------------------------------------------------"
        
        while read -r raw_line; do
            [ -z "$raw_line" ] && continue
            
            # 1. Extract ID and state
            v_id=$(echo "$raw_line" | awk '{print $1}')
            if echo "$raw_line" | grep -q "shut off"; then
                v_state="shut off"
            elif echo "$raw_line" | grep -q "running"; then
                v_state="running"
            elif echo "$raw_line" | grep -q "paused"; then
                v_state="paused"
            else
                v_state=$(echo "$raw_line" | awk '{print $NF}')
            fi
            
            # 2. Extract VM name
            v_name=$(echo "$raw_line" | sed "s/^$v_id//" | sed "s/$v_state$//" | xargs)
            
            # 3. Extract total resources allocated by the host (using dominfo and domblkinfo)
            v_info=$(virsh dominfo "$v_name" 2>/dev/null)
            
            # Total allocated vCPU count
            alloc_cpu=$(echo "$v_info" | grep -E '^CPU\(s\):' | awk '{print $2}')
            [ -z "$alloc_cpu" ] && alloc_cpu="N/A" || alloc_cpu="${alloc_cpu} vCPU"
            
            # Max allocated memory size (converted from KB to MB)
            max_mem_kb=$(echo "$v_info" | grep -E '^Max memory:' | awk '{print $3}')
            if [ -n "$max_mem_kb" ] && [ "$max_mem_kb" -gt 0 ]; then
                alloc_mem="$((max_mem_kb / 1024)) MB"
            else
                alloc_mem="N/A"
            fi
            
            # Max allocated virtual disk capacity (extract the Capacity metric and convert to GB)
            alloc_disk="N/A"
            disk_target=$(virsh domblklist "$v_name" 2>/dev/null | tail -n +3 | awk '{print $1}' | grep -v '^$' | head -n1)
            if [ -n "$disk_target" ]; then
                disk_cap=$(virsh domblkinfo "$v_name" "$disk_target" 2>/dev/null | grep "Capacity:" | awk '{print $2}')
                if [ -n "$disk_cap" ] && [ "$disk_cap" -gt 0 ]; then
                    # Convert bytes to GB
                    alloc_disk=$(awk -v cap="$disk_cap" 'BEGIN {printf "%.0f GB", cap / 1024 / 1024 / 1024}')
                fi
            fi
            
            # Pass to output matching the alignment format
            ROW_STR=$(printf "    %-7s %-20s %-12s %-12s %-15s %-15s" "$v_id" "$v_name" "$v_state" "$alloc_cpu" "$alloc_mem" "$alloc_disk")
            log "$ROW_STR"
            
        done <<EOF
$VM_RAW_LIST
EOF
    else
        log "    (No registered VMs)"
    fi
else
    log "    (virsh command not found - unable to check)"
fi

log ""
# 5. Check the running status of major domestic/foreign virtualization / VDI / container services
log "  [Other Virtualization Platforms & VDI Service Status]"
# Kept as a declare form to preserve compatibility with the default BASH version (4.1.x) on CentOS 6.9
declare -A VIRT_CHECKS
VIRT_CHECKS[ "VMware vSphere/ESXi" ]="vmware hostd vpxa vmtoolsd"
VIRT_CHECKS[ "Citrix Apps & Desktops" ]="ctx vda ctxhdx"
VIRT_CHECKS[ "Docker Container" ]="dockerd docker-proxy"
VIRT_CHECKS[ "Kubernetes Node" ]="kubelet kube-proxy"
VIRT_CHECKS[ "Hanwith HDaaS (Korean VDI)" ]="hdaas hdaas-"
VIRT_CHECKS[ "Tmax CloudSpace / HyperZone" ]="hyperzone tmaxcloud"
VIRT_CHECKS[ "Infranics Infravirt" ]="infravirt"
VIRT_CHECKS[ "TilkoBlaze / Dstation (Korean VDI)" ]="dstation tilko vdimgr"
VIRT_CHECKS[ "AhnLab MDS Virtual Machine" ]="mdsvmid"

VIRT_FOUND=0
for virtname in "${!VIRT_CHECKS[@]}" ; do
    for proc in ${VIRT_CHECKS[$virtname]}; do
        if pgrep -x "$proc" >/dev/null 2>&1 || pgrep -f "$proc" >/dev/null 2>&1; then
            log "    ▶ $virtname : ${C_GREEN}Running${C_NC}"
            VIRT_FOUND=1
            break
        fi
    done
done
[ $VIRT_FOUND -eq 0 ] && log "    (No major domestic/foreign virtualization or VDI service detected)"

###############################################################################
section "10. Software & Service Port Check"
###############################################################################
log "  [Running Status]"
declare -A SVC_CHECKS=(
    # ==========================================
    # 1. System Access Control & Secure OS
    # ==========================================
    [ "Hunesion i-oneNGS (Access Control)" ]="ngsagent ngsd"
    [ "SGA Solutions RedCastle (Secure OS)" ]="rc_daemon rc_monitor"
    [ "PNPsecure DBSAFER (DB/Server Access)" ]="dbs_agent dbstecd"
    [ "Netand HiGuard / APPM (Password/Access)" ]="higuard appm_daemon"
	[ "PNPsecure DBSAFER" ]="dbs_agent dbstecd dbsd"
    [ "Netand HiGuard/APPM" ]="higuard appm_daemon"
    [ "Secuve iGIN" ]="igin topperware"
    [ "CyberArk PAM" ]="epmagent psmagent"
    [ "BeyondTrust" ]="pb.agent privilege_manager"
    [ "Teleport (Access Plane)" ]="teleport"
    [ "Apache Guacamole (Gateway)" ]="guacd"
    [ "HashiCorp Boundary" ]="boundary"
    [ "OpenSSH (Standard)" ]="sshd"
	[ "Cockpit (Web Management)" ]="cockpit-bridge"
	[ "Mosh (Mobile Shell)" ]="mosh-server"

    # ==========================================
    # 2. Network Separation & Security
    # ==========================================
    [ "Hunesion i-oneNet (Network Link)" ]="ionenet"
    [ "Shinhwa Intertek CrossGate (Network Link)" ]="crossgate netlink_d"
    [ "PentaSecurity WAPPLES (WAF)" ]="wapples_agent wapples"
    [ "AXGATE VPN / Firewall Agent" ]="axgate_agent axgate_vpn"
    [ "INCAP Web Firewall" ]="incapguard"
	[ "Hunesion i-oneEX (Data Transfer)" ]="ioneex_agent ioneex_d"
    [ "General File/Data Link Agent" ]="trans_agent linkagent"
	[ "Wazuh Agent" ]="wazuh-agentd"
    [ "OSSEC" ]="ossec-execd ossec-agentd"
    [ "Fail2Ban" ]="fail2ban-server"
    [ "OpenSCAP (Scanner)" ]="oscap"
	[ "HAProxy" ]="haproxy"
	[ "Keepalived" ]="keepalived"
    [ "Corosync" ]="corosync"
    [ "Pacemaker" ]="pacemakerd attrd stonithd"

    # ==========================================
    # 3. Backup & Recovery
    # ==========================================
    [ "Veritas NetBackup" ]="bpcd vnetd pnbatd"
    [ "Veeam Agent for Linux" ]="veeamservice veeamconfig"
    [ "Commvault" ]="cvd cvlaunchd ClSArachnid"
    [ "Veritas Backup Exec (RALUS)" ]="beremote"
    [ "Arcserve UDP Agent" ]="d2dserver d2d_ea"
    [ "Bacula / Bareos File Daemon" ]="bacula-fd bareos-fd"
    [ "UrBackup Client/Server" ]="urbackupsrv urbackupclientbackend"

    # ==========================================
    # 4. EDR and Anti-Virus & Encryption
    # ==========================================
    [ "AhnLab V3 Office Security / EDR" ]="v3d v3med v3spamd asmd"
    [ "Trend Micro Deep Security Agent" ]="ds_agent"
    [ "Fasoo DRM / SoftCamp Document Security" ]="fsd scds_d"
    [ "Fasoo / Softcamp Crypto" ]="fscrypto sc_cryptod"
    [ "MarkAny Content Security" ]="macs_d"

    # ==========================================
    # 5. DB Encryption & DLP
    # ==========================================
    [ "KSign / Sinsayway DB Crypto" ]="securedb_agent petra_agent"
    [ "Enterprise DLP Agent" ]="dlp_agent pc_filterd"
	[ "KSign SecureDB" ]="securedb_agent ksign_d"
    [ "Sinsayway Petra" ]="petra_agent petrad"
    [ "PentaSecurity D'Amo" ]="damo_agent damod"
    [ "Thales Vormetric (CipherTrust)" ]="voradmin secfsd vte"
    [ "IBM Guardium" ]="guardium_bundle gsvr"
	[ "Somansa DLP/Privacy-i" ]="somansa privacyi dlpi"
    [ "Fasoo DRM/DLP" ]="fsd fasoo_agent"
    [ "Softcamp Security" ]="scds_d sc_cryptod"
    [ "MarkAny Content Security" ]="macs_d macs_agent"
    [ "Symantec/Broadcom DLP" ]="edpa wdp"
    [ "McAfee/Trellix DLP" ]="masvc mfedlp"
    [ "Digital Guardian" ]="dg_agent dg_service"

    # ==========================================
    # 6. Vulnerability & Privacy
    # ==========================================
    [ "JiranSecurity ServerFilter (Privacy)" ]="sfagent serverfilter"
    [ "LSware SecuMS / OmniGuard" ]="secums_agent ogagent"
    [ "SGA Solutions TrustLine / RedEye" ]="trustline redeye_d"

    # ==========================================
    # 7. NAC
    # ==========================================
    [ "Genians NAC (Korean)" ]="gni_agent gni_nac genca"
    [ "Cisco ISE Agent / Supplicant" ]="cisco-ise-agent acdaemon"
    [ "Fortinet FortiNAC Agent" ]="fortinac_agent"
    [ "Aruba ClearPass Agent" ]="clearpass_agent onguard"
    [ "Secuve iGIN / Topperware" ]="igin topperware"

    # ==========================================
    # 8. APM Monitoring & SIEM
    # ==========================================
    [ "Zabbix Agent" ]="zabbix_agentd zabbix_agent2"
    [ "Zabbix Server" ]="zabbix_server"
    [ "Jennifer APM" ]="jennifer"
    [ "WhaTap Agent" ]="whatap"
    [ "Splunk Universal Forwarder" ]="splunkd"
    [ "Datadog Agent" ]="datadog-agent"
    [ "Igloo Corporation SPiDER TM Agent" ]="spider-agent spider_agent igloo_agent"
	[ "Telegraf" ]="telegraf"

    # ==========================================
    # 9. Web / WAS
    # ==========================================
    [ "Apache(httpd)" ]="httpd apache2"
    [ "Nginx" ]="nginx"
    [ "Tomcat" ]="catalina tomcat"
    [ "JBoss/Wildfly" ]="jboss wildfly"
    [ "Tmax JEUS" ]="jeus"
    [ "Tmax WebtoB" ]="webtob hth wsadmin"
    [ "IBM WebSphere" ]="websphere"
    [ "Oracle WebLogic" ]="weblogic"
    [ "Docker Engine" ]="dockerd"
    [ "Kubernetes Kubelet" ]="kubelet"
    [ "Containerd / CRI-O" ]="containerd cri-o"
    [ "Lighttpd / Caddy" ]="lighttpd caddy"
    [ "Node.js Application" ]="node"
    [ "Java Application (Spring, etc.)" ]="java"
	
	# ==========================================
    # 10. Remote Access & Terminal Solutions (Added)
    # ==========================================
    [ "Telnet Server" ]="in.telnetd telnetd"
    [ "SSH Server" ]="sshd"
    [ "FTP Server" ]="vsftpd proftpd pure-ftpd ftpd"
	[ "AnyDesk" ]="anydesk"
	[ "TeamViewer" ]="teamviewerd"
	
	# ==========================================
    # 11. Additional Enterprise Solutions (Recommended)
    # ==========================================
    [ "PentaSecurity PentaGuard" ]="pentaguard"
    [ "Notify/Inka DRM" ]="inka_drm"
    [ "Igloo Corporation ESS (Security Suite)" ]="ess_agent"
    [ "IBM Spectrum Protect (TSM)" ]="dsmc baclnt"
    [ "Micro Focus Data Protector" ]="omniinet omnitm"
    [ "Dell NetWorker (Legato)" ]="nsrd nsrexecd"
    [ "Rubrik / Cohesity Agent" ]="rubrik-agent cohesity"
    [ "Grafana Agent / Alloy" ]="grafana-agent alloy"
    [ "Prometheus Node Exporter" ]="node_exporter"
    [ "Elastic Agent / Filebeat / Metricbeat" ]="elastic-agent filebeat metricbeat"
    [ "Fluentd / Fluent Bit" ]="fluentd td-agent fluent-bit"
    [ "Pinpoint Agent" ]="pinpoint"
	
	# ==========================================
    # 12. Korean File Transfer & Integration
    # ==========================================
    [ "Axway SecureTransport / Interstage" ]="st-server interstage"
    [ "Eucen DataHub / File Transfer" ]="eucen_agent"
    [ "CIS File Transfer Agent" ]="cis_agent"

    # ==========================================
    # 13. Korean PKI, Certification & Encryption
    # ==========================================
    [ "CrossCert PKI / SignGateway" ]="signgate crosscert"
    [ "KICA Certification Agent" ]="kica_agent"
    [ "Initech SecureWeb" ]="initech"
    [ "KSign PKI" ]="ksign_pki"

    # ==========================================
    # 14. Korean Security & Mail/Privacy Solutions
    # ==========================================
    [ "JiranSecurity MailGate / SpamWall" ]="mailgate spamwall"
    [ "JiranSecurity WebKeeper" ]="webkeeper wkagent wk_daemon wk_proxy"
	[ "MarkAny Document SAFER" ]="mas_agent"
    [ "Softcamp Document Security" ]="scds"
    [ "Plantynet Secure Web Gateway" ]="plantynet"
    [ "Wizvera VeraPort" ]="veraport"
	[ "Somansa Privacy-i" ]="privacyi dlpi smn_privacy privacyd dlpd"
    [ "Somansa Server-i" ]="serveri smn_serveri smn_av smn_scan serverd"
    [ "Somansa DB-i" ]="dbi smn_dbi dbid dbproxy"

    # ==========================================
    # 15. Korean DBMS & Performance Monitoring
    # ==========================================
    [ "Tmax Tibero DBMS" ]="tibero"
    [ "Altibase DBMS" ]="altibase"
    [ "MaxGauge DB Monitoring" ]="maxgauge"
    [ "Innorules BRMS" ]="innorules"
	[ "DSNTECH DBsaver (DB Security)" ]="dbsaver dbsavernet dbsagent dbsd"

    # ==========================================
    # 16. Cloud Platforms & CI/CD Runner
    # ==========================================
    [ "OpenStack Compute/Network" ]="nova-compute neutron-server"
    [ "GitLab Runner" ]="gitlab-runner"
    [ "SVN Server" ]="svnserve"
	
	# ==========================================
    # 17. Container Security, VDI & API Gateway
    # ==========================================
    [ "Aqua Security Enforcer" ]="security_enforcer"
    [ "Prisma Cloud Defender" ]="defender twistlock"
    [ "Istio Envoy Proxy" ]="envoy"
    [ "Kong API Gateway" ]="kong"
    [ "Apache APISIX" ]="apisix"
    [ "Radware DefensePro Agent" ]="defensepro"
	
	# ==========================================
    # 18. Log & Management
    # ==========================================
	[ "DSNTECH Logsaver (Log Management)" ]="logsaver logsavernet logsaver_agent"
	[ "Logpresso Enterprise" ]="logpresso logpresso-agent"
    [ "SECUI BlueMax/Log Manager" ]="secui_agent bluemax_agent"
    [ "Tmax SysMaster" ]="sysmaster sysmaster-agent"
    [ "Graylog Server/Sidecar" ]="graylog-server graylog-collector-sidecar"
	[ "Graylog Sidecar" ]="graylog-collector-sidecar"
    [ "Dynatrace OneAgent" ]="oneagent"
    [ "New Relic Infrastructure Agent" ]="newrelic-infra"
    [ "AhnLab Security/Sentry" ]="ahnsentry ahn_agent"
    [ "Grafana Loki" ]="loki promtail"
	[ "Elastic Filebeat" ]="filebeat"
    [ "Fluentd / Fluent Bit" ]="fluentd fluent-bit"
    	
	# ==========================================
    # 19. Global DevOps & HashiCorp Stack (Added)
    # ==========================================
    [ "HashiCorp Consul" ]="consul"
    [ "HashiCorp Vault" ]="vault"
    [ "HashiCorp Terraform/Packer" ]="terraform packer"
    [ "HashiCorp Nomad" ]="nomad"
    [ "Elasticsearch" ]="elasticsearch"
    [ "Kafka (Apache)" ]="kafka"
    [ "RabbitMQ" ]="rabbitmq-server beam.smp"
    [ "Jenkins" ]="jenkins"
    [ "ArgoCD / Argo Workflows" ]="argocd"
	
	# ==========================================
    # 20. Webmail & mail server
    # ==========================================
    [ "Postfix MTA" ]="master smtpd qmgr"
    [ "Dovecot IMAP/POP3" ]="dovecot dovecot-auth"
    [ "Zimbra Collaboration" ]="zmconfigd mailboxd zmmtad"
    [ "Daou Teramail/Groupware" ]="teramail groupware"
    [ "Handy Groupware" ]="handy_server handy_mail"
    [ "G-Groupware" ]="g-mail g-groupware"
    [ "Roundcube Webmail" ]="php-fpm"
    [ "Open-Xchange" ]="ox-server"
    [ "MailEnable/Exchange" ]="msexchange"
	
	# ==========================================
    # 21. PMS (Patch Management System)]
    # ==========================================
    [ "AhnLab APC (Patch)" ]="apc_agent apc_service"
    [ "JiranSecurity PatchMan" ]="patchman_agent pm_agent"
    [ "Red Hat Satellite (Katello)" ]="goferd katello-agent"
    [ "Canonical Landscape" ]="landscape-client"
    [ "Spacewalk / Foreman" ]="osad osa-dispatcher"
    [ "Chef Client" ]="chef-client"
    [ "Puppet Agent" ]="puppet"
    [ "Ansible (Automation)" ]="ansible-pull"
)

# 1. Detect running process and output their status
SVC_FOUND=0
declare -A RUNNING_PROCS

for svcname in "${!SVC_CHECKS[@]}"; do
    for proc in ${SVC_CHECKS[$svcname]}; do
        if pgrep -x "$proc" >/dev/null 2>&1 || pgrep -f "$proc" >/dev/null 2>&1; then
            log "    ▶ $svcname : ${C_GREEN}Running${C_NC}"
            SVC_FOUND=1
            RUNNING_PROCS["$proc"]="$svcname"
            break
        fi
    done
done
[ "$SVC_FOUND" -eq 0 ] && log "    (No major services detected)"

log ""
log "  [All Listening & Service Ports]"
if has_cmd ss; then
    # Retrieve listening TCP port information using the 'ss' command and process line by line
    ss -tlnp 2>/dev/null | tail -n +2 | while read -r line; do
        # Separate IP address and port (the part after the last colon is the port)
        local_addr=$(echo "$line" | awk '{print $4}')
        port=$(echo "$local_addr" | awk -F: '{print $NF}')
        if [ -z "$port" ] || ! [[ "$port" =~ ^[0-9]+$ ]]; then
            port=$(echo "$local_addr" | sed 's/.*:\([0-9]*\)$/\1/')
        fi

        # Extract the process name
        proc=$(echo "$line" | LC_ALL=C.UTF-8 grep -oP '(?<=users:\(\(")[^"]+' 2>/dev/null)
        [ -z "$proc" ] && proc="unknown"

        if [ -n "$port" ] && [[ "$port" =~ ^[0-9]+$ ]]; then
            matched_svc=""
            for p_key in "${!RUNNING_PROCS[@]}"; do
                if [[ "$proc" == *"$p_key"* ]] || [[ "$p_key" == *"$proc"* ]]; then
                    matched_svc="[${RUNNING_PROCS[$p_key]}] "
                    break
                fi
            done
            
            # 1) Highlight in green if matched with a registered major service
            if [ -n "$matched_svc" ]; then
                log "    - ${C_GREEN}${matched_svc} $proc${C_NC} : $port (LISTEN)"
            # 2) List unmatched general system ports together
            else
                log "    - $proc : $port (LISTEN)"
            fi
        fi
    done
else
    log "    (ss command not found - unable to check)"
fi

###############################################################################
section "11. System Error Message Check (Warning/Critical levels)"
###############################################################################
if has_cmd journalctl; then
    log "  [Critical Level (Emerg/Alert/Crit/Err)]"
    CRIT_LINES=$(journalctl -p 0..3 -b --no-pager 2>/dev/null | tail -10)
    if [ -n "$CRIT_LINES" ]; then
        echo "$CRIT_LINES" | while read -r line; do
            # Format long lines to maintain a 4-space indent when wrapping
            formatted_line=$(echo "$line" | sed ':a;N;$!ba;s/\n/\n    /g')
            log "    ${C_RED}${formatted_line}${C_NC}"
        done
    else
        log "    (None)"
    fi
    
    log "  [Warning Level]"
    WARN_LINES=$(journalctl -p 4 -b --no-pager 2>/dev/null | tail -10)
    if [ -n "$WARN_LINES" ]; then
        echo "$WARN_LINES" | while read -r line; do
            formatted_line=$(echo "$line" | sed ':a;N;$!ba;s/\n/\n    /g')
            log "    ${C_YELLOW}${formatted_line}${C_NC}"
        done
    else
        log "    (None)"
    fi
else
    log "  [dmesg-based Check]"
    log "  [Critical Level]"
    dmesg 2>/dev/null | grep -iE "error|fail" | tail -10 | while read -r line; do
        formatted_line=$(echo "$line" | sed ':a;N;$!ba;s/\n/\n    /g')
        log "    ${C_RED}${formatted_line}${C_NC}"
    done
    
    log "  [Warning Level]"
    dmesg 2>/dev/null | grep -iE "warn" | tail -10 | while read -r line; do
        formatted_line=$(echo "$line" | sed ':a;N;$!ba;s/\n/\n    /g')
        log "    ${C_YELLOW}${formatted_line}${C_NC}"
    done
fi

###############################################################################
section "12. Hardware Status Check"
###############################################################################
HW_STATUS="Normal"
HW_DETAIL_LIST=() 
VENDOR_TOOL_DETECTED=0

C_RED='\033[0;31m'
C_GREEN='\033[0;32m'
C_YELLOW='\033[0;33m'
C_NC='\033[0m'

log "  [Detailed Hardware Component Scan]"

# =============================================================================
# 1. Basic OS kernel & environment sensor scan (common)
# =============================================================================
MCE_ERR=$(dmesg 2>/dev/null | grep -iE "machine check exception|hardware error" | grep -vE "CPU supports.*MCE banks")
ECC_ERR=$(dmesg 2>/dev/null | grep -iE "ecc error|correctable error|uncorrectable error")
[ -n "$MCE_ERR" ] && { HW_STATUS="Fault"; HW_DETAIL_LIST+=("CPU hardware fault (MCE) detected"); }
[ -n "$ECC_ERR" ] && { HW_STATUS="Fault"; HW_DETAIL_LIST+=("Memory fault (ECC error) detected"); }

# Software RAID & Disk I/O
if [ -f /proc/mdstat ] && grep -qE "\[.*_.*\]" /proc/mdstat 2>/dev/null; then
    HW_STATUS="Fault"
    HW_DETAIL_LIST+=("Software RAID degraded")
fi
DISK_IO_ERR=$(dmesg 2>/dev/null | grep -iE "blk_update_request: I/O error|buffer i/o error|bad block")
[ -n "$DISK_IO_ERR" ] && { HW_STATUS="Fault"; HW_DETAIL_LIST+=("Disk physical I/O error or bad sector detected"); }

# Sensors & IPMI
if has_cmd sensors; then
    SENSOR_ALARM=$(sensors 2>/dev/null | grep -iE "ALARM|FAULT")
    [ -n "$SENSOR_ALARM" ] && { HW_STATUS="Fault"; HW_DETAIL_LIST+=("System fan/temperature threshold exceeded (ALARM)"); }
fi

if has_cmd ipmitool; then
    IPMI_FAULT=$(ipmitool sdr 2>/dev/null | grep -iE "fail|fault|crit|error" | grep -viE "no error|ok")
    if [ -n "$IPMI_FAULT" ]; then
        HW_STATUS="Fault"
        IPMI_SUMMARY=$(echo "$IPMI_FAULT" | head -n 1 | awk -F'|' '{print $1}' | xargs)
        HW_DETAIL_LIST+=("IPMI hardware sensor fault (e.g. $IPMI_SUMMARY)")
    fi
fi

# =============================================================================
# 2. Parse physical-server hardware RAID controller & virtual disk level info
# =============================================================================
LSPCI_CMD="lspci"
if [ ! -x "$(command -v lspci)" ] && [ -x "/sbin/lspci" ]; then LSPCI_CMD="/sbin/lspci"; fi

IS_VM="N"
if [ -x "$(command -v systemd-detect-virt)" ] && [ "$(systemd-detect-virt 2>/dev/null)" != "none" ]; then IS_VM="Y"; fi
if [ -x "$(command -v virt-what)" ] && [ -n "$(virt-what 2>/dev/null)" ]; then IS_VM="Y"; fi

# Filter out unnecessary PCIe bridges/switches (e.g., Renesas) and target only actual RAID/SAS controllers
RAID_CARD_STR=$($LSPCI_CMD 2>/dev/null | grep -iE "raid|storage|sas|lsi|mega" | grep -vE "SATA|AHCI|USB|IDE|Switch|Bridge|Renesas")

FORCE_CHECK=0
if [ -x "$(command -v ssacli)" ] || [ -x "$(command -v hpacucli)" ] || [ -x "$(command -v omreport)" ] || [ -x "$(command -v storcli)" ] || [ -x "$(command -v storcli64)" ]; then
    FORCE_CHECK=1
fi

RAID_DETECTED=0

if [ -n "$RAID_CARD_STR" ] || [ "$FORCE_CHECK" -eq 1 ]; then
    RAID_DETECTED=1
    log ""
    log "  [Hardware RAID Controller Device Info]"
    
    DETECTED_MODEL=""
    if [ -n "$RAID_CARD_STR" ]; then
        echo "$RAID_CARD_STR" | while read -r r_line; do
            dev_name=$(echo "$r_line" | awk -F': ' '{print $2}')
            log "    ▶ Detected device: $dev_name"
        done
        DETECTED_MODEL=$(echo "$RAID_CARD_STR" | head -n 1 | awk -F': ' '{print $2}')
    else
        log "    ▶ Running vendor-specific management-tool-based device discovery"
    fi

    RAID_HEADER_PRINTED=0

    # 2-1. HPE Smart Array scan
    HPE_CLI=""
    if [ -x "$(command -v ssacli)" ]; then HPE_CLI="ssacli"
    elif [ -x "/usr/sbin/ssacli" ]; then HPE_CLI="/usr/sbin/ssacli"
    elif [ -x "$(command -v hpacucli)" ]; then HPE_CLI="hpacucli"
    elif [ -x "/usr/sbin/hpacucli" ]; then HPE_CLI="/usr/sbin/hpacucli"; fi

    if [ -n "$HPE_CLI" ]; then
        VENDOR_TOOL_DETECTED=1
        HPE_STATUS=$($HPE_CLI ctrl all show status 2>/dev/null)
        hpe_ctrl_stat=$(echo "$HPE_STATUS" | grep -i "Controller Status:" | cut -d':' -f2 | xargs)
        hpe_batt_stat=$(echo "$HPE_STATUS" | grep -i "Cache Status:" | cut -d':' -f2 | xargs)
        [ -z "$hpe_ctrl_stat" ] && hpe_ctrl_stat="Unknown"
        [ -z "$hpe_batt_stat" ] && hpe_batt_stat="Unknown"
        
        log "    ▶ Controller Status  : $hpe_ctrl_stat"
        log "    ▶ Cache Battery Status : $hpe_batt_stat"

        HPE_LD_INFO=$($HPE_CLI ctrl all show config 2>/dev/null | grep -i "logicaldrive")
        if [ -n "$HPE_LD_INFO" ]; then
            log ""
            log "  [Hardware RAID Configuration & Virtual Disk Detail]"
            HEADER_STR=$(printf "    %-20s %-15s %-15s %-12s" "Drive Name" "Capacity" "RAID Level" "Status")
            log "$HEADER_STR"
            log "    ----------------------------------------------------------------"
            RAID_HEADER_PRINTED=1
            
            echo "$HPE_LD_INFO" | while read -r line; do
                [ -z "$line" ] && continue
                ld_id=$(echo "$line" | awk '{print $1, $2}')
                ld_size=$(echo "$line" | awk -F'(' '{print $2}' | awk -F',' '{print $1}' | xargs)
                ld_raid=$(echo "$line" | awk -F',' '{print $2}' | xargs)
                ld_stat=$(echo "$line" | awk -F',' '{print $3}' | tr -d ')' | xargs)
                
                ROW_STR=$(printf "    %-20s %-15s %-15s %-12s" "$ld_id" "$ld_size" "$ld_raid" "$ld_stat")
                log "$ROW_STR"
            done
        fi
        HPE_FAULT=$(echo "$HPE_STATUS" | grep -vE "OK|Normal" | grep -E "Status|Battery")
        if [ -n "$HPE_FAULT" ]; then HW_STATUS="Fault"; HW_DETAIL_LIST+=("HPE Smart Array / cache battery issue"); fi
    fi

    # 2-2. DELL PERC RAID scan
    DELL_CLI=""
    if [ -x "$(command -v omreport)" ]; then DELL_CLI="omreport"; elif [ -x "/opt/dell/srvadmin/bin/omreport" ]; then DELL_CLI="/opt/dell/srvadmin/bin/omreport"; fi
    
    if [ -n "$DELL_CLI" ]; then
        VENDOR_TOOL_DETECTED=1
        dell_ctrl_stat=$($DELL_CLI storage controller 2>/dev/null | grep "^Status" | head -n1 | cut -d':' -f2 | xargs)
        dell_batt_stat=$($DELL_CLI storage battery 2>/dev/null | grep "^Status" | head -n1 | cut -d':' -f2 | xargs)
        [ -z "$dell_ctrl_stat" ] && dell_ctrl_stat="Unknown"
        [ -z "$dell_batt_stat" ] && dell_batt_stat="Unknown"
        
        log "    ▶ Controller Status  : $dell_ctrl_stat"
        log "    ▶ Cache Battery Status : $dell_batt_stat"

        DELL_VD_RAW=$($DELL_CLI storage vdisk 2>/dev/null)
        if echo "$DELL_VD_RAW" | grep -q -i "ID"; then
            if [ "$RAID_HEADER_PRINTED" -eq 0 ]; then
                log ""
                log "  [Hardware RAID Configuration & Virtual Disk Detail]"
                HEADER_STR=$(printf "    %-15s %-15s %-20s %-12s" "Virtual Disk ID" "Capacity" "RAID Level(Layout)" "Status")
                log "$HEADER_STR"
                log "    ----------------------------------------------------------------"
                RAID_HEADER_PRINTED=1
            fi
            
            echo "$DELL_VD_RAW" | grep -E "^ID|^Status|^Size|^Layout" | while read -r line; do
                key=$(echo "$line" | cut -d':' -f1 | xargs)
                val=$(echo "$line" | cut -d':' -f2- | xargs)
                
                case "$key" in
                    ID) vdid=$val ;;
                    Status) stat=$val ;;
                    Size) size=$val ;;
                    Layout) 
                        if [ "$val" = "Mirrored" ]; then layout="RAID-1"
                        elif [ "$val" = "Striped" ]; then layout="RAID-0"
                        elif [ "$val" = "Spanned" ]; then layout="RAID-10"
                        else layout="$val"; fi
                        
                        ROW_STR=$(printf "    %-15s %-15s %-20s %-12s" "$vdid" "$size" "$layout" "$stat")
                        log "$ROW_STR"
                        ;;
                esac
            done
        fi
        DELL_CHASSIS=$($DELL_CLI chassis 2>/dev/null | grep -i "Health" | grep -viE "Ok|Normal")
        DELL_STORAGE=$($DELL_CLI storage vdisk 2>/dev/null | grep -i "Status" | grep -viE "Ok|Normal|Ready")
        DELL_BATTERY=$($DELL_CLI storage battery 2>/dev/null | grep -i "Status" | grep -viE "Ok|Normal")
        if [ -n "$DELL_CHASSIS" ] || [ -n "$DELL_STORAGE" ] || [ -n "$DELL_BATTERY" ]; then
            HW_STATUS="Fault"; HW_DETAIL_LIST+=("DELL chassis component or PERC RAID/battery issue");
        fi
    fi

    # 2-3. Lenovo / Broadcom / LSI MegaRAID (storcli) scan
    L_CLI=""
    if [ -x "$(command -v storcli)" ]; then L_CLI="storcli"
    elif [ -x "$(command -v storcli64)" ]; then L_CLI="storcli64"
    elif [ -x "/opt/MegaRAID/storcli/storcli" ]; then L_CLI="/opt/MegaRAID/storcli/storcli"
    elif [ -x "/opt/MegaRAID/storcli/storcli64" ]; then L_CLI="/opt/MegaRAID/storcli/storcli64"
    elif [ -x "/usr/sbin/storcli" ]; then L_CLI="/usr/sbin/storcli"
    elif [ -x "/usr/sbin/storcli64" ]; then L_CLI="/usr/sbin/storcli64"; fi

    if [ -n "$L_CLI" ]; then
        VENDOR_TOOL_DETECTED=1
        lenovo_ctrl_raw=$($L_CLI /c0 show 2>/dev/null)
        [ -z "$lenovo_ctrl_raw" ] && lenovo_ctrl_raw=$($L_CLI /call show 2>/dev/null)
        lenovo_ctrl_stat=$(echo "$lenovo_ctrl_raw" | grep -i "Status =" | head -n1 | cut -d'=' -f2 | xargs)
        
        lenovo_batt_raw=$($L_CLI /c0/bbu show 2>/dev/null)
        [ -z "$lenovo_batt_raw" ] && lenovo_batt_raw=$($L_CLI /call/bbu show 2>/dev/null)
        lenovo_batt_stat=$(echo "$lenovo_batt_raw" | grep -iE "State|Status" | grep -v "Missing" | head -n1 | cut -d':' -f2 | xargs)
        
        [ -z "$lenovo_ctrl_stat" ] && lenovo_ctrl_stat="Unknown"
        [ -z "$lenovo_batt_stat" ] && lenovo_batt_stat="Unknown"
        
        log "    ▶ Controller Status  : $lenovo_ctrl_stat"
        log "    ▶ Cache Battery Status : $lenovo_batt_stat"

        LENOVO_VD_INFO=$($L_CLI /c0/vall show 2>/dev/null | grep -A 20 "DG/VD" | grep -E "^[0-9]")
        [ -z "$LENOVO_VD_INFO" ] && LENOVO_VD_INFO=$($L_CLI /call/vall show 2>/dev/null | grep -A 20 "DG/VD" | grep -E "^[0-9]")
        
        if [ -n "$LENOVO_VD_INFO" ]; then
            if [ "$RAID_HEADER_PRINTED" -eq 0 ]; then
                log ""
                log "  [Hardware RAID Configuration & Virtual Disk Detail]"
                HEADER_STR=$(printf "    %-15s %-15s %-15s %-12s" "DG/VD" "Capacity" "RAID Level(TYPE)" "Status")
                log "$HEADER_STR"
                log "    ----------------------------------------------------------------"
                RAID_HEADER_PRINTED=1
            fi
            echo "$LENOVO_VD_INFO" | while read -r dg_vd TYPE opt d_state size unit stat; do
                [ -z "$dg_vd" ] && continue
                if echo "$TYPE" | grep -q -i "RAID"; then r_level="$TYPE"; else r_level="RAID-$TYPE"; fi
                [ "$unit" = "Optl" ] || [ "$unit" = "Dgrd" ] && { stat=$unit; unit=""; }
                ROW_STR=$(printf "    %-15s %-15s %-15s %-12s" "$dg_vd" "$size $unit" "$r_level" "$stat")
                log "$ROW_STR"
            done
        fi
        
        LENOVO_FAULT=$(echo "$lenovo_ctrl_raw" | grep -iE "Status|State" | grep -E "Failed|Degraded|Needs Attention|Inoperable")
        if [ -n "$LENOVO_FAULT" ]; then HW_STATUS="Fault"; HW_DETAIL_LIST+=("LSI MegaRAID controller or BBU battery issue"); fi
    else
        if [ -n "$DETECTED_MODEL" ]; then
            log "    ▶ Controller Status  : Normal (Detected, but management tool 'storcli' not installed for detail scan)"
        else
            log "    ▶ Controller Status  : Normal (Hardware RAID detected, management tool not installed)"
        fi
    fi
fi

if [ "$RAID_DETECTED" -eq 0 ]; then
    if [ "$IS_VM" = "Y" ]; then
        log "  - Hardware RAID : This is a virtualization guest (VM), so no physical RAID controller is present."
    else
        log "  - Hardware RAID : No standalone hardware RAID controller card was detected on this system."
    fi
fi

# =============================================================================
# 3. Print the combined result and detailed breakdown
# =============================================================================
log ""
if [ "$HW_STATUS" = "Normal" ]; then
    log "  - Overall Hardware Status : [${C_GREEN}Normal${C_NC} (all sensors and hardware logs are operating normally)]"
else
    HW_DETAIL=$(printf ", %s" "${HW_DETAIL_LIST[@]}")
    HW_DETAIL=${HW_DETAIL:2} 
    log "  - Overall Hardware Status : [${C_RED}Fault${C_NC} (${HW_DETAIL}) - detailed inspection needed]"
    
    log "    [Fault Log Summary]"
    [ -n "$MCE_ERR" ]     && log "    ${C_YELLOW}└ CPU Error:${C_NC} $(echo "$MCE_ERR" | tail -n 1)"
    [ -n "$ECC_ERR" ]     && log "    ${C_YELLOW}└ Memory Error:${C_NC} $(echo "$ECC_ERR" | tail -n 1)"
    [ -n "$DISK_IO_ERR" ] && log "    ${C_YELLOW}└ Disk Error:${C_NC} $(echo "$DISK_IO_ERR" | tail -n 1)"
    [ -n "$IPMI_FAULT" ]    && log "    ${C_YELLOW}└ IPMI Sensor Error:${C_NC}\n$(echo "$IPMI_FAULT" | sed 's/^/      /')"
    [ -n "$HPE_FAULT" ]     && log "    ${C_YELLOW}└ HPE SmartArray Error:${C_NC}\n$(echo "$HPE_FAULT" | sed 's/^/      /')"
    [ -n "$DELL_STORAGE" ] && log "    ${C_YELLOW}└ DELL Storage Error:${C_NC} Virtual disk (VDisk) status issue detected"
    [ -n "$DELL_BATTERY" ] && log "    ${C_YELLOW}└ DELL Battery Error:${C_NC} PERC controller battery status issue detected"
    [ -n "$LENOVO_FAULT" ] && log "    ${C_YELLOW}└ Lenovo/MegaRAID Error:${C_NC}\n$(echo "$LENOVO_FAULT" | sed 's/^/      /')"
fi

###############################################################################
section "13. Security Check Summary (From KISA List)"
###############################################################################
log "  [Key Security Settings Review & KISA Vulnerability Check]"

# ==========================================
# [High Priority] Critical Security Items
# ==========================================

# 1. U-01: SSH root remote login (PermitRootLogin)
if [ -f /etc/ssh/sshd_config ]; then
    ROOTLOGIN=$(grep -i "^PermitRootLogin" /etc/ssh/sshd_config 2>/dev/null | awk '{print $2}')
    if [ -z "$ROOTLOGIN" ] || [ "$ROOTLOGIN" = "yes" ]; then
        log "    ▶ ${C_RED}[High]${C_NC} [U-01] SSH root remote login is allowed (PermitRootLogin: ${ROOTLOGIN:-unset})."
    else
        log "    ▶ ${C_GREEN}[Normal]${C_NC} [U-01] SSH root remote login is restricted (${ROOTLOGIN})."
    fi
fi

# 2. U-02: Password max/min days policy
if [ -f /etc/login.defs ]; then
    MAXDAYS=$(awk '/^PASS_MAX_DAYS/{print $2}' /etc/login.defs)
    if [ -n "$MAXDAYS" ] && [ "$MAXDAYS" -gt 90 ] 2>/dev/null; then
        log "    ▶ ${C_YELLOW}[Medium]${C_NC} [U-02] PASS_MAX_DAYS (${MAXDAYS}) exceeds recommended limit (90 days)."
    fi
    MINDAYS=$(awk '/^PASS_MIN_DAYS/{print $2}' /etc/login.defs)
    if [ -z "$MINDAYS" ] || [ "$MINDAYS" -lt 1 ] 2>/dev/null; then
        log "    ▶ ${C_YELLOW}[Medium]${C_NC} [U-02] PASS_MIN_DAYS (${MINDAYS:-0}) is under recommended value (1 day)."
    fi
fi

# 3. U-05: /etc/shadow file permission & ownership
if [ -f /etc/shadow ]; then
    SHADOW_PERM=$(stat -c "%a" /etc/shadow 2>/dev/null)
    SHADOW_USER=$(stat -c "%U" /etc/shadow 2>/dev/null)
    if [ "$SHADOW_PERM" -gt 000 ] && [ "$SHADOW_PERM" -ne 400 ]; then
        log "    ▶ ${C_RED}[High]${C_NC} [U-05] /etc/shadow permission is insecure (${SHADOW_PERM}, recommended: 000 or 400)."
    else
        log "    ▶ ${C_GREEN}[Normal]${C_NC} [U-05] /etc/shadow permission is secure (${SHADOW_PERM})."
    fi
fi

# 4. U-06: Root PATH environment variable check (checking leading/double colons)
if [ -n "$PATH" ]; then
    if [[ "$PATH" == *"::"* ]] || [[ "$PATH" == *".:"* ]] || [[ "$PATH" == *":."* ]] || [[ "$PATH" == "."* ]]; then
        log "    ▶ ${C_RED}[High]${C_NC} [U-06] Root PATH contains current directory (.) or empty path (${PATH})."
    else
        log "    ▶ ${C_GREEN}[Normal]${C_NC} [U-06] Root PATH environment variable is safe."
    fi
fi

# 5. U-14: User startup files (.profile, .bashrc) world-writable check
if [ "$IS_ROOT" -eq 1 ]; then
    UNSAFE_FILES=""
    for user_home in $(awk -F: '($3 >= 1000 && $7 !~ /nologin|false/) {print $6}' /etc/passwd); do
        if [ -d "$user_home" ]; then
            for rc_file in "$user_home/.profile" "$user_home/.bashrc" "$user_home/.bash_profile"; do
                if [ -f "$rc_file" ]; then
                    if [ -w "$rc_file" ]; then
                        UNSAFE_FILES="${UNSAFE_FILES}${rc_file} "
                    fi
                fi
            done
        fi
    done
    if [ -n "$UNSAFE_FILES" ]; then
        log "    ▶ ${C_RED}[High]${C_NC} [U-14] User startup file(s) have write permission for others/group: ${UNSAFE_FILES}"
    else
        log "    ▶ ${C_GREEN}[Normal]${C_NC} [U-14] User startup files permission safe."
    fi
fi

# 6. U-18: .rhosts and hosts.equiv check
RHOSTS_FOUND=""
for user_home in $(awk -F: '{print $6}' /etc/passwd); do
    [ -d "$user_home" ] && [ -f "$user_home/.rhosts" ] && RHOSTS_FOUND="${RHOSTS_FOUND}${user_home}/.rhosts "
done
[ -f /etc/hosts.equiv ] && RHOSTS_FOUND="${RHOSTS_FOUND}/etc/hosts.equiv "
if [ -n "$RHOSTS_FOUND" ]; then
    log "    ▶ ${C_RED}[High]${C_NC} [U-18] Insecure remote trust file(s) found: ${RHOSTS_FOUND}"
else
    log "    ▶ ${C_GREEN}[Normal]${C_NC} [U-18] No insecure .rhosts or hosts.equiv files found."
fi

# 7. U-22: r-commands (rsh, rlogin, rcp) service activation check
R_SVC_ACTIVE=0
for r_svc in rsh.socket rlogin.socket rcp.socket rsh rlogin; do
    if systemctl is-active "$r_svc" >/dev/null 2>&1; then
        R_SVC_ACTIVE=1
    fi
done
if [ "$R_SVC_ACTIVE" -eq 1 ]; then
    log "    ▶ ${C_RED}[High]${C_NC} [U-22] Legacy r-command services (rsh/rlogin) are active."
else
    log "    ▶ ${C_GREEN}[Normal]${C_NC} [U-22] Legacy r-command services are disabled."
fi

# 8. U-52: Telnet service check
if pgrep -x "in.telnetd" >/dev/null 2>&1 || systemctl is-active telnet.socket >/dev/null 2>&1; then
    log "    ▶ ${C_RED}[High]${C_NC} [U-52] Insecure Telnet service is active."
else
    log "    ▶ ${C_GREEN}[Normal]${C_NC} [U-52] Telnet service is disabled."
fi

# ==========================================
# [Medium Priority] Internal Security & Management
# ==========================================

# 9. U-11: /etc/services permission check
if [ -f /etc/services ]; then
    SERV_PERM=$(stat -c "%a" /etc/services 2>/dev/null)
    if [ "$SERV_PERM" -gt 644 ]; then
        log "    ▶ ${C_YELLOW}[Medium]${C_NC} [U-11] /etc/services permission is insecure (${SERV_PERM}, recommended: 644 or less)."
    fi
fi

# 10. U-16: World Writable files quick scan (checking key system paths)
if [ "$IS_ROOT" -eq 1 ]; then
    WW_COUNT=$(find /etc /bin /sbin /usr/bin /usr/sbin -type f -perm -2o 2>/dev/null | wc -l)
    if [ "$WW_COUNT" -gt 0 ]; then
        log "    ▶ ${C_YELLOW}[Medium]${C_NC} [U-16] Found ${WW_COUNT} world-writable file(s) in system binary/config directories."
    else
        log "    ▶ ${C_GREEN}[Normal]${C_NC} [U-16] No world-writable system files found."
    fi
fi

# 11. U-19: Cron file permission check
if [ -d /etc/cron.d ] && [ "$(stat -c "%a" /etc/cron.d 2>/dev/null)" -gt 755 ]; then
    log "    ▶ ${C_YELLOW}[Medium]${C_NC} [U-19] /etc/cron.d directory permission is insecure."
fi

# 12. U-20: Finger service check
if pgrep -x "fingerd" >/dev/null 2>&1 || systemctl is-active finger.socket >/dev/null 2>&1; then
    log "    ▶ ${C_YELLOW}[Medium]${C_NC} [U-20] Insecure Finger service is active."
else
    log "    ▶ ${C_GREEN}[Normal]${C_NC} [U-20] Finger service is disabled."
fi

# 13. SELinux & Firewall basic status
if has_cmd getenforce; then
    SEL=$(getenforce 2>/dev/null)
    [ "$SEL" != "Enforcing" ] && log "    ▶ ${C_YELLOW}[Medium]${C_NC} SELinux is disabled or not enforcing (${SEL})."
fi

# 14. Empty Password Account Check
if [ "$IS_ROOT" -eq 1 ] && [ -r /etc/shadow ]; then
    EMPTY_PW=$(awk -F: '($2==""){print $1}' /etc/shadow)
    if [ -n "$EMPTY_PW" ]; then
        log "    ▶ ${C_RED}[High]${C_NC} Account(s) with no password found: $(echo "$EMPTY_PW" | tr '\n' ' ')"
    fi
fi

################################################################################
# 14. User Account & System Boot/Reboot History Check
################################################################################
section "14. User Account & System Boot/Reboot History Check"

# 1. Actual login-enabled accounts among those created, plus their last login record
log "  [Active Accounts & Last Login History]"
HEADER_ACC=$(printf "    %-18s %-25s %-20s" "Account" "Last Login Time" "Source (IP/TTY)")
log "$HEADER_ACC"
log "    ----------------------------------------------------------------------"

# Extract actively-usable accounts from /etc/passwd, excluding system daemon accounts like nologin, false, sync
ACTIVE_USERS=$(awk -F: '$7 !~ /nologin|false|sync|shutdown|halt/ {print $1}' /etc/passwd | sort)

if [ -n "$ACTIVE_USERS" ]; then
    echo "$ACTIVE_USERS" | while read -r u_name; do
        [ -z "$u_name" ] && continue
        
        # Capture the single most recent login record for this account via the last command
        last_log=$(last -n 1 "$u_name" 2>/dev/null | head -n 1)
        
        if echo "$last_log" | grep -qE "^wtmp|reboot|^$"; then
            # No login record at all
            u_time="No login record"
            u_from="N/A"
        else
            # Parse the device/IP and date fields from the last command's output format
            # (whitespace handling compatible across both CentOS 6/7)
            u_from=$(echo "$last_log" | awk '{print $3}')
            # Determine whether the date info comes right after the tty or after an IP
            if [[ "$u_from" =~ ^[0-9] ]]; then
                # The 3rd field is a date (e.g. a local tty login with no IP)
                u_time=$(echo "$last_log" | awk '{print $4,$5,$6,$7}')
            else
                # The 3rd field is an IP address or hostname
                u_time=$(echo "$last_log" | awk '{print $4,$5,$6,$7,$8}')
            fi
            [ -z "$u_time" ] && u_time="Unknown"
            [ -z "$u_from" ] && u_from="local"
        fi
        
        ROW_ACC=$(printf "    %-18s %-25s %-20s" "$u_name" "$u_time" "$u_from")
        log "$ROW_ACC"
    done
else
    log "    (No active regular accounts detected)"
fi

log ""

# 2. Recent boot/reboot history at the actual hardware/OS level
log "  [Recent System Boot / Reboot History (last 5)]"
HEADER_BOOT=$(printf "    %-15s %-25s %-20s" "Event Type" "Boot Time" "Uptime Duration")
log "$HEADER_BOOT"
log "    ----------------------------------------------------------------------"

# Extract kernel physical reset/boot history via the last reboot command
BOOT_HISTORY=$(last reboot 2>/dev/null | head -n 5 | sed '/^$/d')

if [ -n "$BOOT_HISTORY" ]; then
    echo "$BOOT_HISTORY" | while read -r b_line; do
        [ -z "$b_line" ] && continue
        
        b_type="System Boot"
        
        # Parse the boot-time info (combine the date string starting at the 4th field)
        b_time=$(echo "$b_line" | awk '{print $5,$6,$7,$8,$9}')
        
        # Extract the duration in parentheses, whether it's still running or shows downtime
        b_duration=$(echo "$b_line" | sed -n 's/.*(\([^)]*\)).*/\1/p')
		if [ -z "$b_duration" ] || echo "$b_line" | grep -q "still running"; then b_duration="Running"
		fi       
        ROW_BOOT=$(printf "    %-15s %-25s %-20s" "$b_type" "$b_time" "$b_duration")
        log "$ROW_BOOT"
    done
else
    # Final fallback based on the current uptime if the wtmp log has rotated out
    if has_cmd uptime; then
        up_time=$(uptime 2>/dev/null | awk -F'up ' '{print $2}' | cut -d',' -f1)
        log "    ▶ System is currently up (detailed history lost to wtmp rotation / current uptime: $up_time)"
    else
        log "    (Unable to query boot history)"
    fi
fi

###############################################################################
log ""
log "${C_BOLD}=========================================================${C_NC}"
log "${C_BOLD} Check complete.${C_NC}"
log "${C_BOLD}=========================================================${C_NC}"

echo ""
read -r -p "Save the check report as a TXT file? (y/n): " SAVE_YN
if [[ "$SAVE_YN" =~ ^[Yy]$ ]]; then
    DEFAULT_NAME="linux_check_report_${HOSTNAME_VAL}_$(date +%Y%m%d_%H%M%S).txt"
    read -r -p "Enter a filename to save as (press Enter for default: $DEFAULT_NAME): " FILENAME
    FILENAME=${FILENAME:-$DEFAULT_NAME}
    cp "$TMP_LOG" "$FILENAME"
    echo "Saved to: $FILENAME"
else
    echo "Exiting without saving."
fi

rm -f "$TMP_LOG" 2>/dev/null
