import sys

def load(path):
    with open(path, "rb") as f:
        return f.read()

def hex_dump(data, start, end, context=6):
    lo = max(0, start - context)
    hi = min(len(data), end + context)
    chunk = data[lo:hi]
    hex_str = " ".join(f"{b:02X}" for b in chunk)
    ascii_str = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
    return f"  @0x{lo:04X}: {hex_str}\n  ASCII: {ascii_str}"

# Ті самі компактні, перспективні діапазони з початку файлу,
# де перетнулися обидва порівняння (Zotac-vs-Zotac і Zotac-vs-Gigabyte)
RANGES = [
    (0x0004, 0x0010),
    (0x0A36, 0x0A52),
    (0x0AEE, 0x0AF6),
    (0x0BC8, 0x0BD4),
    (0x0C6F, 0x0C73),
    (0x0DCD, 0x0DE3),
    (0x0E05, 0x0E26),
]

def main():
    if len(sys.argv) < 4:
        print("Використання:")
        print("  python extract_ranges.py zotac_p104.rom zotac_1080mini.rom gigabyte_p104.rom")
        sys.exit(1)

    path_a, path_b, path_c = sys.argv[1:4]
    a = load(path_a)
    b = load(path_b)
    c = load(path_c)

    for start, end in RANGES:
        print(f"\n{'=' * 60}")
        print(f"Діапазон [0x{start:04X} - 0x{end:04X}]")
        print(f"{'=' * 60}")
        print("Zotac P104:")
        print(hex_dump(a, start, end))
        print("Zotac 1080 Mini:")
        print(hex_dump(b, start, end))
        print("Gigabyte P104:")
        print(hex_dump(c, start, end))

if __name__ == "__main__":
    main()