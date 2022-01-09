import zlib
import ctypes

with open('../strings.txt') as f:
    lines = f.readlines()

with open('../strings2.txt', 'w') as the_file:
    for line in lines:
        subline = line[35:-1].encode()
        crc32 = ctypes.c_int32(zlib.crc32(subline)).value
        the_file.write("'%s' = %s\n" % (subline, crc32))