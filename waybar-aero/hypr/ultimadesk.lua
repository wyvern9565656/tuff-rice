-- >>> UltimaDesk managed >>>
local home = os.getenv("HOME") or ""
local config = home .. "/.config/waybar-aero/"
local data = home .. "/.local/share/ultimadesk/"

hl.monitor({
    output = "VGA-1",
    mode = "1368x768@59.71",
    position = "auto",
    scale = 1,
})

hl.config({
    input = {
        kb_layout = "br",
    },
    cursor = {
        no_warps = true,
    },
    decoration = {
        rounding = 18,
        blur = {
            enabled = true,
            size = 7,
            passes = 2,
        },
    },
})

hl.animation({ leaf = "workspaces", enabled = true, speed = 20, bezier = "default", style = "slide" })
hl.animation({ leaf = "workspacesIn", enabled = true, speed = 20, bezier = "default", style = "slide" })
hl.animation({ leaf = "workspacesOut", enabled = true, speed = 20, bezier = "default", style = "slide" })

for workspace = 1, 10 do
    hl.workspace_rule({ workspace = tostring(workspace), persistent = false })
end

hl.window_rule({
    name = "ultimadesk-shell",
    match = { class = "^aero-shell[.]py$" },
    float = true,
    border_size = 0,
})
hl.window_rule({
    name = "ultimadesk-launcher",
    match = { class = "^aero-launcher[.]py$" },
    float = true,
    border_size = 0,
})
hl.window_rule({
    name = "ultimadesk-workspaces",
    match = { class = "^aero-workspaces[.]py$" },
    float = true,
    border_size = 0,
})
hl.window_rule({
    name = "ultimadesk-player",
    match = { class = "^aero-player[.]py$" },
    float = true,
    border_size = 0,
})

local panelRules = {
    { name = "shortcuts", title = "^UltimaDesk$", size = "420 340", move = "84 40" },
    { name = "wifi", title = "^UltimaDesk Wi-Fi$", size = "420 420", move = "monitor_w-614 40" },
    { name = "bluetooth", title = "^UltimaDesk Bluetooth$", size = "420 420", move = "monitor_w-536 40" },
    { name = "audio", title = "^UltimaDesk Audio$", size = "420 400", move = "monitor_w-668 40" },
    { name = "control", title = "^Centro de controle$", size = "460 520", move = "84 40" },
    { name = "notifications", title = "^Notificacoes$", size = "480 560", move = "84 40" },
    { name = "calendar", title = "^Calendario$", size = "366 410", move = "monitor_w-373 40" },
    { name = "player", title = "^UltimaDesk Player$", size = "342 470", move = "513 44" },
    { name = "wallpapers", title = "^UltimaDesk Wallpapers$", size = "1120 286", move = "124 44" },
}

for _, panel in ipairs(panelRules) do
    hl.window_rule({
        name = "ultimadesk-panel-" .. panel.name,
        match = { title = panel.title },
        float = true,
        size = panel.size,
        move = panel.move,
    })
end

local function bind(key, dispatcher, flags)
    hl.bind(key, dispatcher, flags)
end

local function exec(key, command, flags)
    bind(key, hl.dsp.exec_cmd(command), flags)
end

local mainMod = "SUPER"
local lockedRepeat = { locked = true, repeating = true }

exec(mainMod .. " + Return", "kitty")
exec(mainMod .. " + E", "thunar")
exec(mainMod .. " + D", config .. "aero-launcher.sh")
exec(mainMod .. " + R", config .. "aero-launcher.sh")
exec(mainMod .. " + B", "xdg-open https://")
exec(mainMod .. " + I", config .. "aero-control.sh")
exec(mainMod .. " + W", "python3 " .. data .. "aero-workspaces.py")
exec(mainMod .. " + SHIFT + W", config .. "wallpaper-carousel.sh")
exec(
    mainMod .. " + V",
    "sh -c 'cliphist list | rofi -theme " .. data .. "rofi.rasi -dmenu -p Clipboard | cliphist decode | wl-copy'"
)
exec(mainMod .. " + L", config .. "lock-screen.sh")
exec(mainMod .. " + M", config .. "power-menu.sh")
exec(mainMod .. " + SHIFT + S", config .. "screenshot-menu.sh")
exec("Print", config .. "screenshot-menu.sh")
exec(mainMod .. " + Print", config .. "screenshot-menu.sh")

bind(mainMod .. " + Q", hl.dsp.window.close())
bind(mainMod .. " + SHIFT + Q", hl.dsp.exit())
bind(mainMod .. " + F", hl.dsp.window.fullscreen())
bind(mainMod .. " + SPACE", hl.dsp.window.float({ action = "toggle" }))
bind(mainMod .. " + P", hl.dsp.window.pseudo())
bind(mainMod .. " + O", hl.dsp.layout("togglesplit"))
bind(mainMod .. " + Tab", hl.dsp.window.cycle_next())
bind(mainMod .. " + SHIFT + Tab", hl.dsp.window.cycle_next({ next = false }))

for direction, key in pairs({ left = "Left", down = "Down", up = "Up", right = "Right" }) do
    bind(mainMod .. " + " .. direction, hl.dsp.focus({ direction = direction }))
    bind(mainMod .. " + SHIFT + " .. direction, hl.dsp.window.move({ direction = direction }))
end

for workspace = 1, 9 do
    local key = tostring(workspace)
    bind(mainMod .. " + " .. key, hl.dsp.focus({ workspace = workspace }))
    bind(mainMod .. " + SHIFT + " .. key, hl.dsp.window.move({ workspace = workspace }))
end
bind(mainMod .. " + 0", hl.dsp.focus({ workspace = 10 }))
bind(mainMod .. " + SHIFT + 0", hl.dsp.window.move({ workspace = 10 }))
bind("SUPER + ALT_L", hl.dsp.window.fullscreen())
bind("SUPER + ALT_R", hl.dsp.window.fullscreen())

exec("XF86AudioRaiseVolume", "wpctl set-volume -l 1.5 @DEFAULT_AUDIO_SINK@ 5%+", lockedRepeat)
exec("XF86AudioLowerVolume", "wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-", lockedRepeat)
exec("XF86AudioMute", "wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle", lockedRepeat)
exec("XF86AudioMicMute", "wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle", lockedRepeat)
exec("XF86AudioPlay", "playerctl play-pause", lockedRepeat)
exec("XF86AudioNext", "playerctl next", lockedRepeat)
exec("XF86AudioPrev", "playerctl previous", lockedRepeat)
exec("XF86MonBrightnessUp", "brightnessctl set +5%", lockedRepeat)
exec("XF86MonBrightnessDown", "brightnessctl set 5%-", lockedRepeat)

hl.on("hyprland.start", function()
    hl.exec_cmd(config .. "start-rice.sh")
end)
-- <<< UltimaDesk managed <<<