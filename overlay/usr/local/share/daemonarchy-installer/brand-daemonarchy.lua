--
-- Daemonarchy brand for the FreeBSD loader menu (loader_brand="daemonarchy").
--

local drawer = require("drawer")

drawer.addBrand("daemonarchy", {
	graphic = {
		" ___                                      _",
		"|   \\ __ _ ___ _ __  ___ _ _  __ _ _ _ __| |_ _  _",
		"| |) / _` / -_) '  \\/ _ \\ ' \\/ _` | '_/ _| ' \\ || |",
		"|___/\\__,_\\___|_|_|_\\___/_||_\\__,_|_| \\__|_||_\\_, |",
		"                                              |__/",
	},
	requires_color = false,
})

-- The installer media alone sets daemonarchy_live_media in its loader.conf.
-- Installed systems copy this brand file but never offer the live desktop.
-- The drawer loads this file before the first menu is drawn, so the entry is
-- in place before the welcome menu's entries are evaluated. Return/Enter still
-- boots the default text installer; only this entry sets daemonarchy_live.
if loader.getenv("daemonarchy_live_media") == "YES" then
	local core = require("core")
	local color = require("color")
	local menu = require("menu")
	if menu.welcome and not menu.welcome.daemonarchy_live then
		local entry = {
			entry_type = core.MENU_ENTRY,
			name = color.highlight("T") ..
			    "ry Daemonarchy (live desktop, disk untouched)",
			func = function()
				loader.setenv("daemonarchy_live", "YES")
				core.setSingleUser(false)
				core.boot()
			end,
			alias = {"t", "T"},
		}
		local entries = menu.welcome.entries
		menu.welcome.daemonarchy_live = entry
		menu.welcome.entries = function()
			local list = entries
			if type(list) == "function" then
				list = list()
			end
			-- Shift every later entry by one, preserving the menu's own
			-- ordering and any absent (nil) optional entries.
			local result = {}
			for index, item in pairs(list) do
				if type(index) == "number" and index > 1 then
					result[index + 1] = item
				else
					result[index] = item
				end
			end
			result[2] = entry
			return result
		end
	end
end

return true
