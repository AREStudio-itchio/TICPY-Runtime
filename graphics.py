import math
import pyglet
from font import FONT_6X8

WIDTH, HEIGHT = 240, 136


class TICGraphics:

    def __init__(self, memory):
        self.mem = memory
        self.framebuffer = bytearray(WIDTH * HEIGHT * 3)
        pyglet.image.Texture.default_min_filter = pyglet.gl.GL_NEAREST
        pyglet.image.Texture.default_mag_filter = pyglet.gl.GL_NEAREST
        self.image = pyglet.image.ImageData(
            WIDTH, HEIGHT, "RGB", bytes(self.framebuffer), pitch=-WIDTH * 3
        )
        self.texture = self.image.get_texture()
        self.texture.mag_filter = pyglet.gl.GL_NEAREST
        self.texture.min_filter = pyglet.gl.GL_NEAREST
        self.clip_rect = (0, 0, WIDTH, HEIGHT)

    def update_texture(self, scn_callback=None):
        from pyglet import gl
        import ctypes

        ram = self.mem.ram
        fb = self.framebuffer
        has_scn = callable(scn_callback)
        active_vb = getattr(self, "_active_vbank", 0)

        off0 = 0x00000 if active_vb == 0 else 0x18000
        off1 = 0x18000 if active_vb == 0 else 0x00000
        has_vb1 = any(ram[off1:off1 + 16320])

        # Reutilizar tabla LUT si la paleta no cambió
        pal_key = tuple(self.mem.palette)
        if getattr(self, "_last_pal_key", None) != pal_key:
            self._last_pal_key = pal_key
            self._cached_lut = [
                bytes(pal_key[b & 0x0F] + pal_key[(b >> 4) & 0x0F]) for b in range(256)
            ]

        lut = self._cached_lut

        for y in range(HEIGHT):
            if has_scn:
                scn_callback(y)
                pal_now = tuple(self.mem.palette)
                if pal_now != self._last_pal_key:
                    self._last_pal_key = pal_now
                    self._cached_lut = [
                        bytes(pal_now[b & 0x0F] + pal_now[(b >> 4) & 0x0F]) for b in range(256)
                    ]
                    lut = self._cached_lut

            dst_y = (HEIGHT - 1) - y
            fb_row = dst_y * 720
            row0 = off0 + y * 120

            if not has_vb1:
                fb[fb_row:fb_row + 720] = b"".join(
                    lut[ram[row0 + bx]] for bx in range(120)
                )
            else:
                row1 = off1 + y * 120
                fb[fb_row:fb_row + 720] = b"".join(
                    lut[((ram[row1 + bx] & 0x0F) or (ram[row0 + bx] & 0x0F)) |
                        ((((ram[row1 + bx] >> 4) & 0x0F) or ((ram[row0 + bx] >> 4) & 0x0F)) << 4)]
                    for bx in range(120)
                )

        if not hasattr(self, "_c_buf"):
            self._c_buf = (ctypes.c_ubyte * len(fb)).from_buffer(fb)

        gl.glBindTexture(self.texture.target, self.texture.id)
        gl.glTexSubImage2D(
            self.texture.target, 0, 0, 0, WIDTH, HEIGHT,
            gl.GL_RGB, gl.GL_UNSIGNED_BYTE, self._c_buf
        )

    def clip(self, x=0, y=0, w=WIDTH, h=HEIGHT):
        x, y, w, h = map(int, (x, y, w, h))
        self.clip_rect = (
            max(0, x), max(0, y),
            min(WIDTH, x + max(0, w)), min(HEIGHT, y + max(0, h))
        )

    def cls(self, color=0):
        c = int(color) & 15
        self.mem.ram[0:16320] = bytes([c | (c << 4)]) * 16320

    def pix(self, x, y, color=None):
        x, y = int(x), int(y)
        if color is None:
            if not (0 <= x < WIDTH and 0 <= y < HEIGHT):
                return 0
            val = self.mem.ram[y * 120 + (x >> 1)]
            return ((val >> 4) & 15) if (x & 1) else (val & 15)
        cx0, cy0, cx1, cy1 = self.clip_rect
        if not (cx0 <= x < cx1 and cy0 <= y < cy1):
            return
        c = int(color) & 15
        idx = y * 120 + (x >> 1)
        old = self.mem.ram[idx]
        self.mem.ram[idx] = ((old & 0x0F) | (c << 4)) if (x & 1) else ((old & 0xF0) | c)

    def line(self, x0, y0, x1, y1, color):
        x0, y0, x1, y1 = map(int, (x0, y0, x1, y1))
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx - dy
        while True:
            self.pix(x0, y0, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def rect(self, x, y, w, h, color):
        x, y, w, h = map(int, (x, y, w, h))
        for py in range(max(0, h)):
            for px in range(max(0, w)):
                self.pix(x + px, y + py, color)

    def rectb(self, x, y, w, h, color):
        x, y, w, h = map(int, (x, y, w, h))
        if w > 0 and h > 0:
            self.line(x, y, x + w - 1, y, color)
            self.line(x, y + h - 1, x + w - 1, y + h - 1, color)
            self.line(x, y, x, y + h - 1, color)
            self.line(x + w - 1, y, x + w - 1, y + h - 1, color)

    def circ(self, x, y, radius, color):
        x, y, r = map(int, (x, y, radius))
        for py in range(-r, r + 1):
            ext = int(max(0, r * r - py * py) ** 0.5)
            for px in range(-ext, ext + 1):
                self.pix(x + px, y + py, color)

    def circb(self, x, y, radius, color):
        x, y, r = map(int, (x, y, radius))
        px, py, err = r, 0, 1 - r
        while px >= py:
            for dx, dy in ((px, py), (-px, py), (px, -py), (-px, -py),
                           (py, px), (-py, px), (py, -px), (-py, -px)):
                self.pix(x + dx, y + dy, color)
            py += 1
            if err < 0:
                err += 2 * py + 1
            else:
                px -= 1
                err += 2 * (py - px) + 1

    def ellip(self, x, y, a, b, color):
        x, y, a, b = map(int, (x, y, a, b))
        if a > 0 and b > 0:
            for py in range(-b, b + 1):
                ext = int(a * max(0.0, 1.0 - (py * py) / (b * b)) ** 0.5)
                for px in range(-ext, ext + 1):
                    self.pix(x + px, y + py, color)

    def ellipb(self, x, y, a, b, color):
        x, y, a, b = map(int, (x, y, a, b))
        if a > 0 and b > 0:
            prev = None
            steps = max(32, (a + b) * 4)
            for i in range(steps + 1):
                ang = (2 * math.pi * i) / steps
                pt = (int(round(x + a * math.cos(ang))), int(round(y + b * math.sin(ang))))
                if prev:
                    self.line(prev[0], prev[1], pt[0], pt[1], color)
                prev = pt

    def tri(self, x1, y1, x2, y2, x3, y3, color):
        pts = sorted([(int(x1), int(y1)), (int(x2), int(y2)), (int(x3), int(y3))], key=lambda p: p[1])
        (x1, y1), (x2, y2), (x3, y3) = pts
        def interp(y0, x0, y1, x1):
            return [x0] if y1 == y0 else [x0 + (x1 - x0) * (y - y0) / (y1 - y0) for y in range(y0, y1 + 1)]
        if y1 == y3:
            for x in range(min(x1, x2, x3), max(x1, x2, x3) + 1):
                self.pix(x, y1, color)
            return
        x13 = interp(y1, x1, y3, x3)
        x123 = interp(y1, x1, y2, x2)[:-1] + interp(y2, x2, y3, x3)
        for idx, y in enumerate(range(y1, y3 + 1)):
            xa, xb = int(round(x13[idx])), int(round(x123[idx]))
            for x in range(min(xa, xb), max(xa, xb) + 1):
                self.pix(x, y, color)

    def trib(self, x1, y1, x2, y2, x3, y3, color):
        self.line(x1, y1, x2, y2, color)
        self.line(x2, y2, x3, y3, color)
        self.line(x3, y3, x1, y1, color)

    def vbank(self, bank=None):
        old = getattr(self, "_active_vbank", 0)
        if bank is not None:
            bank = int(bank) & 1
            if bank != old:
                # Intercambiar VRAM y paleta con el banco secundario en RAM (0x18000)
                vram0 = bytes(self.mem.ram[0x00000:0x03FF0])
                vram1 = bytes(self.mem.ram[0x18000:0x1BFF0])
                self.mem.ram[0x00000:0x03FF0] = vram1
                self.mem.ram[0x18000:0x1BFF0] = vram0

                for i in range(16):
                    base = 0x03FC0 + i * 3
                    self.mem.palette[i] = tuple(self.mem.ram[base:base + 3])

                self._active_vbank = bank
        return old

    def ttri(self, x1, y1, x2, y2, x3, y3,
             u1, v1, u2, v2, u3, v3,
             texsrc=0, chromakey=-1, z1=0, z2=0, z3=0):

        verts = [
            (float(x1), float(y1), float(u1), float(v1)),
            (float(x2), float(y2), float(u2), float(v2)),
            (float(x3), float(y3), float(u3), float(v3)),
        ]
        verts.sort(key=lambda p: p[1])
        (x1, y1, u1, v1), (x2, y2, u2, v2), (x3, y3, u3, v3) = verts

        transparent = set(int(c) for c in chromakey) if isinstance(chromakey, (list, tuple, set)) else (
            {int(chromakey)} if int(chromakey) >= 0 else set()
        )

        texsrc = int(texsrc)
        iy1, iy2, iy3 = int(round(y1)), int(round(y2)), int(round(y3))
        if iy1 == iy3:
            return

        cx0, cy0, cx1, cy1 = self.clip_rect
        ram = self.mem.ram
        tiles = self.mem.tiles if texsrc != 2 else self.mem.sprites

        for y in range(max(cy0, iy1), min(cy1, iy3 + 1)):
            t13 = (y - y1) / (y3 - y1)
            xa = x1 + (x3 - x1) * t13
            ua = u1 + (u3 - u1) * t13
            va = v1 + (v3 - v1) * t13

            if y < iy2:
                t12 = (y - y1) / (y2 - y1) if y2 != y1 else 0.0
                xb = x1 + (x2 - x1) * t12
                ub = u1 + (u2 - u1) * t12
                vb = v1 + (v2 - v1) * t12
            else:
                t23 = (y - y2) / (y3 - y2) if y3 != y2 else 0.0
                xb = x2 + (x3 - x2) * t23
                ub = u2 + (u3 - u2) * t23
                vb = v2 + (v3 - v2) * t23

            if xa > xb:
                xa, xb, ua, ub, va, vb = xb, xa, ub, ua, vb, va

            ix_start = max(cx0, int(math.ceil(xa)))
            ix_end = min(cx1 - 1, int(math.floor(xb)))
            span = xb - xa
            if ix_start > ix_end:
                continue

            du = (ub - ua) / span if span > 0 else 0.0
            dv = (vb - va) / span if span > 0 else 0.0
            u = ua + (ix_start - xa) * du
            v = va + (ix_start - xa) * dv
            row_base = y * 120

            for x in range(ix_start, ix_end + 1):
                iu, iv = int(u) & 127, int(v) & 127
                data = tiles.get((iv // 8) * 16 + (iu // 8))
                color = data[(iv & 7) * 8 + (iu & 7)] if data and len(data) >= 64 else 0

                if color not in transparent:
                    idx = row_base + (x >> 1)
                    if x & 1:
                        ram[idx] = (ram[idx] & 0x0F) | (color << 4)
                    else:
                        ram[idx] = (ram[idx] & 0xF0) | color

                u += du
                v += dv

    def _get_tile_data(self, tile_id):
        if 0 <= tile_id < 256:
            return self.mem.tiles.get(tile_id)
        if 256 <= tile_id < 512:
            return self.mem.sprites.get(tile_id - 256)
        return None

    def spr(self, tile, x, y, colorkey=-1, scale=1, flip=0, rotate=0, w=1, h=1):
        tile, x, y = int(tile), int(x), int(y)
        scale, flip, rotate = max(1, int(scale)), int(flip) & 3, int(rotate) & 3
        w, h = max(1, int(w)), max(1, int(h))
        transparent = set(int(c) for c in colorkey) if isinstance(colorkey, (list, tuple, set)) else (
            {int(colorkey)} if int(colorkey) >= 0 else set()
        )
        tw, th = w * 8, h * 8
        ow, oh = (th, tw) if rotate in (1, 3) else (tw, th)
        for sy in range(oh):
            for sx in range(ow):
                if rotate == 1:
                    rx, ry = sy, th - 1 - sx
                elif rotate == 2:
                    rx, ry = tw - 1 - sx, th - 1 - sy
                elif rotate == 3:
                    rx, ry = tw - 1 - sy, sx
                else:
                    rx, ry = sx, sy
                if flip & 1:
                    rx = (tw - 1) - rx
                if flip & 2:
                    ry = (th - 1) - ry
                tile_id = ((tile // 16) + (ry // 8)) * 16 + ((tile % 16) + (rx // 8))
                data = self._get_tile_data(tile_id)
                if data and len(data) >= 64:
                    color = data[(ry & 7) * 8 + (rx & 7)]
                    if color not in transparent:
                        self.rect(x + sx * scale, y + sy * scale, scale, scale, color)

    def map(self, x=0, y=0, w=30, h=17, sx=0, sy=0, colorkey=-1, scale=1, remap=None):
        x, y, w, h, sx, sy = map(int, (x, y, w, h, sx, sy))
        scale = max(1, int(scale))
        for my in range(h):
            for mx in range(w):
                map_x, map_y = sx + mx, sy + my
                tile = self.mem.mget(map_x, map_y)
                flip, rotate = 0, 0
                if callable(remap):
                    res = remap(tile, map_x, map_y)
                    if isinstance(res, tuple):
                        tile = res[0]
                        flip = res[1] if len(res) > 1 else 0
                        rotate = res[2] if len(res) > 2 else 0
                    elif res is not None:
                        tile = res
                if tile:
                    self.spr(tile, x + mx * 8 * scale, y + my * 8 * scale, colorkey, scale, flip, rotate)

    def print_text(self, text, x=0, y=0, color=15, fixed=False, scale=1, small_font=False):
        text, x, y, scale = str(text), int(x), int(y), max(1, int(scale))
        origin_x, max_x = x, x
        for char in text:
            if char == "\n":
                max_x, x = max(max_x, x), origin_x
                y += (6 if small_font else 8) * scale
                continue
            glyph = FONT_6X8.get(char, FONT_6X8["?"])
            char_width = 0
            for row, bits in enumerate(glyph):
                for col in range(6):
                    if bits & (1 << (7 - col)):
                        char_width = max(char_width, col + 1)
                        self.rect(x + col * scale, y + row * scale, scale, scale, color)
            advance = (4 if small_font else 6) if fixed else (3 if char == " " else char_width + 1)
            x += advance * scale
        return max(max_x, x) - origin_x

    def font(self, text, x, y, chromakey=-1, char_width=8, char_height=8, fixed=False, scale=1, alt=False):
        text, x, y = str(text), int(x), int(y)
        cw, ch, scale = max(1, int(char_width)), max(1, int(char_height)), max(1, int(scale))
        base_tile = 256 if alt else 0
        transparent = set(int(c) for c in chromakey) if isinstance(chromakey, (list, tuple, set)) else (
            {int(chromakey)} if int(chromakey) >= 0 else set()
        )
        origin_x, max_x = x, x
        for char in text:
            if char == "\n":
                max_x, x = max(max_x, x), origin_x
                y += ch * scale
                continue
            code = ord(char) if 32 <= ord(char) <= 127 else ord("?")
            tile_id = base_tile + (code - 32)
            advance = cw
            if not fixed:
                real_w = 0
                data = self._get_tile_data(tile_id)
                if data and len(data) >= 64:
                    for py in range(min(8, ch)):
                        for px in range(min(8, cw)):
                            if data[py * 8 + px] not in transparent:
                                real_w = max(real_w, px + 1)
                advance = 3 if char == " " else (real_w + 1 if real_w > 0 else cw)
            self.spr(tile_id, x, y, chromakey, scale, 0, 0, max(1, (cw + 7) // 8), max(1, (ch + 7) // 8))
            x += advance * scale
        return max(max_x, x) - origin_x

    def draw(self):
        self.update_texture()
        self.texture.blit(0, 0, width=WIDTH, height=HEIGHT)
