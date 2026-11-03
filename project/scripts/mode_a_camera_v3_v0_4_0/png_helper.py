import struct,zlib
def gray_png(pixels, width, height):
    """Losslessly wrap captured Gray8 pixels; no image processing."""
    if len(pixels) != width * height:
        raise ValueError("Gray8 dimensions do not match pixel count")
    def chunk(kind, payload):
        return (struct.pack(">I", len(payload)) + kind + payload +
                struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff))
    scanlines = b"".join(b"\x00" + pixels[y*width:(y+1)*width] for y in range(height))
    return (b"\x89PNG\r\n\x1a\n" +
            chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(scanlines)) + chunk(b"IEND", b""))
