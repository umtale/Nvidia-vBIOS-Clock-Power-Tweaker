import struct
import sys

def find_bit_header(data):
    """Шукаємо сигнатуру FF B8 42 49 54 00 (ID 0xB8FF + 'BIT\\0')"""
    sig = bytes([0xFF, 0xB8]) + b"BIT\x00"
    offset = data.find(sig)
    if offset == -1:
        raise ValueError("BIT-сигнатуру не знайдено у файлі!")
    return offset

def find_image_layout(data, bit_offset):
    """
    Усі вказівники BIT відраховуються від початку legacy-образу (55 AA), а не від
    початку файлу (у файлі перед образом може лежати NVGI-заголовок).

    Вказівники >= довжини legacy-образу ведуть в extension-образ (56 4E + NPDS,
    code type 0xE0), ніби він іде одразу за legacy-образом: UEFI-образ
    між ними пропускається.

    Повертає (base, image0_length, extension_offset); extension_offset = None,
    якщо extension-образу немає.
    """
    base = -1
    cursor = bit_offset
    while True:
        cursor = data.rfind(b"\x55\xAA", 0, cursor + 1)
        if cursor == -1:
            raise ValueError("Legacy-образ (55 AA + PCIR) перед BIT не знайдено!")
        pcir = cursor + struct.unpack_from("<H", data, cursor + 0x18)[0]
        if data[pcir:pcir + 4] == b"PCIR":
            base = cursor
            break
        cursor -= 1

    image0_length = 0
    extension_offset = None
    offset = base

    print("Образи у файлі:")
    for i in range(8):
        if data[offset:offset + 2] not in (b"\x55\xAA", b"\x56\x4E"):
            break
        pcir = offset + struct.unpack_from("<H", data, offset + 0x18)[0]
        if data[pcir:pcir + 4] not in (b"PCIR", b"NPDS"):
            break

        length = struct.unpack_from("<H", data, pcir + 0x10)[0] * 512
        code_type = data[pcir + 0x14]
        print(f"  @0x{offset:05X}  {data[offset:offset + 2].hex(' ').upper()}  "
              f"{data[pcir:pcir + 4].decode()}  довжина=0x{length:X}  code type=0x{code_type:02X}")

        if i == 0:
            image0_length = length
        elif code_type == 0xE0 and extension_offset is None:
            extension_offset = offset

        if length == 0:
            break
        offset += length
    print()

    return base, image0_length, extension_offset

def resolve_pointer(pointer, layout):
    """Переводить вказівник BIT у зміщення у файлі (None, якщо не виходить)"""
    base, image0_length, extension_offset = layout
    if pointer == 0:
        return None
    if pointer < image0_length:
        return base + pointer
    if extension_offset is not None:
        return extension_offset + pointer - image0_length
    return None

def parse_bit_header(data, bit_offset):
    """
    Структура заголовка (від початку сигнатури):
    2 байти ID (FF B8) - вже враховано в сигнатурі
    4 байти "BIT\\0"
    2 байти BCD Version
    1 байт Header Size
    1 байт Token Size
    1 байт Token Entries
    1 байт Checksum
    """
    # сигнатура сама по собі 6 байт (2+4), далі йдуть решта полів
    base = bit_offset
    bcd_version = struct.unpack_from("<H", data, base + 6)[0]
    header_size = data[base + 8]
    token_size = data[base + 9]
    token_entries = data[base + 10]
    checksum = data[base + 11]

    print(f"BIT header @ 0x{bit_offset:04X}")
    print(f"  BCD Version   : 0x{bcd_version:04X}")
    print(f"  Header Size   : {header_size}")
    print(f"  Token Size    : {token_size}")
    print(f"  Token Entries : {token_entries}")
    print(f"  Checksum      : 0x{checksum:02X}")
    print()

    return header_size, token_size, token_entries

def find_perf_token(data, bit_offset, header_size, token_size, token_entries):
    """Перебираємо токени, шукаємо ID = 0x50 ('P' = BIT_TOKEN_PERF_PTRS)"""
    first_token_offset = bit_offset + header_size

    print(f"Перший токен починається з 0x{first_token_offset:04X}")
    print("Усі знайдені токени:")

    perf_token = None
    for i in range(token_entries):
        tok_off = first_token_offset + i * token_size
        tok_id = data[tok_off]
        data_version = data[tok_off + 1]
        data_size = struct.unpack_from("<H", data, tok_off + 2)[0]
        data_ptr = struct.unpack_from("<H", data, tok_off + 4)[0]

        id_char = chr(tok_id) if 32 <= tok_id <= 126 else "?"
        print(f"  [{i:2}] @0x{tok_off:04X}  ID=0x{tok_id:02X} ('{id_char}')  "
              f"DataVer={data_version}  Size={data_size}  Ptr=0x{data_ptr:04X}")

        if tok_id == 0x50:  # 'P' -> BIT_TOKEN_PERF_PTRS
            perf_token = (data_version, data_size, data_ptr)

    print()
    if perf_token is None:
        raise ValueError("Токен PERF_PTRS (ID=0x50) не знайдено!")

    return perf_token

def dump_perf_ptrs_v2(data, perf_ptr_offset, data_size, layout):
    """
    BIT_PERF_PTRS Version 2 - список 32-бітних вказівників поспіль,
    у порядку, задокументованому NVIDIA.
    Виводимо назву таблиці, вказівник і його зміщення у файлі.
    """
    fields = [
        "Performance Table Pointer",
        "Memory Clock Table Pointer",
        "Memory Tweak Table Pointer",
        "Power Control Table Pointer",
        "Thermal Control Table Pointer",
        "Thermal Device Table Pointer",
        "Thermal Coolers Table Pointer",
        "Performance Settings Script Pointer",
        "Continuous Virtual Binning Table Pointer",
        "Ventura Table Pointer",
        "Power Sensors Table Pointer",
        "Power Policy Table Pointer",
        "P-State Clock Range Table Pointer",
        "Voltage Frequency Table Pointer",
        "Virtual P-State Table Pointer",
        "Power Topology Table Pointer",
        "Power Leakage Table Pointer",
        "Performance Test Specifications Table Pointer",
        "Thermal Channel Table Pointer",
        "Thermal Adjustment Table Pointer",
        "Thermal Policy Table Pointer",
        "P-State Memory Clock Frequency Table Pointer",
        "Fan Cooler Table Pointer",
        "Fan Policy Table Pointer",
        "DI/DT Table Pointer",
        "Fan Test Table Pointer",
        "Voltage Rail Table Pointer",
        "Voltage Device Table Pointer",
        "Voltage Policy Table Pointer",
        "LowPower Table Pointer",
        "LowPower PCIe Table Pointer",
        "LowPower PCIe-Platform Table Pointer",
        "LowPower GR Table Pointer",
        "LowPower MS Table Pointer",
        "LowPower DI Table Pointer",
        "LowPower GC6 Table Pointer",
        "LowPower PSI Table Pointer",
        "Thermal Monitor Table Pointer",
        "Overclocking Table Pointer",
        "LowPower NVLINK Table Pointer",
    ]

    print(f"BIT_PERF_PTRS @ зміщення у файлі 0x{perf_ptr_offset:04X}")
    print("=" * 78)

    results = {}
    for i, name in enumerate(fields):
        if (i + 1) * 4 > data_size:
            break
        field_offset = perf_ptr_offset + i * 4
        value = struct.unpack_from("<I", data, field_offset)[0]
        file_offset = resolve_pointer(value, layout)

        location = "-" if file_offset is None else f"файл 0x{file_offset:05X}"
        marker = "  <---" if "Fan" in name or "Thermal" in name else ""
        print(f"  [{i:2}] {name:45s} = 0x{value:05X}  {location}{marker}")
        results[name] = file_offset

    print()
    return results

def dump_fan_tables(data, results):
    """
    Розбір Fan Cooler Table і Fan Policy Table версії 1.0 (Pascal).
    Зміщення полів підібрано порівнянням кількох vBIOS, офіційного
    опису немає.
    """
    cooler = results.get("Fan Cooler Table Pointer")
    policy = results.get("Fan Policy Table Pointer")

    if cooler is None or policy is None:
        print("Fan-таблиці не знайдено.")
        return
    if data[cooler:cooler + 3] != bytes([0x10, 0x04, 0x1A]) or data[policy:policy + 3] != bytes([0x10, 0x05, 0x35]):
        print("Заголовки fan-таблиць не в очікуваному форматі (чекаємо 10 04 1A і 10 05 35), розбір пропущено.")
        return

    entry = cooler + 4
    print(f"Fan Cooler Table @ 0x{cooler:05X} (жорсткі ліміти)")
    print(f"  raw: {data[cooler:cooler + 4 + 0x1A].hex(' ').upper()}")
    print(f"  @0x{entry + 2:05X}  PWM min : {data[entry + 2]} %")
    print(f"  @0x{entry + 3:05X}  PWM max : {data[entry + 3]} %")
    print(f"  @0x{entry + 14:05X}  RPM min : {struct.unpack_from('<H', data, entry + 14)[0]}")
    print(f"  @0x{entry + 16:05X}  RPM max : {struct.unpack_from('<H', data, entry + 16)[0]}")
    print()

    entry = policy + 5
    print(f"Fan Policy Table @ 0x{policy:05X} (крива, 3 точки)")
    print(f"  raw: {data[policy:policy + 5 + 0x35].hex(' ').upper()}")
    for point in range(3):
        pwm_off = entry + 17 + point
        temp_off = entry + 21 + point * 4
        rpm_off = temp_off + 2
        temp = struct.unpack_from("<H", data, temp_off)[0] / 32  # температура зберігається в 1/32 °C
        rpm = struct.unpack_from("<H", data, rpm_off)[0]
        print(f"  Точка {point + 1}: {temp:g} °C (@0x{temp_off:05X})  "
              f"{data[pwm_off]} % (@0x{pwm_off:05X})  {rpm} RPM (@0x{rpm_off:05X})")

def main():
    if len(sys.argv) < 2:
        print("Використання: python find_fan_table.py шлях_до_vbios.rom")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, "rb") as f:
        data = f.read()

    print(f"Файл: {path}  ({len(data)} байт)\n")

    bit_offset = find_bit_header(data)
    layout = find_image_layout(data, bit_offset)
    header_size, token_size, token_entries = parse_bit_header(data, bit_offset)
    data_version, data_size, perf_ptr = find_perf_token(
        data, bit_offset, header_size, token_size, token_entries
    )

    print(f"PERF_PTRS token: DataVersion={data_version}, DataSize={data_size}, "
          f"DataPointer=0x{perf_ptr:04X}\n")

    if data_version != 2:
        print(f"УВАГА: DataVersion={data_version}, а не 2 — структура полів "
              f"може відрізнятися від того, що очікує цей скрипт!\n")

    # вказівник токена теж відраховується від початку legacy-образу
    results = dump_perf_ptrs_v2(data, layout[0] + perf_ptr, data_size, layout)
    dump_fan_tables(data, results)

if __name__ == "__main__":
    main()
