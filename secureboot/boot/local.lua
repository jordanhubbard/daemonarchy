-- This signed hook runs after local loader configuration has been parsed.
-- The installer keeps a stock kernel for BIOS and a verified kernel for EFI.
local core = require("core")
local config = require("config")

local enforcing = loader.getenv("daemonarchy_secureboot")
local selected = loader.getenv("daemonarchy_verified_profile") == "YES"
if core.isUEFIBoot() and (enforcing == "1" or enforcing == "unknown" or selected) then
    if not config.processFile("/boot/daemonarchy-secureboot.conf", false) then
        error("Daemonarchy verified boot configuration could not be loaded")
    end
else
    config.disableModule("daemonarchy_runtime")
end
