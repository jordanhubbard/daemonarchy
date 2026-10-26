-- Daemonarchy live desktop: Hyprland, a terminal and the graphical installer.
-- This is deliberately not Omarchy's full desktop, which is installed later.
local installer = "/usr/local/libexec/daemonarchy-installer/live-installer"

hl.monitor({ output = "", mode = "preferred", position = "auto", scale = "auto" })

hl.config({
  input = {
    kb_layout = "us",
    follow_mouse = 1,
  },
  general = {
    gaps_in = 4,
    gaps_out = 8,
    border_size = 2,
  },
  misc = {
    disable_hyprland_logo = true,
    disable_splash_rendering = true,
  },
})

hl.bind("SUPER + RETURN", hl.dsp.exec_cmd("foot"))
hl.bind("SUPER + I", hl.dsp.exec_cmd(installer))
hl.bind("SUPER + Q", hl.dsp.window.close())
hl.bind("SUPER + W", hl.dsp.window.close())

hl.on("hyprland.start", function()
  hl.exec_cmd(installer)
end)
