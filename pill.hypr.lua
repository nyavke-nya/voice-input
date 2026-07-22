-- Референс Hyprland Voice Input. Установщик ставит этот блок сам в
-- ~/.config/caelestia/hypr-user.lua при первом запуске и при смене хоткея.
-- Файл здесь — на случай ручной установки или другого расположения конфига.
--
-- Замени "GRAVE" на свой бинд (имя XKB-keysym: A, SPACE, F9, GRAVE=backtick…),
-- а путь python — на свой venv.

-- >>> pill managed integration >>>
hl.on("hyprland.start", function()
    hl.exec_cmd("env PYTHONPATH=/home/user/hyprland-voice-input /home/user/hyprland-voice-input/.venv/bin/python -m pill")
end)  -- фоновый демон

hl.bind("GRAVE",
    hl.dsp.exec_cmd("env PYTHONPATH=/home/user/hyprland-voice-input /home/user/hyprland-voice-input/.venv/bin/python -m pill --toggle"),
    { release = true })

hl.window_rule({
    name             = "pill-overlay",
    match            = { class = "^pill$" },
    float            = true,
    pin              = true,
    no_initial_focus = true,
    no_anim          = true,
    no_dim           = true,
    no_shadow        = true,
    border_size      = 0,
    rounding         = 0,
    opacity          = "1.0 override",
    size             = "400 960",
    move             = "(monitor_w*0.5-window_w*0.5) (monitor_h*0.985-window_h)",  -- низ по центру
})
-- <<< pill managed integration <<<


---------------------------------------------------------------------------
-- Для vanilla-Hyprland (обычный hyprland.conf, БЕЗ Lua) эквивалент такой:
--
--   exec-once = env PYTHONPATH=/home/user/hyprland-voice-input /home/user/hyprland-voice-input/.venv/bin/python -m pill
--   bind = , grave, exec, env PYTHONPATH=/home/user/hyprland-voice-input /home/user/hyprland-voice-input/.venv/bin/python -m pill --toggle
--   windowrulev2 = float,      class:^(pill)$
--   windowrulev2 = pin,        class:^(pill)$
--   windowrulev2 = noborder,   class:^(pill)$
--   windowrulev2 = noshadow,   class:^(pill)$
--   windowrulev2 = size 400 960, class:^(pill)$
--   windowrulev2 = move 50% 98%-960, class:^(pill)$
---------------------------------------------------------------------------
