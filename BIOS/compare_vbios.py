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

def compare(name_a, data_a, name_b, data_b, report):
    header = f"\n{'=' * 70}\nПОРІВНЯННЯ: {name_a}  vs  {name_b}\nРозміри: {len(data_a)} vs {len(data_b)} байт\n{'=' * 70}"
    print(header)
    report.write(header + "\n")

    ranges = find_diff_ranges(data_a, data_b, min_gap=4)

    if not ranges:
        msg = "  Файли ідентичні (в межах спільної довжини)."
        print(msg)
        report.write(msg + "\n")
        return []

    # У КОНСОЛЬ - лише компактне зведення: список діапазонів та їхніх розмірів
    print(f"  Знайдено {len(ranges)} відмінних ділянок (подробиці -> у файл):")
    total_diff_bytes = sum(e - s for s, e in ranges)
    print(f"  Сумарно відрізняється: {total_diff_bytes} байт із {min(len(data_a), len(data_b))}")
    for start, end in ranges:
        print(f"    [0x{start:04X} - 0x{end:04X}]  ({end - start} байт)")

    # У ФАЙЛ - повні hex-дампи по кожному діапазону
    report.write(f"  Знайдено {len(ranges)} відмінних ділянок:\n\n")
    for start, end in ranges:
        size = end - start
        report.write(f"  [0x{start:04X} - 0x{end:04X}]  ({size} байт різниці)\n")
        report.write(f"  {name_a}:\n")
        report.write(hex_preview(data_a, start, end) + "\n")
        report.write(f"  {name_b}:\n")
        report.write(hex_preview(data_b, start, end) + "\n\n")

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

    report_path = "vbios_diff_report.txt"
    with open(report_path, "w", encoding="utf-8") as report:

        # Порівняння 1: два Zotac (імовірно той самий PCB/VRM дизайн)
        diffs_zotac_vs_zotac = compare(
            "Zotac P104", zotac_p104,
            "Zotac 1080 Mini", zotac_1080mini,
            report
        )

        # Порівняння 2: Zotac P104 vs Gigabyte P104 (той самий чип, інший партнер/BIOS)
        diffs_zotac_vs_gigabyte = compare(
            "Zotac P104", zotac_p104,
            "Gigabyte P104", gigabyte_p104,
            report
        )

        # Перетин: області, які відрізняються в ОБОХ порівняннях -
        # сильні кандидати саме на fan/thermal таблицю
        summary = f"\n{'=' * 70}\nОБЛАСТІ, ЩО ВІДРІЗНЯЮТЬСЯ В ОБОХ ПОРІВНЯННЯХ (сильні кандидати):\n{'=' * 70}"
        print(summary)
        report.write(summary + "\n")

        overlaps = ranges_overlap(diffs_zotac_vs_zotac, diffs_zotac_vs_gigabyte, slack=16)

        if not overlaps:
            msg = ("  Перетинів не знайдено. Можливо, Zotac P104 і Zotac 1080 Mini\n"
                   "  надто різні плати (не справжні 'клони'), або fan-таблиця\n"
                   "  відрізняється лише між Zotac/Gigabyte, але не всередині лінійки Zotac.")
            print(msg)
            report.write(msg + "\n")
        else:
            for overlap_start, overlap_end, s1, e1, s2, e2 in overlaps:
                line1 = f"\n  Перетин @ [0x{overlap_start:04X} - 0x{overlap_end:04X}]"
                line2 = f"    (із Zotac-vs-Zotac діапазону 0x{s1:04X}-0x{e1:04X}"
                line3 = f"     і Zotac-vs-Gigabyte діапазону 0x{s2:04X}-0x{e2:04X})"
                print(line1); print(line2); print(line3)
                report.write(line1 + "\n" + line2 + "\n" + line3 + "\n")

    print(f"\nПовний звіт із hex-дампами збережено в: {report_path}")
    print("У консолі вище - лише зведення (список діапазонів і підсумкові перетини).")
    print("Надішли мені ЦЕ зведення (те, що в консолі), а не весь файл звіту.")

if __name__ == "__main__":
    main()