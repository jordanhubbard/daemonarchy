-- Arcade plugin sandbox runner: lua -E sandbox.lua PLUGIN WIDTH HEIGHT SEED
--
-- Defense in depth only. The host (arcade.py) also runs this process with a
-- cleared environment, resource limits, low priority and a per-frame deadline,
-- and treats everything printed here as untrusted.
--
-- Host -> runner, one line per frame:  T <dt_ms> <held,keys>
-- Runner -> host:  C | P x y c | R x y w h c | S freq ms wave vol, then F (end of frame);
--                  E if the plugin failed (the runner then exits).

local path, W, H = arg[1], tonumber(arg[2]), tonumber(arg[3])
math.randomseed(tonumber(arg[4]) or 1)

local BUDGET = 2000000     -- VM instructions per tick
local MAX_OPS = 4096
local MAX_STRING = 65536
local stdout = io.stdout
stdout:setvbuf("full")

-- Strings share one metatable, so ("x"):rep(n) reaches the real library no
-- matter what the plugin's environment holds. Patch the library itself.
local real_rep = string.rep
string.rep = function(s, n, sep)
  if (#s + #(sep or "")) * n > MAX_STRING then error("string too large", 2) end
  return real_rep(s, n, sep)
end
string.dump = nil

local ops = 0
local function emit(...)
  ops = ops + 1
  if ops > MAX_OPS then error("too many drawing operations", 0) end
  stdout:write(string.format(...), "\n")
end

local function num(v, name)
  if type(v) ~= "number" or v ~= v then error(name .. " must be a number", 3) end
  return math.floor(math.max(-1e6, math.min(1e6, v)))
end

local held = {}
local env = {
  assert = assert, error = error, ipairs = ipairs, next = next, pairs = pairs,
  select = select, tonumber = tonumber, tostring = tostring, type = type,
  setmetatable = setmetatable, W = W, H = H,
  math = {}, string = {}, table = {},
  gfx = {
    clear = function() emit("C") end,
    pixel = function(x, y, c) emit("P %d %d %d", num(x, "x"), num(y, "y"), num(c, "color")) end,
    rect = function(x, y, w, h, c)
      emit("R %d %d %d %d %d", num(x, "x"), num(y, "y"), num(w, "w"), num(h, "h"), num(c, "color"))
    end,
  },
  sfx = {
    blip = function(freq, ms, wave, vol)
      if wave ~= "sq" and wave ~= "tri" and wave ~= "noise" then wave = "sq" end
      emit("S %d %d %s %d", num(freq, "freq"), num(ms, "ms"), wave, num((vol or 0.5) * 100, "volume"))
    end,
  },
  input = { held = function(name) return held[name] == true end },
}
for k, v in pairs(math) do env.math[k] = v end
for k, v in pairs(string) do env.string[k] = v end
for k, v in pairs(table) do env.table[k] = v end

local file = assert(io.open(path, "rb"))
local source = file:read(MAX_STRING + 1)
file:close()
if #source > MAX_STRING or source:sub(1, 1) == "\27" then error("plugin rejected", 0) end

local function guarded(fn, ...)
  ops = 0
  debug.sethook(function() error("instruction budget exceeded", 0) end, "", BUDGET)
  local ok, err = pcall(fn, ...)
  debug.sethook()
  if not ok then
    io.stderr:write(tostring(err), "\n")
    stdout:write("E\n")
    stdout:flush()
    os.exit(1)
  end
end

local chunk, err = load(source, "=plugin", "t", env)
if not chunk then io.stderr:write(tostring(err), "\n") stdout:write("E\n") stdout:flush() os.exit(1) end
guarded(chunk)
if type(env.tick) ~= "function" then stdout:write("E\n") stdout:flush() os.exit(1) end
if type(env.init) == "function" then guarded(env.init) stdout:write("") end

for line in io.stdin:lines() do
  local dt, keys = line:match("^T (%d+) ?(.*)$")
  if not dt then break end
  held = {}
  for name in keys:gmatch("[%w]+") do held[name] = true end
  guarded(env.tick, tonumber(dt) / 1000)
  stdout:write("F\n")
  stdout:flush()
end
