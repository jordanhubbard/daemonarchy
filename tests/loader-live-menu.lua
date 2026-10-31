-- Exercise the loader brand file against FreeBSD's real welcome menu and
-- drawer: run as `lua5.4 tests/loader-live-menu.lua [BRAND.lua]` from the
-- repository root. With a BRAND.lua argument it only prints each case's entry
-- count and last row (to compare an older brand file) and asserts nothing.
--
-- tests/fixtures/loader-lua/{menu,drawer}.lua are the unmodified files from
-- daemonarchy-src (see PROVENANCE there). Only the loader's C modules and
-- core/color/config/screen are stubbed, so the entry list, the alias keys and
-- the rows and columns that the real drawer prints are what the loader draws.
-- This is not a native boot; the QEMU/UEFI observation is in the PR.
local fixtures = "tests/fixtures/loader-lua/"
local brand = arg and arg[1] or
    "overlay/usr/local/share/daemonarchy-installer/brand-daemonarchy.lua"
local report = arg and arg[1] ~= nil

-- The fixture digests are the contract with daemonarchy-src.
local function slurp(path)
	local f = assert(io.open(path, "rb"))
	local data = f:read("a")
	f:close()
	return data
end
for line in slurp(fixtures .. "SHA256SUMS"):gmatch("[^\n]+") do
	local sum, name = line:match("^(%x+)%s+(%S+)$")
	local p = assert(io.popen("sha256sum " .. fixtures .. name))
	local got = p:read("a"):match("^(%x+)")
	p:close()
	assert(got == sum, name .. " differs from SHA256SUMS")
end

-- Layout constants of the real drawer (stand/lua/drawer.lua): menu_position
-- {5, 10}, frame_size {w = 39, h = 14}, logo "none" shifts x by 17. Entries
-- run from row 11; the frame's bottom border is row 23; row 24 is the
-- autoboot countdown. So the last usable entry row is 22.
local MENU_X, FIRST_ROW, LAST_ROW = 5 + 17, 11, 22
local FRAME_RIGHT = 2 + 17 + 39

local function scenario(opts)
	local env = {
		console = "efi",
		loader_brand = "daemonarchy",
		loader_logo = "none",
		daemonarchy_live_media = opts.media and "YES" or nil,
		daemonarchy_debug_menu = opts.debug and "YES" or nil,
		boottrace_stick = opts.stick and "YES" or nil,
	}
	local booted, single = false, nil
	local cursor_x, cursor_y = 1, 1
	local cells = {} -- row -> {col -> char}
	function printc(text)
		cells[cursor_y] = cells[cursor_y] or {}
		for ch in tostring(text):gmatch(".") do
			cells[cursor_y][cursor_x] = ch
			cursor_x = cursor_x + 1
		end
	end
	gfx = nil
	loader = {
		getenv = function(name) return env[name] end,
		setenv = function(name, value) env[name] = value end,
		has_command = function() return opts.boottrace ~= false end,
		perform = function() return 0 end,
		time = function() return 0 end,
		delay = function() end,
	}
	package.loaded.core = {
		MENU_ENTRY = "entry", MENU_CAROUSEL_ENTRY = "carousel",
		MENU_SUBMENU = "submenu", MENU_RETURN = "return",
		MENU_SEPARATOR = "separator",
		KEY_BACKSPACE = 8, KEY_DELETE = 127, KEY_ENTER = 13,
		KEYSTR_ESCAPE = "\027",
		isSingleUserBoot = function() return false end,
		setSingleUser = function(value) single = value end,
		boot = function() booted = true end,
		hasACPI = function() return true end,
		isRewinded = function() return false end,
		isZFSBoot = function() return opts.zfs == true end,
		isCheckpointed = function() return false end,
		isUEFIBoot = function() return opts.uefi ~= false end,
		isSerialConsole = function() return true end, -- ASCII frame
		hasUnicode = function() return false end,
		isFramebufferConsole = function() return false end,
		loaderTooOld = function() return false end,
		bootenvList = function() return opts.zfs and { "default", "rollback" } or {} end,
		bootenvDefault = function() return "default" end,
		kernelList = function() return { "kernel", "kernel.secure" } end,
		getConsoleName = function() return "Video" end,
	}
	package.loaded.color = {
		highlight = function(text) return text end,
		isEnabled = function() return false end,
		escapefg = function() return "" end,
		resetfg = function() return "" end,
		GREEN = 2, RED = 1, CYAN = 6,
	}
	package.loaded.config = {
		getCarouselIndex = function() return 1 end,
		setCarouselIndex = function() end,
		selectKernel = function() end,
	}
	package.loaded.cli = {}
	package.loaded.screen = {
		clear = function() end,
		defcursor = function() end,
		setcursor = function(x, y) cursor_x, cursor_y = x, y end,
	}
	package.loaded.boottrace = {
		available = function() return opts.boottrace ~= false and opts.uefi ~= false end,
		label = function() return "with boot trace" end,
		boot = function() end,
		cycle = function() end,
	}
	-- The loader's try_include: gfx-daemonarchy does not exist; the brand file
	-- is loaded by the drawer the first time it draws the brand.
	function try_include(name)
		if name == "brand-daemonarchy" then
			return dofile(brand)
		end
		return nil
	end
	package.loaded.drawer, package.loaded.menu = nil, nil
	package.loaded.drawer = dofile(fixtures .. "drawer.lua")
	local menu = dofile(fixtures .. "menu.lua")
	package.loaded.menu = menu
	local alias_table = package.loaded.drawer.drawscreen(menu.welcome)
	return {
		env = env, menu = menu, cells = cells, alias_table = alias_table,
		state = function() return booted, single end,
	}
end

-- The text printed in a row inside the frame, and whether anything ran into
-- or past the frame's right border (an ASCII frame draws "|" there).
local function rowtext(s, row)
	local cells = s.cells[row] or {}
	local line = {}
	for col = MENU_X, FRAME_RIGHT - 1 do
		line[#line + 1] = cells[col] or " "
	end
	local overflow = cells[FRAME_RIGHT] ~= nil and cells[FRAME_RIGHT] ~= "|"
	for col in pairs(cells) do
		if col > FRAME_RIGHT then overflow = true end
	end
	return (table.concat(line):gsub("%s+$", "")), overflow
end

-- The entries the drawer printed, with their rows.
local function drawn(s)
	local items, last_row, line_no = {}, 0, 0
	for _, e in ipairs(s.menu.welcome.entries()) do
		if e.visible == nil or e.visible() then
			line_no = line_no + 1
			local row = FIRST_ROW - 1 + line_no
			items[#items + 1] = { entry = e, row = row, text = rowtext(s, row) }
			-- A trailing blank separator draws nothing.
			if e.entry_type ~= "separator" or e.name ~= nil then
				last_row = row
			end
		end
	end
	return items, last_row
end

local function check(label, opts, expect)
	local s = scenario(opts)
	local items, last_row = drawn(s)
	local numbered, texts, owner = 0, {}, {}
	for _, item in ipairs(items) do
		local e = item.entry
		texts[#texts + 1] = item.text
		if e.entry_type ~= "separator" then
			numbered = numbered + 1
			local keys = { tostring(numbered) }
			for _, a in ipairs(e.alias or {}) do keys[#keys + 1] = a end
			for _, key in ipairs(keys) do
				assert(owner[key] == nil or owner[key] == e,
				    label .. ": key '" .. key .. "' belongs to two entries: " ..
				    tostring(owner[key] and owner[key].name) .. " / " .. tostring(e.name))
				owner[key] = e
			end
			if not report then
				assert(not item.overflow,
				    label .. ": entry runs over the frame: " .. item.text)
			end
		end
	end
	for key, e in pairs(s.alias_table) do
		assert(owner[key] == e, label .. ": drawer alias '" .. key .. "' mismatch")
	end
	if report then
		print(string.format("%-30s entries=%2d last row=%2d", label, numbered, last_row))
		return s, items, owner
	end
	assert(last_row <= LAST_ROW, string.format(
	    "%s: menu ends on row %d, the frame holds rows up to %d (row 24 is the countdown)",
	    label, last_row, LAST_ROW))
	assert(numbered == expect.count, string.format(
	    "%s: %d numbered entries, expected %d", label, numbered, expect.count))
	for _, needle in ipairs(expect.present or {}) do
		local found = false
		for _, t in ipairs(texts) do
			if t:find(needle, 1, true) then found = true end
		end
		assert(found, label .. ": missing entry " .. needle)
	end
	for _, needle in ipairs(expect.absent or {}) do
		for _, t in ipairs(texts) do
			assert(not t:find(needle, 1, true), label .. ": unexpected entry " .. t)
		end
	end
	assert(s.env.loader_menu_title:find("Daemonarchy", 1, true), label .. ": menu title")
	return s, items, owner
end

-- Installer media (UEFI, boot trace available, not ZFS).
local s, items, owner = check("installer media", { media = true }, {
	count = 8,
	present = { "Boot Multi user", "Try Daemonarchy (live desktop)", "Boot Single user",
	    "Boot Options", "Reboot" },
	absent = { "Boot trace", "Network debugging" },
})
if not report then
	assert(items[1].text:find("Boot Multi user", 1, true), "the default entry must stay first")
	assert(items[2].text:find("Try Daemonarchy", 1, true), "live entry follows the default")
	assert(owner.t == owner["2"] and owner.T == owner.t, "T selects the live entry")
	assert(owner.i == nil and owner.n == nil, "i and n are free while debug entries are hidden")
	assert(s.env.daemonarchy_live == nil, "drawing the menu must not select the live desktop")
	owner.t.func()
	local booted, single = s.state()
	assert(s.env.daemonarchy_live == "YES" and booted and single == false)
end

-- Installed system with boot environments (ZFS): Boot Environments visible.
check("installed, boot environments", { zfs = true }, {
	count = 8,
	present = { "Boot Environments", "Boot Options" },
	absent = { "Try Daemonarchy", "Boot trace", "Network debugging" },
})
check("installed, no ZFS", {}, {
	count = 7, present = { "Boot Options" }, absent = { "Try Daemonarchy" },
})

-- Installer media with the developer entries on.
local d = check("installer media, debug", { media = true, debug = true }, {
	count = 10,
	present = { "Boot trace", "Network debugging", "Try Daemonarchy (live desktop)",
	    "Boot Options" },
})
check("installed with BEs, debug", { zfs = true, debug = true }, {
	count = 10, present = { "Boot trace", "Network debugging", "Boot Environments" },
})
-- The hardware trace image sets boottrace_stick=YES (its Hardware trace
-- entry, key w, shows too).
check("trace stick", { stick = true }, {
	count = 10, present = { "Boot trace", "Hardware trace", "Boot Options" },
})
-- Non-UEFI boot: the debug entries' own visible() hides them either way.
check("BIOS installer media", { media = true, uefi = false, boottrace = false }, {
	count = 8, absent = { "Boot trace", "Network debugging" },
})

-- Loading the brand file again (the drawer may include it on redraw) must not
-- wrap the menu twice.
local before = #d.menu.welcome.entries()
dofile(brand)
assert(#d.menu.welcome.entries() == before, "the brand file wrapped the menu twice")

if not report then
	print("PASS: real menu.lua + drawer.lua with the brand file: unique keys, entries inside the frame (last row <= 22), live entry on the installer media only, debug entries only on request")
end
