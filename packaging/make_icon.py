# Copyright © 2026 Tradesmart Supplies Limited. All rights reserved. Developed by Maurille Khonde.
"""Make packaging/smartassist.ico (the program's icon) from assets/favicon.png, with no extra package.

A Windows .ico file may simply hold PNG pictures. Sizes 16 to 256 are made with PyMuPDF.
"""
import os
import struct

import pymupdf

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "..", "assets", "favicon.png")
TARGET = os.path.join(HERE, "smartassist.ico")
SIZES = [16, 24, 32, 48, 64, 128, 256]


def png_of_size(size):
    page = pymupdf.open(SOURCE)[0]
    scale = size / page.rect.width
    return page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=True).tobytes("png")


def main():
    pictures = [png_of_size(size) for size in SIZES]
    header = struct.pack("<HHH", 0, 1, len(pictures))
    offset = 6 + 16 * len(pictures)
    entries, data = b"", b""
    for size, picture in zip(SIZES, pictures):
        side = 0 if size == 256 else size          # 0 means 256 in the .ico format
        entries += struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32, len(picture), offset + len(data))
        data += picture
    with open(TARGET, "wb") as f:
        f.write(header + entries + data)
    print("Made", TARGET)


if __name__ == "__main__":
    main()
