#!/usr/bin/env bash
# Remove Voice Input integration without removing shared distro packages.
set -Eeuo pipefail

voice_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
voice_venv="${voice_root}/.venv"
voice_user="$(id -un)"
voice_dry_run=false
voice_purge=false

if [[ ! -f "${voice_root}/requirements.txt" || ! -f "${voice_root}/pill/__main__.py" ]]; then
    printf 'uninstall.sh должен находиться в корне репозитория Voice Input.\n' >&2
    exit 1
fi

voice_usage() {
    printf 'Использование / Usage: %s [--dry-run] [--purge]\n' "$0"
}

while (($#)); do
    case "$1" in
        --dry-run) voice_dry_run=true ;;
        --purge) voice_purge=true ;;
        -h|--help) voice_usage; exit 0 ;;
        *) voice_usage >&2; exit 2 ;;
    esac
    shift
done

if ((EUID == 0)) && ! $voice_dry_run; then
    printf 'Запустите %s обычным пользователем, не через sudo.\n' "$0" >&2
    exit 1
fi

voice_config_home="${XDG_CONFIG_HOME:-${HOME}/.config}"
voice_data_home="${XDG_DATA_HOME:-${HOME}/.local/share}"
voice_cache_home="${XDG_CACHE_HOME:-${HOME}/.cache}"
voice_state_home="${XDG_STATE_HOME:-${HOME}/.local/state}"
voice_state_file="${voice_state_home}/voice-input/install-state"

voice_state_flag() {
    [[ -f "$voice_state_file" ]] || { printf false; return; }
    sed -n "s/^${1}=//p" "$voice_state_file" | tail -n 1 | grep -E '^(true|false)$' || printf false
}

voice_uinput_group_created="$(voice_state_flag uinput_group_created)"
voice_voiceinput_group_created="$(voice_state_flag voiceinput_group_created)"
voice_uinput_membership_added="$(voice_state_flag uinput_membership_added)"
voice_voiceinput_membership_added="$(voice_state_flag voiceinput_membership_added)"
voice_ydotool_service_enabled="$(voice_state_flag ydotool_service_enabled)"
voice_ydotoold_pid="$(sed -n 's/^ydotoold_pid=//p' "$voice_state_file" 2>/dev/null \
    | tail -n 1 | grep -E '^[0-9]+$' || true)"

printf '\nVOICE INPUT — УДАЛЕНИЕ / UNINSTALL\n'
printf '  • остановить фоновый процесс / stop the daemon\n'
printf '  • удалить XDG autostart, launcher и native bind\n'
printf '  • удалить %s\n' "$voice_venv"
printf '  • удалить app-owned udev rules и права групп\n'
printf '  • оставить общие системные пакеты и Hugging Face cache\n'
if $voice_purge; then
    printf '  • PURGE: удалить ~/.config/pill и ~/.cache/pill\n'
else
    printf '  • сохранить настройки, статистику и пользовательский cache\n'
fi

if $voice_dry_run; then
    printf '\nDry-run: ничего не удалено. / Nothing was removed.\n'
    exit 0
fi

if command -v sudo >/dev/null 2>&1; then
    voice_priv=(sudo)
elif command -v doas >/dev/null 2>&1; then
    voice_priv=(doas)
else
    printf 'Нужен sudo или doas для удаления udev-правил и групп.\n' >&2
    exit 1
fi
voice_as_root() {
    "${voice_priv[@]}" "$@"
}

voice_stop_daemon() {
    local socket="${XDG_CACHE_HOME:-${HOME}/.cache}/pill/pill.sock"
    if [[ -x "${voice_root}/voice-input" && -x "${voice_venv}/bin/python" ]]; then
        "${voice_root}/voice-input" --quit || true
        for _ in {1..20}; do
            [[ ! -S "$socket" ]] && break
            sleep 0.05
        done
    fi
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

voice_file_is_managed() {
    local target="$1"
    [[ -f "$target" ]] || return 1
    grep -qE '^(X-VoiceInput-Managed=true|# Managed by Voice Input|Description=Virtual keyboard daemon for Voice Input)$' "$target" \
        || { grep -Fq -- "$voice_root" "$target" && grep -q -- '-m pill' "$target"; }
}

voice_restore_or_remove() {
    local target="$1"
    local backup="${target}.before-voice-input.bak"
    if [[ -f "$backup" ]]; then
        if [[ ! -e "$target" ]] || voice_file_is_managed "$target"; then
            mv -f -- "$backup" "$target"
        else
            printf 'Не трогаю изменённый файл %s; резервная копия: %s\n' "$target" "$backup" >&2
        fi
    elif voice_file_is_managed "$target"; then
        rm -f -- "$target"
    fi
}

printf '\nВНИМАНИЕ: будут удалены только файлы Voice Input и его точечные правила в /etc.\n'
printf 'WARNING: only Voice Input files and its narrow /etc rules will be removed.\n'
voice_as_root true

voice_stop_daemon
if [[ -n "$voice_ydotoold_pid" ]] \
        && [[ "$(ps -o user= -p "$voice_ydotoold_pid" 2>/dev/null | xargs)" == "$voice_user" ]] \
        && [[ "$(ps -o comm= -p "$voice_ydotoold_pid" 2>/dev/null | xargs)" == ydotoold ]]; then
    kill "$voice_ydotoold_pid" 2>/dev/null || true
fi

voice_python=""
if [[ -x "${voice_venv}/bin/python" ]]; then
    voice_python="${voice_venv}/bin/python"
else
    for voice_python_name in python3 python3.14 python3.13 python3.12 python3.11 python3.10 python3.9 python; do
        voice_python_candidate="$(command -v "$voice_python_name" 2>/dev/null || true)"
        if [[ -n "$voice_python_candidate" ]] \
                && "$voice_python_candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 9))'; then
            voice_python="$voice_python_candidate"
            break
        fi
    done
fi
if [[ -n "$voice_python" ]]; then
    env PYTHONPATH="$voice_root" "$voice_python" -m pill.desktop_integration --uninstall || \
        printf 'Предупреждение: не все native bind-блоки удалось удалить.\n' >&2
fi

voice_own_unit="${voice_config_home}/systemd/user/voice-input-ydotoold.service"
if command -v systemctl >/dev/null 2>&1 && systemctl --user show-environment >/dev/null 2>&1; then
    if voice_file_is_managed "$voice_own_unit"; then
        systemctl --user disable --now voice-input-ydotoold.service >/dev/null 2>&1 || true
    fi
    if [[ "$voice_ydotool_service_enabled" == true ]]; then
        systemctl --user disable --now ydotool.service >/dev/null 2>&1 || true
    fi
fi
voice_restore_or_remove "$voice_own_unit"

# Compatibility cleanup for the first Arch-only installer.
voice_legacy_override="${voice_config_home}/systemd/user/ydotool.service.d/override.conf"
if [[ -f "$voice_legacy_override" ]] \
        && grep -q 'При SDDM-автологине /dev/uinput' "$voice_legacy_override"; then
    rm -f -- "$voice_legacy_override"
    rmdir -- "$(dirname -- "$voice_legacy_override")" 2>/dev/null || true
fi
if command -v systemctl >/dev/null 2>&1; then
    systemctl --user daemon-reload >/dev/null 2>&1 || true
fi

voice_restore_or_remove "${voice_data_home}/applications/voice-input.desktop"
voice_restore_or_remove "${voice_config_home}/autostart/voice-input.desktop"
voice_legacy_desktop="${voice_data_home}/applications/pill.desktop"
if voice_file_is_managed "$voice_legacy_desktop"; then
    rm -f -- "$voice_legacy_desktop"
fi
voice_bin="${HOME}/.local/bin/voice-input"
if [[ -L "$voice_bin" && "$(readlink -f "$voice_bin")" == "${voice_root}/voice-input" ]]; then
    rm -f -- "$voice_bin"
fi
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${voice_data_home}/applications" >/dev/null 2>&1 || true
fi

for voice_rule in \
    /etc/udev/rules.d/99-voice-input-uinput.rules \
    /etc/udev/rules.d/99-voice-input-keyboard.rules; do
    if [[ -f "${voice_rule}.before-voice-input.bak" ]]; then
        voice_as_root mv -f -- "${voice_rule}.before-voice-input.bak" "$voice_rule"
    elif [[ -e "$voice_rule" ]]; then
        voice_as_root rm -f -- "$voice_rule"
    fi
done
voice_legacy_rule=/etc/udev/rules.d/99-pill-uinput.rules
if [[ -f "${voice_legacy_rule}.before-pill.bak" ]]; then
    voice_as_root mv -f -- "${voice_legacy_rule}.before-pill.bak" "$voice_legacy_rule"
elif [[ -e "$voice_legacy_rule" ]]; then
    voice_as_root rm -f -- "$voice_legacy_rule"
fi
if command -v udevadm >/dev/null 2>&1; then
    voice_as_root udevadm control --reload-rules || true
    voice_as_root udevadm trigger --subsystem-match=input --action=add || true
fi

voice_remove_membership() {
    local group="$1"
    if command -v gpasswd >/dev/null 2>&1; then
        voice_as_root gpasswd -d "$voice_user" "$group" >/dev/null 2>&1 || true
    elif command -v delgroup >/dev/null 2>&1; then
        voice_as_root delgroup "$voice_user" "$group" >/dev/null 2>&1 || true
    fi
}
[[ "$voice_voiceinput_membership_added" == true ]] && voice_remove_membership voiceinput
[[ "$voice_uinput_membership_added" == true ]] && voice_remove_membership uinput

voice_delete_empty_group() {
    local group="$1"
    local created="$2"
    [[ "$created" == true ]] || return 0
    local members
    members="$(getent group "$group" 2>/dev/null | cut -d: -f4 || true)"
    [[ -z "$members" ]] || return 0
    if command -v groupdel >/dev/null 2>&1; then
        voice_as_root groupdel "$group" || true
    elif command -v delgroup >/dev/null 2>&1; then
        voice_as_root delgroup "$group" || true
    fi
}
voice_delete_empty_group voiceinput "$voice_voiceinput_group_created"
voice_delete_empty_group uinput "$voice_uinput_group_created"

if [[ -d "$voice_venv" ]]; then
    rm -rf -- "$voice_venv"
fi
rm -f -- "$voice_state_file"
rmdir -- "${voice_state_home}/voice-input" 2>/dev/null || true

if $voice_purge; then
    [[ -d "${voice_config_home}/pill" ]] && rm -rf -- "${voice_config_home}/pill"
    [[ -d "${voice_cache_home}/pill" ]] && rm -rf -- "${voice_cache_home}/pill"
fi

printf '\nVoice Input удалён. Общие пакеты и общий Hugging Face cache сохранены.\n'
printf 'Voice Input was removed. Shared packages and the shared Hugging Face cache were kept.\n'
printf 'Изменение групп окончательно применится после следующего входа в сеанс.\n'
