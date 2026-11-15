DEFAULT_PALETTE = [
    (0x1A, 0x1C, 0x2C),  # 0
    (0x5D, 0x27, 0x5D),  # 1
    (0xB1, 0x3E, 0x53),  # 2
    (0xEF, 0x7D, 0x57),  # 3
    (0xFF, 0xCD, 0x75),  # 4
    (0xA7, 0xF0, 0x70),  # 5
    (0x38, 0xB7, 0x64),  # 6
    (0x25, 0x71, 0x79),  # 7
    (0x29, 0x36, 0x6F),  # 8
    (0x3B, 0x5D, 0xC9),  # 9
    (0x41, 0xA6, 0xF6),  # A
    (0x73, 0xEF, 0xF7),  # B
    (0xF4, 0xF4, 0xF4),  # C
    (0x94, 0xB0, 0xC2),  # D
    (0x56, 0x6C, 0x86),  # E
    (0x33, 0x3C, 0x57),  # F
]


class TICMemory:

    def __init__(self):
        self.reset()

    def reset(self):
        self.ram = bytearray(98304)  # 96 KB RAM completa de TIC-80
        self.palette = list(DEFAULT_PALETTE)

        self.tiles = {}
        self.sprites = {}
        self.map_data = bytearray(240 * 136)

        self.cart_banks = {}
        self.vbank_id = 0

        self.flags_data = bytearray(512)
        self.sfx_data = {}
        self.music_data = {}
        self.waveforms = {}
        self.patterns = {}

        self.persistent = bytearray(256)
        self._sync_palette_to_ram()

    def _sync_palette_to_ram(self):
        for i, rgb in enumerate(self.palette):
            base = 0x03FC0 + i * 3
            self.ram[base:base + 3] = bytes(rgb)

    def _sync_tile_to_ram(self, tile_id, pixels):
        if len(pixels) < 64:
            return
        base = 0x04000 + tile_id * 32
        for i in range(0, 64, 2):
            low = pixels[i] & 0x0F
            high = pixels[i + 1] & 0x0F
            self.ram[base + (i // 2)] = low | (high << 4)

    def _sync_ram_to_tile(self, address):
        tile_id = (address - 0x04000) // 32
        base = 0x04000 + tile_id * 32
        pixels = []
        for b in self.ram[base:base + 32]:
            pixels.append(b & 0x0F)
            pixels.append((b >> 4) & 0x0F)
        if 0 <= tile_id < 256:
            self.tiles[tile_id] = pixels
        elif 256 <= tile_id < 512:
            self.sprites[tile_id - 256] = pixels

    def load_cartridge(self, cart):

        self.reset()

        for (name, bank), entries in cart.chunks.items():

            if name == "PALETTE":
                for _, raw in entries.items():
                    for i in range(min(16, len(raw) // 3)):
                        self.palette[i] = tuple(
                            raw[i * 3:i * 3 + 3]
                        )
                self._sync_palette_to_ram()

            elif name == "MAP":
                for row, raw in entries.items():
                    if 0 <= row < 136:
                        start = row * 240
                        count = min(240, len(raw))
                        self.map_data[start:start + count] = raw[:count]
                        self.ram[0x08000 + start:0x08000 + start + count] = raw[:count]

            elif name in ("TILES", "SPRITES"):
                target = self.tiles if name == "TILES" else self.sprites
                offset_base = 0 if name == "TILES" else 256

                for index, raw in entries.items():
                    tile_idx = bank * 256 + index
                    target[tile_idx] = raw
                    if bank == 0 and 0 <= index < 256:
                        self._sync_tile_to_ram(offset_base + index, raw)

            elif name == "FLAGS":
                for index, raw in entries.items():
                    start = bank * 256 + index * len(raw)
                    end = min(start + len(raw), len(self.flags_data))

                    if start < end:
                        self.flags_data[start:end] = raw[:end - start]
                        if start + len(raw) <= 512:
                            self.ram[0x14404 + start:0x14404 + end] = raw[:end - start]

            elif name == "SFX":
                self.sfx_data.update(entries)

            elif name == "MUSIC":
                self.music_data.update(entries)

            elif name == "WAVEFORMS":
                self.waveforms.update(entries)

            elif name == "PATTERNS":
                self.patterns.update(entries)

        import copy
        self.cart_banks = copy.deepcopy(cart.chunks)

    def peek(self, address):
        address = int(address)
        if not 0 <= address < len(self.ram):
            return 0
        return self.ram[address]

    def poke(self, address, value):
        address = int(address)
        val = int(value) & 255
        if 0 <= address < len(self.ram):
            self.ram[address] = val

            # Paleta (0x03FC0 - 0x03FEF)
            if 0x03FC0 <= address < 0x03FF0:
                offset = address - 0x03FC0
                color_idx = offset // 3
                channel = offset % 3
                rgb = list(self.palette[color_idx])
                rgb[channel] = val
                self.palette[color_idx] = tuple(rgb)

            # Tiles y Sprites (0x04000 - 0x07FFF)
            elif 0x04000 <= address < 0x08000:
                self._sync_ram_to_tile(address)

            # Mapa (0x08000 - 0x0FF7F)
            elif 0x08000 <= address < 0x0FF80:
                self.map_data[address - 0x08000] = val

            # Flags (0x14404 - 0x14603)
            elif 0x14404 <= address < 0x14604:
                self.flags_data[address - 0x14404] = val

    def peek4(self, address):
        address = int(address)
        value = self.peek(address // 2)
        if address & 1:
            return (value >> 4) & 15
        return value & 15

    def poke4(self, address, value):
        address = int(address)
        byte_address = address // 2
        old = self.peek(byte_address)
        value = int(value) & 15
        if address & 1:
            self.poke(byte_address, (old & 15) | (value << 4))
        else:
            self.poke(byte_address, (old & 240) | value)

    def peek2(self, address):
        address = int(address)
        value = self.peek(address // 4)
        shift = (address & 3) * 2
        return (value >> shift) & 3

    def poke2(self, address, value):
        address = int(address)
        byte_address = address // 4
        old = self.peek(byte_address)
        shift = (address & 3) * 2
        mask = ~(3 << shift) & 255
        self.poke(byte_address, (old & mask) | ((int(value) & 3) << shift))

    def peek1(self, address):
        address = int(address)
        value = self.peek(address // 8)
        shift = address & 7
        return (value >> shift) & 1

    def poke1(self, address, value):
        address = int(address)
        byte_address = address // 8
        old = self.peek(byte_address)
        shift = address & 7
        mask = ~(1 << shift) & 255
        self.poke(byte_address, (old & mask) | ((int(value) & 1) << shift))

    def memcpy(self, dest, source, length):
        dest, source, length = int(dest), int(source), int(length)
        data = bytes(
            self.peek(source + i)
            for i in range(max(0, length))
        )
        for i, value in enumerate(data):
            self.poke(dest + i, value)

    def memset(self, dest, value, length):
        dest, length = int(dest), int(length)
        for i in range(max(0, length)):
            self.poke(dest + i, value)

    def mget(self, x, y):
        x, y = int(x), int(y)
        if 0 <= x < 240 and 0 <= y < 136:
            return self.map_data[y * 240 + x]
        return 0

    def mset(self, x, y, tile):
        x, y = int(x), int(y)
        if 0 <= x < 240 and 0 <= y < 136:
            idx = y * 240 + x
            val = int(tile) & 255
            self.map_data[idx] = val
            self.ram[0x08000 + idx] = val

    def fget(self, tile, flag):
        tile, flag = int(tile), int(flag)
        if not 0 <= tile < len(self.flags_data):
            return False
        if not 0 <= flag < 8:
            return False
        return bool(self.flags_data[tile] & (1 << flag))

    def fset(self, tile, flag, value):
        tile, flag = int(tile), int(flag)
        if not 0 <= tile < len(self.flags_data):
            return
        if not 0 <= flag < 8:
            return
        if value:
            self.flags_data[tile] |= 1 << flag
        else:
            self.flags_data[tile] &= ~(1 << flag)
        self.ram[0x14404 + tile] = self.flags_data[tile]

    def pmem(self, index, value=None):
        index = int(index) % 256
        old = self.persistent[index]
        if value is not None:
            self.persistent[index] = int(value) & 255
        return old
    def sync(self, mask=0, bank=0, to_cart=False):
        mask = int(mask)
        bank = int(bank) & 7
        to_cart = bool(to_cart)

        if mask == 0:
            mask = 0xFF

        sections = [
            (1, "TILES", self.tiles, 0),
            (2, "SPRITES", self.sprites, 256),
            (4, "MAP", None, 0),
            (8, "SFX", self.sfx_data, 0),
            (16, "MUSIC", self.music_data, 0),
            (32, "PALETTE", None, 0),
            (64, "FLAGS", None, 0),
            (128, "WAVEFORMS", self.waveforms, 0),
        ]

        for bit, name, target_dict, base_offset in sections:
            if not (mask & bit):
                continue

            key = (name, bank)
            if to_cart:
                if name in ("TILES", "SPRITES"):
                    self.cart_banks[key] = {
                        i: list(target_dict[i]) for i in range(256) if i in target_dict
                    }
                elif name == "MAP":
                    self.cart_banks[key] = {
                        r: bytes(self.map_data[r * 240:(r + 1) * 240]) for r in range(136)
                    }
                elif name == "PALETTE":
                    raw_pal = bytearray()
                    for r, g, b in self.palette:
                        raw_pal.extend([r, g, b])
                    self.cart_banks[key] = {0: bytes(raw_pal)}
                elif name == "FLAGS":
                    self.cart_banks[key] = {0: bytes(self.flags_data[:256])}
                elif target_dict is not None:
                    self.cart_banks[key] = dict(target_dict)
            else:
                entries = self.cart_banks.get(key, {})
                if name in ("TILES", "SPRITES"):
                    target_dict.clear()
                    for idx, raw in entries.items():
                        target_dict[idx] = list(raw)
                        if 0 <= idx < 256:
                            self._sync_tile_to_ram(base_offset + idx, raw)
                elif name == "MAP":
                    self.map_data[:] = b"\x00" * (240 * 136)
                    self.ram[0x08000:0x0FF80] = b"\x00" * (240 * 136)
                    for row, raw in entries.items():
                        if 0 <= row < 136:
                            start = row * 240
                            count = min(240, len(raw))
                            self.map_data[start:start + count] = raw[:count]
                            self.ram[0x08000 + start:0x08000 + start + count] = raw[:count]
                elif name == "PALETTE":
                    for _, raw in entries.items():
                        for i in range(min(16, len(raw) // 3)):
                            self.palette[i] = tuple(raw[i * 3:i * 3 + 3])
                    self._sync_palette_to_ram()
                elif name == "FLAGS":
                    self.flags_data[:256] = b"\x00" * 256
                    for idx, raw in entries.items():
                        start = idx * len(raw)
                        end = min(start + len(raw), 256)
                        if start < end:
                            self.flags_data[start:end] = raw[:end - start]
                            self.ram[0x14404 + start:0x14404 + end] = raw[:end - start]
                elif target_dict is not None:
                    target_dict.clear()
                    target_dict.update(entries)

