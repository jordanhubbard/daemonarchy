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

return true
