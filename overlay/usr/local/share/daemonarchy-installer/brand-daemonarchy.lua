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

-- Menu title: drawbox() reads loader_menu_title after this file is loaded, so
-- the brand file can name the menu. An operator's own setting wins.
if loader.getenv("loader_menu_title") == nil then
	loader.setenv("loader_menu_title", "Welcome to Daemonarchy")
end

-- Changes to FreeBSD's welcome menu, made without patching menu.lua:
--
--  * The installer media alone sets daemonarchy_live_media in its loader.conf
--    and gets "Try Daemonarchy" after the default boot entry. Installed
--    systems copy this brand file but never offer the live desktop. Return
--    and Enter still boot the default; only this entry sets daemonarchy_live.
--  * "Boot trace" and "Network debugging" are developer tools (docs/boottrace.md,
--    docs/remote-agent-debug.md). They are listed only when the loader sets
--    daemonarchy_debug_menu=YES or boottrace_stick=YES. Without them the
--    menu fits inside the 14-row frame (rows 10 to 22 of a 25-row console,
--    leaving row 24 for the autoboot countdown): Boot Options and, on a
--    ZFS system with boot environments, Boot Environments stay visible.
--    The keys i and n are free while they are hidden.
--  * With the debug entries shown, the blank separator lines are dropped so
--    the menu still ends by row 22.
-- The drawer loads this file before the first menu is drawn, so the changes
-- are in place before the welcome menu's entries are evaluated.
local core = require("core")
local color = require("color")
local menu = require("menu")

local function debug_menu()
	return loader.getenv("daemonarchy_debug_menu") == "YES" or
	    loader.getenv("boottrace_stick") == "YES"
end

if menu.welcome and not menu.welcome.daemonarchy_wrapped then
	menu.welcome.daemonarchy_wrapped = true
	local live = nil
	if loader.getenv("daemonarchy_live_media") == "YES" then
		-- Short enough for the 39-column frame: "2. " plus the label
		-- must end before column 41. The text installer stays the default;
		-- the disk is untouched until an installation is confirmed.
		live = {
			entry_type = core.MENU_ENTRY,
			name = color.highlight("T") .. "ry Daemonarchy (live desktop)",
			func = function()
				loader.setenv("daemonarchy_live", "YES")
				core.setSingleUser(false)
				core.boot()
			end,
			alias = {"t", "T"},
		}
		menu.welcome.daemonarchy_live = live
	end
	local entries = menu.welcome.entries
	menu.welcome.entries = function()
		local list = entries
		if type(list) == "function" then
			list = list()
		end
		local all = menu.welcome.all_entries or {}
		local show_debug = debug_menu()
		local last = 0
		for index in pairs(list) do
			if type(index) == "number" and index > last then
				last = index
			end
		end
		-- The drawer stops at the first nil, so build a dense list.
		local result = {}
		for index = 1, last do
			local item = list[index]
			if item ~= nil then
				local hide = false
				if not show_debug then
					hide = (item == all.boottrace or item == all.netdebug)
				elseif item.entry_type == core.MENU_SEPARATOR and
				    item.name == nil then
					hide = true
				end
				if not hide then
					result[#result + 1] = item
					if index == 1 and live ~= nil then
						result[#result + 1] = live
					end
				end
			end
		end
		return result
	end
end

return true
