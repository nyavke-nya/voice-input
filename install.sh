#!/bin/sh
# shellcheck shell=bash
# Universal Linux installer for Voice Input. Run as a normal user: ./install.sh

# Alpine and a few minimal systems do not ship Bash. Bootstrap it before the
# Bash-only implementation below is parsed; dry-run never changes the system.
if [ -z "${BASH_VERSION:-}" ]; then
    if command -v bash >/dev/null 2>&1; then
        exec bash "$0" "$@"
    fi
    voice_bootstrap_dry=false
    for voice_bootstrap_arg do
        [ "$voice_bootstrap_arg" = --dry-run ] && voice_bootstrap_dry=true
    done
    voice_bootstrap_musl=false
    for voice_bootstrap_loader in /lib/ld-musl-*.so.1; do
        [ -e "$voice_bootstrap_loader" ] && voice_bootstrap_musl=true
    done
    if $voice_bootstrap_musl; then
        printf '%s\n' \
            'Alpine/musl определён. onnxruntime и CTranslate2 пока не имеют musllinux wheels.' \
            'Alpine/musl detected. onnxruntime and CTranslate2 do not provide musllinux wheels yet.' >&2
        $voice_bootstrap_dry && exit 0
        exit 1
    fi
    if $voice_bootstrap_dry; then
        printf '%s\n' 'Bash не найден. Обычная установка сначала поставит пакет bash.'
        printf '%s\n' 'Bash is missing. A normal install will install the bash package first.'
        exit 0
    fi
    if [ "$(id -u)" -eq 0 ]; then
        printf '%s\n' 'Запустите установщик обычным пользователем, не root.' >&2
        exit 1
    fi
    if command -v sudo >/dev/null 2>&1; then
        voice_bootstrap_priv=sudo
    elif command -v doas >/dev/null 2>&1; then
        voice_bootstrap_priv=doas
    else
        printf '%s\n' 'Для установки Bash нужен sudo или doas.' >&2
        exit 1
    fi
    printf '%s\n' 'WARNING / ВНИМАНИЕ: устанавливаю системный пакет bash.'
    if command -v apk >/dev/null 2>&1; then
        "$voice_bootstrap_priv" apk add bash
    elif command -v xbps-install >/dev/null 2>&1; then
        "$voice_bootstrap_priv" xbps-install -Sy bash
    elif command -v apt-get >/dev/null 2>&1; then
        "$voice_bootstrap_priv" apt-get update
        "$voice_bootstrap_priv" apt-get install -y bash
    elif command -v dnf >/dev/null 2>&1; then
        "$voice_bootstrap_priv" dnf install -y bash
    elif command -v pacman >/dev/null 2>&1; then
        "$voice_bootstrap_priv" pacman -S --needed --noconfirm bash
    elif command -v zypper >/dev/null 2>&1; then
        "$voice_bootstrap_priv" zypper --non-interactive install bash
    else
        printf '%s\n' 'Сначала установите Bash пакетным менеджером системы.' >&2
        exit 1
    fi
    exec bash "$0" "$@"
fi

set -Eeuo pipefail

voice_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
voice_venv="${voice_root}/.venv"
voice_user="$(id -un)"
voice_dry_run=false
voice_skip_model=false
voice_config_file="${XDG_CONFIG_HOME:-${HOME}/.config}/pill/config.json"
voice_new_config=false
[[ -f "$voice_config_file" ]] || voice_new_config=true

voice_usage() {
    printf 'Использование / Usage: %s [--dry-run] [--skip-model]\n' "$0"
}

while (($#)); do
    case "$1" in
        --dry-run) voice_dry_run=true ;;
        --skip-model) voice_skip_model=true ;;
        -h|--help) voice_usage; exit 0 ;;
        *) voice_usage >&2; exit 2 ;;
    esac
    shift
done

if ((EUID == 0)) && ! $voice_dry_run; then
    printf 'Запустите %s обычным пользователем, не через sudo.\n' "$0" >&2
    printf 'Run %s as your normal user, not through sudo.\n' "$0" >&2
    exit 1
fi
if [[ "$voice_root" =~ [[:space:]] ]]; then
    printf 'Путь к проекту пока не должен содержать пробелы: %s\n' "$voice_root" >&2
    exit 1
fi
if [[ ! -f "${voice_root}/requirements.txt" || ! -f "${voice_root}/pill/__main__.py" ]]; then
    printf 'install.sh должен находиться в корне репозитория Voice Input.\n' >&2
    exit 1
fi
if [[ "$(uname -s)" != Linux ]]; then
    printf 'Этот установщик предназначен только для Linux. / This installer is Linux-only.\n' >&2
    exit 1
fi

voice_os_id=linux
voice_os_name=Linux
if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    voice_os_id="${ID:-linux}"
    voice_os_name="${PRETTY_NAME:-${NAME:-Linux}}"
fi

voice_pm=generic
for voice_candidate in pacman apt-get dnf zypper xbps-install apk emerge eopkg; do
    if command -v "$voice_candidate" >/dev/null 2>&1; then
        case "$voice_candidate" in
            apt-get) voice_pm=apt ;;
            xbps-install) voice_pm=xbps ;;
            *) voice_pm="$voice_candidate" ;;
        esac
        break
    fi
done

voice_libc=unknown
voice_ldd_info=""
if command -v ldd >/dev/null 2>&1; then
    voice_ldd_info="$(ldd --version 2>&1 || true)"
fi
if getconf GNU_LIBC_VERSION >/dev/null 2>&1; then
    voice_libc=glibc
elif grep -qi musl <<< "$voice_ldd_info"; then
    voice_libc=musl
fi

voice_session="${XDG_SESSION_TYPE:-}"
if [[ -z "$voice_session" ]]; then
    if [[ -n "${WAYLAND_DISPLAY:-}" ]]; then voice_session=wayland
    elif [[ -n "${DISPLAY:-}" ]]; then voice_session=x11
    else voice_session=unknown
    fi
fi
voice_desktop_raw="${XDG_CURRENT_DESKTOP:-${XDG_SESSION_DESKTOP:-${DESKTOP_SESSION:-}}}"
voice_desktop="${voice_desktop_raw,,}"
if [[ -n "${HYPRLAND_INSTANCE_SIGNATURE:-}" || "$voice_desktop" == *hyprland* ]]; then
    voice_desktop=hyprland
elif [[ -n "${SWAYSOCK:-}" || "$voice_desktop" == *sway* ]]; then
    voice_desktop=sway
elif [[ -n "${I3SOCK:-}" || "$voice_desktop" == i3* ]]; then
    voice_desktop=i3
elif [[ "$voice_desktop" == *gnome* ]]; then
    voice_desktop=gnome
elif [[ "$voice_desktop" == *cinnamon* ]]; then
    voice_desktop=cinnamon
elif [[ "$voice_desktop" == *xfce* ]]; then
    voice_desktop=xfce
elif [[ "$voice_desktop" == *kde* || "$voice_desktop" == *plasma* ]]; then
    voice_desktop=kde
elif [[ -z "$voice_desktop" ]]; then
    voice_desktop=generic
fi

voice_core_packages=()
voice_optional_packages=()
case "$voice_pm" in
    pacman)
        voice_core_packages=(python python-pip portaudio acl base-devel)
        voice_optional_packages=(wtype ydotool dotool wl-clipboard xdotool xclip libnotify desktop-file-utils libxkbcommon-x11 xcb-util-cursor)
        ;;
    apt)
        voice_core_packages=(python3 python3-venv python3-pip python3-dev build-essential linux-libc-dev libportaudio2 portaudio19-dev acl)
        voice_optional_packages=(wtype ydotool dotool wl-clipboard xdotool xclip libnotify-bin desktop-file-utils libgl1 libegl1 libxkbcommon0 libxkbcommon-x11-0 libxcb-cursor0 libxcb-xinerama0)
        ;;
    dnf)
        voice_core_packages=(python3 python3-pip python3-devel gcc kernel-headers portaudio portaudio-devel acl)
        voice_optional_packages=(wtype ydotool dotool wl-clipboard xdotool xclip libnotify desktop-file-utils libxkbcommon-x11 xcb-util-cursor mesa-libGL)
        ;;
    zypper)
        voice_core_packages=(python311 python311-pip python311-devel gcc linux-glibc-devel portaudio-devel acl)
        voice_optional_packages=(wtype ydotool dotool wl-clipboard xdotool xclip libnotify-tools desktop-file-utils libxkbcommon-x11-0 libxcb-cursor0 Mesa-libGL1)
        ;;
    xbps)
        voice_core_packages=(python3 python3-pip python3-devel base-devel portaudio-devel acl)
        voice_optional_packages=(python3-virtualenv wtype ydotool dotool wl-clipboard xdotool xclip libnotify desktop-file-utils libxkbcommon-x11 xcb-util-cursor)
        ;;
    apk)
        voice_core_packages=(python3 py3-pip py3-virtualenv python3-dev build-base linux-headers portaudio portaudio-dev acl)
        voice_optional_packages=(py3-pyside6 wtype ydotool dotool wl-clipboard xdotool xclip libnotify desktop-file-utils libxkbcommon xcb-util-cursor mesa-gl)
        ;;
    emerge)
        voice_core_packages=(dev-lang/python dev-python/pip media-libs/portaudio sys-apps/acl)
        voice_optional_packages=(gui-apps/wtype gui-apps/ydotool gui-apps/dotool gui-apps/wl-clipboard x11-misc/xdotool x11-misc/xclip x11-libs/libnotify dev-util/desktop-file-utils)
        ;;
    eopkg)
        voice_core_packages=(python3 python3-devel portaudio-devel acl)
        voice_optional_packages=(wtype ydotool dotool wl-clipboard xdotool xclip libnotify desktop-file-utils)
        ;;
esac

printf '\nVOICE INPUT — ПЛАН УСТАНОВКИ / INSTALL PLAN\n'
printf '  Linux:       %s (%s)\n' "$voice_os_name" "$voice_os_id"
printf '  Packages:    %s\n' "$voice_pm"
printf '  C library:   %s\n' "$voice_libc"
printf '  Session:     %s\n' "$voice_session"
printf '  Desktop/WM:  %s\n' "$voice_desktop"
printf '  Repository:  %s\n' "$voice_root"
if ((${#voice_core_packages[@]})); then
    printf '  Required:    %s\n' "${voice_core_packages[*]}"
    printf '  Optional:    %s\n' "${voice_optional_packages[*]}"
else
    printf '  Packages:    unknown manager; existing system dependencies will be used\n'
fi
printf '  Python:      .venv + requirements.txt\n'
printf '  Integration: XDG autostart + native bind or evdev fallback\n'
printf '  System:      /etc/udev/rules.d/99-voice-input-*.rules, groups uinput/voiceinput\n'

if $voice_dry_run; then
    printf '\nDry-run: файлы, пакеты и настройки не изменены.\n'
    printf 'Dry run: no files, packages, or settings were changed.\n'
    exit 0
fi

if [[ "$voice_libc" == musl ]]; then
    printf '%s\n' \
        'Alpine/musl распознан, но upstream onnxruntime и CTranslate2 не выпускают musllinux wheels.' \
        'Автоустановка остановлена до системного glibc-бэкенда; менять libc автоматически небезопасно.' \
        'Alpine/musl was detected, but upstream onnxruntime and CTranslate2 do not ship musllinux wheels.' \
        'Installation stops instead of changing your libc. Report/track support: https://t.me/nyavke' >&2
    exit 1
fi

if command -v sudo >/dev/null 2>&1; then
    voice_priv=(sudo)
elif command -v doas >/dev/null 2>&1; then
    voice_priv=(doas)
else
    printf 'Нужен sudo или doas для пакетов, групп и udev-правил.\n' >&2
    printf 'sudo or doas is required for packages, groups, and udev rules.\n' >&2
    exit 1
fi

voice_as_root() {
    "${voice_priv[@]}" "$@"
}

printf '\nВНИМАНИЕ: сейчас будут установлены пакеты и два точечных udev-правила в /etc.\n'
printf 'WARNING: packages and two narrow udev rules under /etc will now be installed.\n'
voice_as_root true

voice_apt_updated=false
voice_install_package() {
    local package="$1"
    case "$voice_pm" in
        pacman) voice_as_root pacman -S --needed --noconfirm "$package" ;;
        apt)
            if ! $voice_apt_updated; then
                voice_as_root apt-get update
                voice_apt_updated=true
            fi
            voice_as_root env DEBIAN_FRONTEND=noninteractive \
                apt-get install -y --no-install-recommends "$package"
            ;;
        dnf) voice_as_root dnf install -y "$package" ;;
        zypper) voice_as_root zypper --non-interactive install --no-recommends "$package" ;;
        xbps) voice_as_root xbps-install -Sy "$package" ;;
        apk) voice_as_root apk add "$package" ;;
        emerge) voice_as_root emerge --noreplace "$package" ;;
        eopkg) voice_as_root eopkg install -y "$package" ;;
        generic) return 1 ;;
    esac
}

if ((${#voice_core_packages[@]})); then
    printf '\nСтавлю обязательные системные зависимости…\n'
    for voice_package in "${voice_core_packages[@]}"; do
        voice_install_package "$voice_package"
    done
    printf '\nСтавлю доступные desktop-инструменты…\n'
    for voice_package in "${voice_optional_packages[@]}"; do
        if ! voice_install_package "$voice_package"; then
            printf 'Предупреждение: пакет %s недоступен; будет использован fallback.\n' "$voice_package" >&2
        fi
    done
else
    printf '\nНеизвестный пакетный менеджер: системные пакеты не меняю.\n' >&2
fi

voice_python=""
for voice_python_name in python3 python3.14 python3.13 python3.12 python3.11 python3.10 python3.9 python; do
    voice_python_candidate="$(command -v "$voice_python_name" 2>/dev/null || true)"
    if [[ -n "$voice_python_candidate" ]] \
            && "$voice_python_candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 9))'; then
        voice_python="$voice_python_candidate"
        break
    fi
done
if [[ -z "$voice_python" ]]; then
    printf 'Voice Input нужен Python 3.9+; подходящий Python не найден.\n' >&2
    printf 'Voice Input requires Python 3.9+; no compatible interpreter was found.\n' >&2
    exit 1
fi

voice_group_exists() {
    getent group "$1" >/dev/null 2>&1 || grep -q "^${1}:" /etc/group
}

voice_group_create() {
    local group="$1"
    if voice_group_exists "$group"; then return 0; fi
    if command -v groupadd >/dev/null 2>&1; then
        voice_as_root groupadd --system "$group"
    elif command -v addgroup >/dev/null 2>&1; then
        voice_as_root addgroup -S "$group"
    else
        printf 'Не найден groupadd/addgroup; группа %s не создана.\n' "$group" >&2
        return 1
    fi
}

voice_group_add_user() {
    local group="$1"
    if command -v usermod >/dev/null 2>&1; then
        voice_as_root usermod -aG "$group" "$voice_user"
    elif command -v addgroup >/dev/null 2>&1; then
        voice_as_root addgroup "$voice_user" "$group"
    else
        return 1
    fi
}

voice_state_dir="${XDG_STATE_HOME:-${HOME}/.local/state}/voice-input"
voice_state_file="${voice_state_dir}/install-state"
voice_previous_flag() {
    [[ -f "$voice_state_file" ]] || { printf false; return; }
    sed -n "s/^${1}=//p" "$voice_state_file" | tail -n 1 | grep -E '^(true|false)$' || printf false
}
voice_uinput_group_created="$(voice_previous_flag uinput_group_created)"
voice_voiceinput_group_created="$(voice_previous_flag voiceinput_group_created)"
voice_uinput_membership_added="$(voice_previous_flag uinput_membership_added)"
voice_voiceinput_membership_added="$(voice_previous_flag voiceinput_membership_added)"
voice_ydotool_service_enabled="$(voice_previous_flag ydotool_service_enabled)"
voice_ydotoold_pid="$(sed -n 's/^ydotoold_pid=//p' "$voice_state_file" 2>/dev/null \
    | tail -n 1 | grep -E '^[0-9]+$' || true)"

voice_write_state() {
    mkdir -p "$voice_state_dir"
    printf '%s\n' \
        "repo=${voice_root}" \
        "user=${voice_user}" \
        "package_manager=${voice_pm}" \
        "desktop=${voice_desktop}" \
        "uinput_group_created=${voice_uinput_group_created}" \
        "voiceinput_group_created=${voice_voiceinput_group_created}" \
        "uinput_membership_added=${voice_uinput_membership_added}" \
        "voiceinput_membership_added=${voice_voiceinput_membership_added}" \
        "ydotool_service_enabled=${voice_ydotool_service_enabled}" \
        "ydotoold_pid=${voice_ydotoold_pid}" \
        > "$voice_state_file"
    chmod 600 "$voice_state_file"
}
voice_write_state

voice_stop_daemon() {
    local socket="${XDG_CACHE_HOME:-${HOME}/.cache}/pill/pill.sock"
    if [[ -x "${voice_root}/voice-input" && -x "${voice_venv}/bin/python" ]]; then
        "${voice_root}/voice-input" --quit || true
        for _ in {1..20}; do
            [[ ! -S "$socket" ]] && break
            sleep 0.05
        done
    fi
    # Releases before --quit ignored the command. Match argv exactly so an
    # unrelated Python process is never stopped.
    local proc pid
    local -a command
    for proc in /proc/[0-9]*; do
        [[ -O "$proc" && -r "${proc}/cmdline" ]] || continue
        command=()
        mapfile -d '' -t command < "${proc}/cmdline" || true
        ((${#command[@]} >= 3)) || continue
        if [[ "${command[0]}" == "${voice_venv}/bin/python" \
                && "${command[1]}" == -m && "${command[2]}" == pill ]]; then
            pid="${proc##*/}"
            kill "$pid" 2>/dev/null || true
        fi
    done
}

if ! voice_group_exists uinput; then
    voice_group_create uinput
    voice_uinput_group_created=true
    voice_write_state
fi
if ! voice_group_exists voiceinput; then
    voice_group_create voiceinput
    voice_voiceinput_group_created=true
    voice_write_state
fi
if ! id -nG "$voice_user" | tr ' ' '\n' | grep -qx uinput; then
    voice_group_add_user uinput
    voice_uinput_membership_added=true
    voice_write_state
fi
if ! id -nG "$voice_user" | tr ' ' '\n' | grep -qx voiceinput; then
    voice_group_add_user voiceinput
    voice_voiceinput_membership_added=true
    voice_write_state
fi

voice_tmp="$(mktemp -d "${TMPDIR:-/tmp}/voice-input-install.XXXXXX")"
voice_cleanup() {
    [[ -n "${voice_tmp:-}" && -d "$voice_tmp" ]] && rm -r -- "$voice_tmp"
}
trap voice_cleanup EXIT

printf '%s\n' 'KERNEL=="uinput", MODE="0660", GROUP="uinput", OPTIONS+="static_node=uinput"' \
    > "${voice_tmp}/99-voice-input-uinput.rules"
printf '%s\n' 'SUBSYSTEM=="input", KERNEL=="event*", ENV{ID_INPUT_KEYBOARD}=="1", MODE="0660", GROUP="voiceinput"' \
    > "${voice_tmp}/99-voice-input-keyboard.rules"

if [[ -d /etc/udev/rules.d ]] || command -v udevadm >/dev/null 2>&1; then
    for voice_rule in 99-voice-input-uinput.rules 99-voice-input-keyboard.rules; do
        voice_target="/etc/udev/rules.d/${voice_rule}"
        if [[ -f "$voice_target" && ! -f "${voice_target}.before-voice-input.bak" ]]; then
            voice_as_root cp -a "$voice_target" "${voice_target}.before-voice-input.bak"
        fi
        voice_as_root install -Dm644 "${voice_tmp}/${voice_rule}" "$voice_target"
    done
    voice_as_root modprobe uinput 2>/dev/null || true
    if command -v udevadm >/dev/null 2>&1; then
        voice_as_root udevadm control --reload-rules || true
        voice_as_root udevadm trigger --subsystem-match=input --action=add || true
        voice_as_root udevadm trigger --action=add /sys/class/misc/uinput 2>/dev/null || true
    fi
else
    printf 'Предупреждение: udev не найден; постоянные права evdev/uinput не установлены.\n' >&2
fi

# ACL lets the current login use the devices before the next logout/login.
if command -v setfacl >/dev/null 2>&1; then
    if [[ -e /dev/uinput ]]; then
        voice_as_root setfacl -m "u:${voice_user}:rw" /dev/uinput || true
    fi
    for voice_event in /dev/input/event*; do
        [[ -e "$voice_event" ]] || continue
        if ! command -v udevadm >/dev/null 2>&1 \
                || udevadm info --query=property --name="$voice_event" 2>/dev/null \
                    | grep -q '^ID_INPUT_KEYBOARD=1$'; then
            voice_as_root setfacl -m "u:${voice_user}:rw" "$voice_event" || true
        fi
    done
fi

voice_backup_user_file() {
    local target="$1"
    local backup="${target}.before-voice-input.bak"
    if [[ -f "$target" && ! -f "$backup" ]] \
            && ! grep -qE '^(X-VoiceInput-Managed=true|# Managed by Voice Input)$' "$target"; then
        cp -a -- "$target" "$backup"
    fi
}

if command -v ydotoold >/dev/null 2>&1; then
    if command -v systemctl >/dev/null 2>&1 && systemctl --user show-environment >/dev/null 2>&1; then
        if systemctl --user cat ydotool.service >/dev/null 2>&1; then
            if ! systemctl --user is-enabled --quiet ydotool.service; then
                voice_ydotool_service_enabled=true
            fi
            systemctl --user enable --now ydotool.service || true
        else
            voice_systemd_dir="${XDG_CONFIG_HOME:-${HOME}/.config}/systemd/user"
            mkdir -p "$voice_systemd_dir"
            voice_ydotool_unit="${voice_systemd_dir}/voice-input-ydotoold.service"
            if [[ -f "$voice_ydotool_unit" ]] \
                    && ! grep -qE '^(# Managed by Voice Input|Description=Virtual keyboard daemon for Voice Input)$' "$voice_ydotool_unit"; then
                printf 'Не заменяю существующий user service: %s\n' "$voice_ydotool_unit" >&2
            else
                printf '%s\n' \
                    '# Managed by Voice Input' \
                    '[Unit]' \
                    'Description=Virtual keyboard daemon for Voice Input' \
                    'StartLimitIntervalSec=0' \
                    '' \
                    '[Service]' \
                    "ExecStart=$(command -v ydotoold)" \
                    'Restart=on-failure' \
                    'RestartSec=2' \
                    '' \
                    '[Install]' \
                    'WantedBy=default.target' \
                    > "$voice_ydotool_unit"
                systemctl --user daemon-reload
                systemctl --user enable --now voice-input-ydotoold.service || true
            fi
        fi
    elif ! pgrep -u "$(id -u)" -x ydotoold >/dev/null 2>&1; then
        nohup ydotoold >"${voice_tmp}/ydotoold.log" 2>&1 </dev/null &
        voice_ydotoold_pid=$!
    fi
fi
voice_write_state

voice_stop_daemon
printf '\nСоздаю Python-окружение… / Creating Python environment…\n'
if ! "$voice_python" -m venv "$voice_venv"; then
    "$voice_python" -m virtualenv "$voice_venv"
fi
"${voice_venv}/bin/python" -m pip install --upgrade pip
"${voice_venv}/bin/python" -m pip install -r "${voice_root}/requirements.txt"

if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1; then
    printf '\nNVIDIA найдена: ставлю cuBLAS/cuDNN…\n'
    if ! "${voice_venv}/bin/python" -m pip install nvidia-cublas-cu12 nvidia-cudnn-cu12; then
        printf 'CUDA-библиотеки не установились; будет использован CPU.\n' >&2
    fi
else
    printf '\nNVIDIA не найдена: распознавание будет работать на CPU.\n'
fi

if ! $voice_skip_model; then
    printf '\nСкачиваю и проверяю модели… / Downloading and checking models…\n'
    if ! env PYTHONPATH="$voice_root" "${voice_venv}/bin/python" - <<'PY'
from pill import config
from pill.audio_recorder import resolve_vad_model
from pill.stt_engine import SttEngine

cfg = config.load()
print("Silero VAD:", resolve_vad_model(cfg.get("vad_model_path")))
print("Whisper:", cfg["model"])
SttEngine(cfg)._ensure_model()
PY
    then
        printf 'Модель не скачалась сейчас; приложение повторит загрузку при запуске.\n' >&2
    fi
fi

voice_root_sed="${voice_root//\\/\\\\}"
voice_root_sed="${voice_root_sed//&/\\&}"
voice_root_sed="${voice_root_sed//|/\\|}"
sed "s|@PILL_ROOT@|${voice_root_sed}|g" "${voice_root}/voice-input.desktop" \
    > "${voice_tmp}/voice-input.desktop"
sed "s|@PILL_ROOT@|${voice_root_sed}|g" "${voice_root}/voice-input-autostart.desktop" \
    > "${voice_tmp}/voice-input-autostart.desktop"
if command -v desktop-file-validate >/dev/null 2>&1; then
    desktop-file-validate "${voice_tmp}/voice-input.desktop"
    desktop-file-validate "${voice_tmp}/voice-input-autostart.desktop"
fi
voice_apps="${XDG_DATA_HOME:-${HOME}/.local/share}/applications"
voice_autostart="${XDG_CONFIG_HOME:-${HOME}/.config}/autostart"
voice_backup_user_file "${voice_apps}/voice-input.desktop"
voice_backup_user_file "${voice_autostart}/voice-input.desktop"
install -Dm644 "${voice_tmp}/voice-input.desktop" "${voice_apps}/voice-input.desktop"
install -Dm644 "${voice_tmp}/voice-input-autostart.desktop" "${voice_autostart}/voice-input.desktop"
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$voice_apps" >/dev/null 2>&1 || true
fi

voice_bin_dir="${HOME}/.local/bin"
mkdir -p "$voice_bin_dir"
if [[ ! -e "${voice_bin_dir}/voice-input" \
        || -L "${voice_bin_dir}/voice-input" && "$(readlink -f "${voice_bin_dir}/voice-input")" == "${voice_root}/voice-input" ]]; then
    ln -sfn "${voice_root}/voice-input" "${voice_bin_dir}/voice-input"
else
    printf 'Не заменяю существующий %s/voice-input; используйте %s/voice-input.\n' "$voice_bin_dir" "$voice_root" >&2
fi

env VOICE_INPUT_DESKTOP="$voice_desktop" VOICE_INPUT_NEW_CONFIG="$voice_new_config" \
    PYTHONPATH="$voice_root" "${voice_venv}/bin/python" - <<'PY'
import os

from pill import config, desktop_integration

cfg = config.load()
desktop = os.environ.get("VOICE_INPUT_DESKTOP", "")
# A printable global key is unreliable in GNOME and leaks into focused fields
# with a read-only evdev fallback. Keep GRAVE only for native Hyprland installs.
if (os.environ.get("VOICE_INPUT_NEW_CONFIG") == "true" and cfg["hotkey"] == "grave"
        and desktop != "hyprland"):
    cfg["hotkey"] = "ctrl+alt+space"
    config.save(cfg)
native = desktop_integration.install(cfg["hotkey"], cfg.get("pill_position", "bottom"))
# A lone printable key leaks into the focused field when evdev is only reading
# events. Fresh fallback installs therefore use a non-printing combination.
if not native and os.environ.get("VOICE_INPUT_NEW_CONFIG") == "true" and cfg["hotkey"] == "grave":
    cfg["hotkey"] = "ctrl+alt+space"
    config.save(cfg)
    desktop_integration.install(cfg["hotkey"], cfg.get("pill_position", "bottom"))
PY

voice_write_state

if [[ -n "${WAYLAND_DISPLAY:-}${DISPLAY:-}" ]]; then
    voice_log_dir="${XDG_CACHE_HOME:-${HOME}/.cache}/pill"
    mkdir -p "$voice_log_dir"
    nohup "${voice_root}/voice-input" >>"${voice_log_dir}/daemon.log" 2>&1 </dev/null &
    sleep 1
    "${voice_root}/voice-input" --diag || true
fi

voice_hotkey="$(env PYTHONPATH="$voice_root" "${voice_venv}/bin/python" - <<'PY'
from pill import config
print(config.load()["hotkey"])
PY
)"
voice_hotkey="${voice_hotkey^^}"
[[ "$voice_hotkey" == GRAVE ]] && voice_hotkey='GRAVE (`)'
printf '\n================================================================\n'
printf 'ГОЛОСОВОЙ ВВОД ЗАПУСКАЕТСЯ КЛАВИШЕЙ: %s\n' "$voice_hotkey"
printf 'VOICE INPUT HOTKEY: %s\n' "$voice_hotkey"
printf '================================================================\n'
printf 'Если нашли ошибку, напишите в Telegram: @nyavke — https://t.me/nyavke\n'
printf 'If you find a bug, message me on Telegram: @nyavke — https://t.me/nyavke\n'
if ! id -nG | tr ' ' '\n' | grep -qx uinput \
        || ! id -nG | tr ' ' '\n' | grep -qx voiceinput; then
    printf 'Для постоянных прав выйдите из сеанса и войдите снова.\n'
    printf 'Log out and back in once to activate permanent device permissions.\n'
fi
