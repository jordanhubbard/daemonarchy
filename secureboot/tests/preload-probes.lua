-- Disposable-guest probe, never part of the production boot hook.
-- The test root contains a valid stock kernel and a copy of geom_nop.ko at
-- /boot/loader.conf.d/raw-module.conf; neither has a boot-manifest entry.
local core = require("core")
local hook = require("hook")

if core.isUEFIBoot() and loader.getenv("daemonarchy_secureboot") == "1" then
    if loader.perform("load /boot/kernel/kernel") == 0 then
        print("DAEMONARCHY_PRELOAD_GENERIC_UNEXPECTEDLY_LOADED")
        error("Unverified stock kernel was accepted")
    end
    print("DAEMONARCHY_PRELOAD_GENERIC_REJECTED")

    hook.register("kernel.loaded", function()
        if loader.perform('load -t "elf obj" /boot/loader.conf.d/raw-module.conf') == 0 then
            print("DAEMONARCHY_PRELOAD_RAW_UNEXPECTEDLY_LOADED")
            error("Unverified raw module was accepted")
        end
        print("DAEMONARCHY_PRELOAD_RAW_REJECTED")
    end)
end
