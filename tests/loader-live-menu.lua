-- Exercise the loader brand file's live desktop entry against stub loader
-- modules: run as `lua5.4 tests/loader-live-menu.lua` from the repository.
-- The real FreeBSD menu is native evidence; this checks the entry's placement,
-- the default boot path, the kenv flag and installed-system invisibility.
local brand = "overlay/usr/local/share/daemonarchy-installer/brand-daemonarchy.lua"

local function scenario(media)
	local env = { daemonarchy_live_media = media }
	local booted, single = false, nil
	-- require() reads the interpreter's own loaded-module table.
	loader = {
		getenv = function(name) return env[name] end,
		setenv = function(name, value) env[name] = value end,
	}
	package.loaded.drawer = { addBrand = function() end }
	package.loaded.color = { highlight = function(text) return text end }
	package.loaded.core = {
		MENU_ENTRY = "entry",
		setSingleUser = function(value) single = value end,
		boot = function() booted = true end,
	}
	local multi_user = { name = "Boot Multi user" }
	local hidden = nil -- an optional entry absent on this platform
	local menu = { welcome = {} }
	menu.welcome.entries = function()
		return { multi_user, { name = "Boot Single user" }, hidden, { name = "Reboot" } }
	end
	package.loaded.menu = menu
	assert(dofile(brand) == true)
	-- The drawer may include the brand again on redraw; never add twice.
	assert(dofile(brand) == true)
	return menu.welcome.entries(), env, function() return booted, single end
end

-- Installer media: the live entry follows the default text installer boot.
local entries, env, state = scenario("YES")
assert(entries[1].name == "Boot Multi user", "the default entry must stay first")
local live = entries[2]
assert(live.name == "Try Daemonarchy (live desktop, disk untouched)", live.name)
assert(live.alias[1] == "t" and live.alias[2] == "T")
assert(entries[3].name == "Boot Single user")
assert(entries[4] == nil and entries[5].name == "Reboot", "optional entries keep their places")
local count = 0
for _, item in pairs(entries) do
	if item == live then count = count + 1 end
end
assert(count == 1, "the live entry was added more than once")
assert(env.daemonarchy_live == nil, "drawing the menu must not select the live desktop")
live.func()
local booted, single = state()
assert(env.daemonarchy_live == "YES" and booted and single == false)

-- Installed systems copy the brand file but never set daemonarchy_live_media.
entries = scenario(nil)
for _, item in pairs(entries) do
	assert(not tostring(item.name):match("Try Daemonarchy"), "live entry on an installed system")
end
print("PASS: live desktop loader entry follows the default boot, sets only daemonarchy_live, absent when installed")
