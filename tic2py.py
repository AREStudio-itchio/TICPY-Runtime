import struct
import sys
import zlib


def convert_tic_to_python(input_path, output_path):
    with open(input_path, "rb") as f:
        data = f.read()

    pos = 0
    chunks = []
    code_banks = {}
    comment_prefix = "#"

    chunk_names = {
        1: "TILES",
        2: "SPRITES",
        4: "MAP",
        9: "SFX",
        10: "WAVEFORMS",
        11: "MUSIC",
        12: "PALETTE",
        14: "FLAGS",
        15: "PATTERNS",
    }

    while pos + 4 <= len(data):
        type_bank, size, _ = struct.unpack("<BHB", data[pos : pos + 4])
        chunk_type = type_bank & 0x1F
        bank = type_bank >> 5
        pos += 4

        content = data[pos : pos + size]
        pos += size

        if chunk_type == 5:
            code_banks[bank] = content.decode("utf-8", errors="replace")
        elif chunk_type in (16, 19):
            try:
                code_banks[bank] = zlib.decompress(content).decode("utf-8", errors="replace")
            except zlib.error:
                code_banks[bank] = zlib.decompress(content, -15).decode("utf-8", errors="replace")
        elif chunk_type in chunk_names:
            chunks.append((chunk_names[chunk_type], bank, content))

    full_code = "\n".join(code_banks[b].rstrip() for b in sorted(code_banks))

    row_sizes = {
        "TILES": 32,
        "SPRITES": 32,
        "SFX": 66,
        "WAVEFORMS": 16,
        "MUSIC": 24,
        "FLAGS": 256,
        "PATTERNS": 192,
    }

    with open(output_path, "w", encoding="utf-8") as out:
        if full_code:
            out.write(full_code + "\n\n")

        for name, bank, content in chunks:
            suffix = f"{bank}" if bank > 0 else ""
            out.write(f"{comment_prefix} <{name}{suffix}>\n")

            if name == "PALETTE":
                out.write(f"{comment_prefix} 000:{content.hex()}\n")
            elif name == "MAP":
                for row in range(136):
                    start = row * 240
                    slice_data = content[start : start + 240]
                    if any(slice_data):
                        out.write(f"{comment_prefix} {row:03d}:{slice_data.hex()}\n")
            else:
                row_size = row_sizes.get(name, 66)

                for idx in range(0, len(content), row_size):
                    slice_data = content[idx : idx + row_size]
                    if any(slice_data):
                        num = idx // row_size
                        # Rellenamos con ceros hasta row_size para que TICAudio nunca lo descarte
                        padded = slice_data.ljust(row_size, b"\x00")
                        out.write(f"{comment_prefix} {num:03d}:{padded.hex()}\n")

            out.write(f"{comment_prefix} </{name}{suffix}>\n\n")

    print(f"Python project saved to: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python tic2py.py game.tic game.py")
    else:
        _, input_file, output_file = sys.argv
        convert_tic_to_python(input_file, output_file)
