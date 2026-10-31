-- Fish tank (toy). Space drops food; the fish chase it. Original art.
local fish, bubbles, food = {}, {}, {}
local clock, fed = 0, false

function init()
  for i = 1, 5 do
    fish[i] = {
      x = math.random(8, W - 8), y = math.random(6, H - 12), dir = i % 2 == 0 and 1 or -1,
      speed = 5 + math.random() * 5, color = ({3, 4, 5, 9, 13})[i], phase = math.random() * 6,
    }
  end
end

local function draw_fish(f)
  local x, y = math.floor(f.x), math.floor(f.y + math.sin(clock * 3 + f.phase))
  gfx.rect(x, y, 6, 3, f.color)
  gfx.rect(x - f.dir * 2, y, 2, 1, f.color)
  gfx.rect(x - f.dir * 3, y - 1, 1, 3, f.color)
  gfx.pixel(x + (f.dir > 0 and 4 or 1), y, 15)
end

function tick(dt)
  clock = clock + dt
  if input.held("space") and not fed then
    food[#food + 1] = { x = math.random(6, W - 6), y = 0 }
    sfx.blip(660, 40, "tri", 0.3)
  end
  fed = input.held("space")
  if math.random() < dt * 3 then bubbles[#bubbles + 1] = { x = math.random(2, W - 2), y = H - 5 } end

  for i = #food, 1, -1 do
    local p = food[i]
    p.y = p.y + dt * 6
    if p.y >= H - 4 then table.remove(food, i) end
  end
  for i = #bubbles, 1, -1 do
    local b = bubbles[i]
    b.y = b.y - dt * 7
    if b.y < 0 then table.remove(bubbles, i) end
  end
  for _, f in ipairs(fish) do
    local target = food[1]
    if target then
      f.dir = target.x > f.x and 1 or -1
      f.y = f.y + (target.y > f.y and 1 or -1) * dt * 6
      if math.abs(target.x - f.x) < 3 and math.abs(target.y - f.y) < 3 then
        table.remove(food, 1)
        sfx.blip(880, 30, "sq", 0.2)
      end
    end
    f.x = f.x + f.dir * f.speed * dt
    if f.x < 4 then f.dir = 1 elseif f.x > W - 10 then f.dir = -1 end
    f.y = math.max(3, math.min(H - 9, f.y))
  end

  gfx.rect(0, 0, W, H, 1)
  gfx.rect(0, H - 4, W, 4, 2)
  for i = 3, W, 9 do gfx.rect(i, H - 7, 1, 3, 11) end
  for _, b in ipairs(bubbles) do gfx.pixel(math.floor(b.x), math.floor(b.y), 7) end
  for _, p in ipairs(food) do gfx.pixel(math.floor(p.x), math.floor(p.y), 5) end
  for _, f in ipairs(fish) do draw_fish(f) end
end
