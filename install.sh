#!/usr/bin/env bash
# Автоустановка Hyprland Voice Input для Arch/CachyOS + Hyprland/caelestia.
# Запускать обычным пользователем: ./install.sh
set -Eeuo pipefail

pill_repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
pill_venv_dir="${pill_repo_dir}/.venv"
pill_target_user="$(id -un)"
pill_dry_run=false

case "${1:-}" in
    "") ;;
    --dry-run) pill_dry_run=true ;;
    *) printf 'Использование: %s [--dry-run]\n' "$0" >&2; exit 2 ;;
esac

if (( EUID == 0 )); then
    printf 'Запустите %s обычным пользователем, не через sudo.\n' "$0" >&2
    exit 1
fi
if [[ "$pill_repo_dir" =~ [[:space:]] ]]; then
    printf 'Путь к проекту не должен содержать пробелы: %s\n' "$pill_repo_dir" >&2
    exit 1
fi
if [[ ! -f "${pill_repo_dir}/requirements.txt" || ! -f "${pill_repo_dir}/pill/__main__.py" ]]; then
    printf 'Скрипт должен лежать в корне репозитория Hyprland Voice Input.\n' >&2
    exit 1
fi
if ! command -v pacman >/dev/null; then
    printf 'Этот установщик рассчитан на Arch/CachyOS с pacman.\n' >&2
    exit 1
fi

pill_hypr_entry="${XDG_CONFIG_HOME:-${HOME}/.config}/hypr/hyprland.lua"
pill_hypr_version="$(pacman -Q hyprland 2>/dev/null | cut -d ' ' -f2 || true)"
if [[ "$pill_hypr_version" != 0.55.* ]] \
        || ! pacman -Q caelestia-shell >/dev/null 2>&1 \
        || ! command -v caelestia >/dev/null \
        || [[ ! -f "$pill_hypr_entry" ]] \
        || ! grep -q 'caelestia/hypr-user.lua' "$pill_hypr_entry"; then
    printf '%s\n' \
        'ОТКАЗ: Hyprland Voice Input пока устанавливается только в Hyprland 0.55.x с caelestia-shell' \
        'и Lua-конфигом ~/.config/hypr/hyprland.lua, подключающим caelestia/hypr-user.lua.' \
        'REFUSED: Hyprland Voice Input currently installs only on Hyprland 0.55.x with caelestia-shell and' \
        'a Lua ~/.config/hypr/hyprland.lua that loads caelestia/hypr-user.lua.' >&2
    exit 1
fi

pill_packages=(
    python python-pip
    wtype ydotool wl-clipboard
    portaudio libnotify desktop-file-utils
)

printf '\nHyprland Voice Input: автоматическая установка из %s\n' "$pill_repo_dir"
printf '  • pacman: %s\n' "${pill_packages[*]}"
printf '  • Python venv + requirements.txt\n'
printf '  • CUDA-библиотеки, если найдена NVIDIA\n'
printf '  • Silero VAD + выбранная модель Whisper\n'
printf '  • desktop-ярлык и Lua-интеграция caelestia/Hyprland\n'
printf '  • /etc/udev/rules.d/99-pill-uinput.rules и ydotool.service\n\n'

if $pill_dry_run; then
    printf 'Dry-run: файлы и система не изменены.\n'
    exit 0
fi

if ! command -v sudo >/dev/null; then
    printf 'Нужен sudo для pacman и одного udev-правила.\n' >&2
    exit 1
fi

# Единственные системные изменения: пакеты, группа uinput и точечное udev-правило.
# Группу input не используем: она дала бы доступ к чужим нажатиям.
sudo -v
sudo pacman -S --needed --noconfirm "${pill_packages[@]}"

if ! getent group uinput >/dev/null; then
    sudo groupadd --system uinput
fi
sudo usermod -aG uinput "$pill_target_user"

pill_tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/pill-install.XXXXXX")"
trap 'rm -r -- "$pill_tmp_dir"' EXIT

printf '%s\n' 'KERNEL=="uinput", MODE="0660", GROUP="uinput", OPTIONS+="static_node=uinput"' \
    > "${pill_tmp_dir}/99-pill-uinput.rules"
if [[ -f /etc/udev/rules.d/99-pill-uinput.rules \
        && ! -f /etc/udev/rules.d/99-pill-uinput.rules.before-pill.bak ]]; then
    sudo cp -a /etc/udev/rules.d/99-pill-uinput.rules \
        /etc/udev/rules.d/99-pill-uinput.rules.before-pill.bak
fi
sudo install -Dm644 "${pill_tmp_dir}/99-pill-uinput.rules" \
    /etc/udev/rules.d/99-pill-uinput.rules
sudo modprobe uinput
sudo udevadm control --reload-rules
sudo udevadm trigger --action=add /sys/class/misc/uinput 2>/dev/null || true

pill_systemd_dir="${XDG_CONFIG_HOME:-${HOME}/.config}/systemd/user/ydotool.service.d"
mkdir -p "$pill_systemd_dir"
if [[ -f "${pill_systemd_dir}/override.conf" \
        && ! -f "${pill_systemd_dir}/override.conf.before-pill.bak" ]]; then
    cp -a "${pill_systemd_dir}/override.conf" \
        "${pill_systemd_dir}/override.conf.before-pill.bak"
fi
printf '%s\n' \
    '[Unit]' \
    '# При SDDM-автологине /dev/uinput может появиться позже user-service.' \
    'StartLimitIntervalSec=0' \
    '' \
    '[Service]' \
    'RestartSec=2s' \
    > "${pill_systemd_dir}/override.conf"
if systemctl --user daemon-reload 2>/dev/null; then
    systemctl --user enable ydotool.service
    if [[ -w /dev/uinput ]]; then
        systemctl --user restart ydotool.service
    fi
else
    printf 'Предупреждение: user-systemd недоступен; ydotool включится после входа.\n' >&2
fi

printf '\nСоздаю venv и ставлю Python-зависимости…\n'
python -m venv "$pill_venv_dir"
"${pill_venv_dir}/bin/python" -m pip install --upgrade pip
"${pill_venv_dir}/bin/python" -m pip install -r "${pill_repo_dir}/requirements.txt"

if command -v nvidia-smi >/dev/null && nvidia-smi -L >/dev/null 2>&1; then
    printf '\nНайдена NVIDIA: ставлю cuBLAS/cuDNN для GPU-распознавания…\n'
    "${pill_venv_dir}/bin/python" -m pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
else
    printf '\nNVIDIA не найдена: распознавание будет работать на CPU.\n'
fi

printf '\nСкачиваю и проверяю модели…\n'
env PYTHONPATH="$pill_repo_dir" "${pill_venv_dir}/bin/python" - <<'PY'
from pill import config
from pill.audio_recorder import resolve_vad_model
from pill.stt_engine import SttEngine

cfg = config.load()
print("Silero VAD:", resolve_vad_model(cfg.get("vad_model_path")))
print("Whisper:", cfg["model"])
SttEngine(cfg)._ensure_model()
PY

pill_applications_dir="${XDG_DATA_HOME:-${HOME}/.local/share}/applications"
pill_repo_sed="${pill_repo_dir//\\/\\\\}"
pill_repo_sed="${pill_repo_sed//&/\\&}"
pill_repo_sed="${pill_repo_sed//|/\\|}"
sed "s|@PILL_ROOT@|${pill_repo_sed}|g" "${pill_repo_dir}/pill.desktop" \
    > "${pill_tmp_dir}/pill.desktop"
desktop-file-validate "${pill_tmp_dir}/pill.desktop"
install -Dm644 "${pill_tmp_dir}/pill.desktop" "${pill_applications_dir}/pill.desktop"
update-desktop-database "$pill_applications_dir" >/dev/null 2>&1 || true

pill_caelestia_dir="${XDG_CONFIG_HOME:-${HOME}/.config}/caelestia"
pill_hypr_user="${pill_caelestia_dir}/hypr-user.lua"
mkdir -p "$pill_caelestia_dir"
if [[ -f "$pill_hypr_user" && ! -f "${pill_hypr_user}.pill-before-install.bak" ]]; then
    cp -a "$pill_hypr_user" "${pill_hypr_user}.pill-before-install.bak"
fi
touch "$pill_hypr_user"

env PYTHONPATH="$pill_repo_dir" "${pill_venv_dir}/bin/python" - <<'PY'
from pill import config, hypr

cfg = config.load()
if not hypr.install(cfg["hotkey"], cfg.get("pill_position", "bottom")):
    raise SystemExit("не удалось установить Lua-интеграцию Hyprland")
print("Hyprland bind:", cfg["hotkey"])
PY

if [[ -n "${WAYLAND_DISPLAY:-}" && -n "${HYPRLAND_INSTANCE_SIGNATURE:-}" ]]; then
    pill_log_dir="${XDG_CACHE_HOME:-${HOME}/.cache}/pill"
    mkdir -p "$pill_log_dir"
    nohup env PYTHONPATH="$pill_repo_dir" "${pill_venv_dir}/bin/python" -m pill \
        >> "${pill_log_dir}/daemon.log" 2>&1 </dev/null &
    sleep 1
    env PYTHONPATH="$pill_repo_dir" "${pill_venv_dir}/bin/python" -m pill --diag
fi

printf '\nHyprland Voice Input установлен. Откройте его в лаунчере или нажмите бинд.\n'
if ! id -nG | tr ' ' '\n' | grep -qx uinput; then
    printf 'Для фолбэка ydotool один раз выйдите из сессии и войдите снова.\n'
fi

pill_hotkey="$(env PYTHONPATH="$pill_repo_dir" "${pill_venv_dir}/bin/python" - <<'PY'
from pill import config
print(config.load()["hotkey"].upper())
PY
)"
if [[ "$pill_hotkey" == GRAVE ]]; then
    pill_hotkey='GRAVE (`)'
fi
printf '\n============================================================\n'
printf 'ГОЛОСОВОЙ ВВОД ЗАПУСКАЕТСЯ КЛАВИШЕЙ: %s\n' "$pill_hotkey"
printf 'VOICE INPUT HOTKEY: %s\n' "$pill_hotkey"
printf '============================================================\n'
