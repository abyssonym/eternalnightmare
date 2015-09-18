from randomtools.tablereader import TableObject, set_global_table_filename
from randomtools.utils import (
    read_multi, write_multi, classproperty, mutate_normal, hexstring,
    rewrite_snes_title, rewrite_snes_checksum,
    utilrandom as random)
from shutil import copyfile
from os import path
from sys import argv
from time import time
import string


try:
    from sys import _MEIPASS
    tblpath = path.join(_MEIPASS, "tables")
except ImportError:
    tblpath = "tables"

RANDOMIZE = True
VERSION = 1


texttable = [(0xA0+i, c) for (i, c) in
             enumerate(string.uppercase + string.lowercase + string.digits)]
texttable += [(0xFF, ' '), (0xE7, "'"), (0xE8, '.'), (0x2f, '*')]
texttable += [(c, i) for (i, c) in texttable]
texttable = dict(texttable)
texttable[0xEF] = "~"


def bytes_to_text(data):
    return "".join([texttable[d] for d in data])


class TextObject(object):
    @property
    def name(self):
        return bytes_to_text(self.text)


class CharStatsObject(TableObject): pass
class WeaponObject(TableObject): pass
class ArmorObject(TableObject): pass
class AccessoryObject(TableObject): pass
class Item2Object(TableObject): pass
class Accessory2Object(TableObject): pass
class ItemNameObject(TableObject, TextObject): pass
class TechNameObject(TableObject, TextObject): pass
class TechObject(TableObject): pass
class TechMPObject(TableObject): pass
class DoubleReqObject(TableObject): pass
class TripleReqObject(TableObject): pass
class ShopItemObject(TableObject): pass
class MonsterObject(TableObject): pass
class DropObject(TableObject): pass
class TreasureObject(TableObject): pass
class LocationObject(TableObject): pass


def add_singing_mountain():
    locs = [l for l in LocationObject.every if
            l.mapindex in [0x82, 0x83, 0x84, 0x90] and l.music == 0x3c]
    for l in locs:
        l.music = 0x52


if __name__ == "__main__":
    if len(argv) >= 2:
        sourcefile = argv[1]
        if len(argv) >= 3:
            seed = int(argv[2])
        else:
            seed = None
    else:
        sourcefile = raw_input("Filename? ")
        seed = raw_input("Seed? ")

    if seed is None or seed == "":
        seed = int(time())
    seed = seed % (10**10)

    outfile = sourcefile.split(".")
    outfile = outfile[:-1] + [str(seed), outfile[-1]]
    txtfile = ".".join(outfile[:-1] + ["txt"])
    outfile = ".".join(outfile)
    copyfile(sourcefile, outfile)
    set_global_table_filename(outfile)

    all_objects = [g for g in globals().values()
                   if isinstance(g, type) and issubclass(g, TableObject)
                   and g not in [TableObject]]
    for ao in all_objects:
        ao.every

    '''
    techpointers = [t.pointer for t in TechObject.every]
    random.shuffle(techpointers)
    for t, tp in zip(TechObject.every, techpointers):
        t.pointer = tp
    '''

    for i, t in enumerate(TechNameObject):
        print "%x" % i, t.name
    import pdb; pdb.set_trace()

    for ao in all_objects:
        ao.write_all(outfile)

    rewrite_snes_title("CT-R %s" % seed, outfile, VERSION)
    rewrite_snes_checksum(outfile, megabits=32)

    '''
    s = ""
    for ao in sorted(all_objects, key=lambda a: a.__name__):
        s += ao.__name__.upper() + "\n"
        s += ao.catalogue
        s += "\n\n"
    s = s.strip()
    f = open(txtfile, "w+")
    f.write(s + "\n")
    f.close()
    '''
