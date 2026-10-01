import sys

def load(path):
    with open(path, "rb") as f:
        return f.read()

def find_diff_ranges(a, b, min_gap=4):
    """
    Знаходить діапазони байтів, де a і b відрізняються.
    min_gap - якщо сусідні відмінності ближче, ніж min_gap байт одна до одної,
    вони об'єднуються в один діапазон (щоб не дробити на купу дрібних).
    Повертає список (start, end) - напіввідкриті інтервали [start, end).
    """
    n = min(len(a), len(b))
    diffs = [i for i in range(n) if a[i] != b[i]]

    if not diffs:
        return []

    ranges = []
    start = diffs[0]
    prev = diffs[0]

    for idx in diffs[1:]:
        if idx - prev <= min_gap:
            prev = idx
            continue
        ranges.append((start, prev + 1))
        start = idx
        prev = idx

    ranges.append((start, prev + 1))
    return ranges

def hex_preview(data, start, end, context=4):
    """Друкує hex-дамп діапазону з невеликим контекстом навколо."""
    lo = max(0, start - context)
    hi = min(len(data), end + context)
    chunk = data[lo:hi]
    hex_str = " ".join(f"{b:02X}" for b in chunk)
    ascii_str = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
    return f"    @0x{lo:04X}: {hex_str}\n    ASCII: {ascii_str}"

def compare(name_a, data_a, name_b, data_b):
    print(f"\n{'=' * 70}")
    print(f"ПОРІВНЯННЯ: {name_a}  vs  {name_b}")
    print(f"Розміри: {len(data_a)} vs {len(data_b)} байт")
    print(f"{'=' * 70}")

    ranges = find_diff_ranges(data_a, data_b, min_gap=4)

    if not ranges:
        print("  Файли ідентичні (в межах спільної довжини).")
        return []

    print(f"  Знайдено {len(ranges)} відмінних ділянок:\n")
    for start, end in ranges:
        size = end - start
        print(f"  [0x{start:04X} - 0x{end:04X}]  ({size} байт різниці)")
        print(f"  {name_a}:")
        print(hex_preview(data_a, start, end))
        print(f"  {name_b}:")
        print(hex_preview(data_b, start, end))
        print()

    return ranges

def ranges_overlap(r1_list, r2_list, slack=16):
    """Знаходить діапазони з r1_list, які перетинаються (із запасом slack)
    з будь-яким діапазоном із r2_list. Корисно, щоб знайти області,
    що відрізняються в ОБОХ порівняннях - сильний кандидат на fan/thermal."""
    overlaps = []
    for s1, e1 in r1_list:
        s1x, e1x = s1 - slack, e1 + slack
        for s2, e2 in r2_list:
            if s1x < e2 and s2 < e1x:
                overlaps.append((max(s1, s2), min(e1, e2), s1, e1, s2, e2))
    return overlaps

def main():
    if len(sys.argv) < 4:
        print("Використання:")
        print("  python compare_vbios.py zotac_p104.rom zotac_1080mini.rom gigabyte_p104.rom")
        sys.exit(1)

    path_zotac_p104, path_zotac_1080mini, path_gigabyte_p104 = sys.argv[1:4]

    zotac_p104 = load(path_zotac_p104)
    zotac_1080mini = load(path_zotac_1080mini)
    gigabyte_p104 = load(path_gigabyte_p104)

    # Порівняння 1: два Zotac (імовірно той самий PCB/VRM дизайн)
    diffs_zotac_vs_zotac = compare(
        "Zotac P104", zotac_p104,
        "Zotac 1080 Mini", zotac_1080mini
    )

    # Порівняння 2: Zotac P104 vs Gigabyte P104 (той самий чип, інший партнер/BIOS)
    diffs_zotac_vs_gigabyte = compare(
        "Zotac P104", zotac_p104,
        "Gigabyte P104", gigabyte_p104
    )

    # Перетин: області, які відрізняються в ОБОХ порівняннях -
    # сильні кандидати саме на fan/thermal таблицю
    print(f"\n{'=' * 70}")
    print("ОБЛАСТІ, ЩО ВІДРІЗНЯЮТЬСЯ В ОБОХ ПОРІВНЯННЯХ (сильні кандидати):")
    print(f"{'=' * 70}")

    overlaps = ranges_overlap(diffs_zotac_vs_zotac, diffs_zotac_vs_gigabyte, slack=16)

    if not overlaps:
        print("  Перетинів не знайдено. Можливо, Zotac P104 і Zotac 1080 Mini")
        print("  надто різні плати (не справжні 'клони'), або fan-таблиця")
        print("  відрізняється лише між Zotac/Gigabyte, але не всередині лінійки Zotac.")
    else:
        for overlap_start, overlap_end, s1, e1, s2, e2 in overlaps:
            print(f"\n  Перетин @ [0x{overlap_start:04X} - 0x{overlap_end:04X}]")
            print(f"    (із Zotac-vs-Zotac діапазону 0x{s1:04X}-0x{e1:04X}")
            print(f"     і Zotac-vs-Gigabyte діапазону 0x{s2:04X}-0x{e2:04X})")

if __name__ == "__main__":
    main()