"""Parse icon resources out of an EXE and report average color of the 32x32 layer."""
import sys
import pefile

def avg_rgb_of_icon_data(data):
    # data = raw icon image (DIB 32bpp BGRA bottom-up, or PNG)
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        import struct
        # PNG: just report we got PNG (means our icon)
        return None, 'png-' + str(len(data))
    if len(data) < 40:
        return None, 'unknown'
    width = int.from_bytes(data[4:8], 'little')
    height = int.from_bytes(data[8:12], 'little')  # 2x for XOR+AND
    height //= 2
    bpp = int.from_bytes(data[14:16], 'little')
    if bpp != 32:
        return None, f'bpp={bpp}'
    pixel_start = 40
    r = g = b = n = 0
    for y in range(height):
        row = pixel_start + y * width * 4
        for x in range(width):
            o = row + x * 4
            b2 = data[o]; g2 = data[o+1]; r2 = data[o+2]
            r += r2; g += g2; b += b2; n += 1
    return (r//n, g//n, b//n), f'{width}x{height}'

def main():
    path = sys.argv[1]
    pe = pefile.PE(path, fast_load=True)
    pe.parse_data_directories()
    if not hasattr(pe, 'DIRECTORY_ENTRY_RESOURCE'):
        print('NO_RESOURCE_DIR')
        return
    seen = set()
    for entry in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        type_id = entry.id
        if type_id != 3:  # RT_ICON only
            continue
        for name_entry in entry.directory.entries:
            for lang_entry in name_entry.directory.entries:
                offset = lang_entry.data.struct.OffsetToData
                size = lang_entry.data.struct.Size
                data = pe.get_data(offset, size)
                avg, desc = avg_rgb_of_icon_data(data)
                key = desc
                if key in seen:
                    continue
                seen.add(key)
                if avg:
                    print(f'RT_ICON {desc} avgRGB=({avg[0]},{avg[1]},{avg[2]})')
                else:
                    print(f'RT_ICON {desc}')
    pe.close()

if __name__ == '__main__':
    main()