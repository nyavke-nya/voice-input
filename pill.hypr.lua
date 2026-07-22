-- Референс Voice Input для Hyprland 0.55+. Установщик ставит этот блок сам в
-- пользовательский Lua-конфиг при первом запуске и при смене хоткея.
-- Файл здесь — на случай ручной установки или другого расположения конфига.
--
-- Замени "GRAVE" на свой бинд (имя XKB-keysym: A, SPACE, F9, GRAVE=backtick…),
-- а путь /home/user/voice-input — на каталог репозитория.

-- >>> pill managed integration >>>
hl.on("hyprland.start", function()
    hl.exec_cmd("/home/user/voice-input/voice-input")
end)  -- фоновый демон

hl.bind("GRAVE",
    hl.dsp.exec_cmd("/home/user/voice-input/voice-input --toggle"),
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
-- Для Hyprland <= 0.54 (старый hyprland.conf) эквивалент такой:
--
--   exec-once = /home/user/voice-input/voice-input
--   bindr = , grave, exec, /home/user/voice-input/voice-input --toggle
--   windowrulev2 = float,      class:^(pill)$
--   windowrulev2 = pin,        class:^(pill)$
--   windowrulev2 = noborder,   class:^(pill)$
--   windowrulev2 = noshadow,   class:^(pill)$
--   windowrulev2 = size 400 960, class:^(pill)$
--   windowrulev2 = move 50% 98%-960, class:^(pill)$
---------------------------------------------------------------------------
