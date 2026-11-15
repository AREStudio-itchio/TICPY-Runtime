import re
import zlib
from dataclasses import dataclass, field
from pathlib import Path


CHUNK_NAMES = {
    1: "TILES",
    2: "SPRITES",
    4: "MAP",
    5: "CODE",
    9: "SFX",
    10: "WAVEFORMS",
    11: "MUSIC",
    12: "PALETTE",
    14: "FLAGS",
    15: "PATTERNS",
    19: "COMPRESSED_CODE",
}


@dataclass
class Cartridge:
    code: str = ""
    chunks: dict = field(default_factory=dict)
    banks: dict = field(default_factory=dict)
    source: str = ""
    format: str = "python"


class CartridgeError(Exception):
    pass


class CartridgeParser:

    @staticmethod
    def load(filename):
        path = Path(filename)

        if not path.exists():
            raise CartridgeError(f"Cartucho inexistente: {path}")

        data = path.read_bytes()

        if path.suffix.lower() == ".tic":
            return CartridgeParser.parse_binary(data)

        if path.suffix.lower() == ".py":
            return CartridgeParser.parse_python(
                data.decode("utf-8-sig")
            )

        raise CartridgeError("Formato no soportado")

    @staticmethod
    def parse_python(source):
        cart = Cartridge(
            code=source,
            source="python",
            format="python"
        )

        current = None
        bank = 0

        for line in source.splitlines():

            stripped = line.strip()

            match = re.match(
                r"#\s*<(TILES|SPRITES|MAP|SFX|MUSIC|FLAGS|PALETTE|PATTERNS)(\d*)>",
                stripped
            )

            if match:
                current = match.group(1)
                bank = int(match.group(2) or 0)

                key = (current, bank)
                cart.chunks.setdefault(key, {})
                continue

            if stripped.startswith("# </"):
                current = None
                continue

            if current and stripped.startswith("# "):

                payload = stripped[2:].split(":", 1)

                if len(payload) != 2:
                    continue

                try:
                    index = int(payload[0].strip())
                    hex_str = payload[1].strip().replace(" ", "")

                    if current in ("TILES", "SPRITES"):
                        hex_str = hex_str.ljust(64, "0")
                        raw = []
                        for i in range(0, 64, 2):
                            raw.append(int(hex_str[i + 1], 16))
                            raw.append(int(hex_str[i], 16))
                    else:
                        raw = bytes.fromhex(hex_str)


                    cart.chunks[(current, bank)][index] = raw

                except ValueError:
                    continue



        return cart

    @staticmethod
    def parse_binary(data):

        cart = Cartridge(format="tic", source="binary")

        pos = 0

        while pos + 4 <= len(data):

            type_bank = data[pos]
            size = int.from_bytes(
                data[pos + 1:pos + 3], "little"
            )

            chunk_type = type_bank & 0x1F
            bank = type_bank >> 5

            pos += 4

            if pos + size > len(data):
                raise CartridgeError(
                    "Bloque TIC-80 truncado"
                )

            payload = data[pos:pos + size]
            pos += size

            name = CHUNK_NAMES.get(chunk_type)

            if name is None:
                continue

            if name == "COMPRESSED_CODE":
                try:
                    payload = zlib.decompress(payload)
                except zlib.error as exc:
                    raise CartridgeError(
                        "No se pudo descomprimir el código"
                    ) from exc

                name = "CODE"

            if name == "CODE":
                try:
                    cart.code = payload.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise CartridgeError(
                        "El código del cartucho no es UTF-8"
                    ) from exc
            else:
                chunk_dict = cart.chunks.setdefault((name, bank), {})
                if name in ("TILES", "SPRITES"):
                    for i in range(0, len(payload), 32):
                        chunk_dict[i // 32] = payload[i:i + 32]
                elif name == "MAP":
                    for row in range(136):
                        start = row * 240
                        if start < len(payload):
                            chunk_dict[row] = payload[start:start + 240]
                else:
                    chunk_dict[0] = payload

        if not cart.code:
            raise CartridgeError(
                "El cartucho no contiene código ejecutable"
            )

        cart.format = "tic"

        return cart
