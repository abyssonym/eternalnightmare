from randomtools.tablereader import (
    TableObject, set_global_table_filename, sort_good_order)
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


class WeaponObject(TableObject): pass
class ArmorObject(TableObject): pass
class AccessoryObject(TableObject): pass
class Item2Object(TableObject): pass


class CharStatsObject(TableObject):
    mutate_attributes = {
        "power_base": (1, 99),
        "stamina_base": (1, 99),
        "speed": (1, 15),
        "magic_base": (1, 99),
        "hit_base": (1, 99),
        "evade_base": (1, 99),
        "mdef_base": (1, 99),
        "level": (1, 99),
        #"helmet": Item2Object,
        #"armor": Item2Object,
        #"weapon": Item2Object,
        #"accessory": Item2Object,
        }
    intershuffle_attributes = [
        "power_base", "stamina_base", "magic_base",
        "hit_base", "evade_base", "mdef_base", "speed"]

    @classproperty
    def after_order(self):
        return [HPGrowthObject, MPGrowthObject]

    def cleanup(self):
        growth = CharGrowthObject.get(self.index)
        for attr in ["power", "stamina", "magic", "hit",
                     "evade", "mdef"]:
            baseattr = "%s_base" % attr
            increase = getattr(growth, attr) * (self.level-1) / 100
            initial = getattr(self, baseattr) + increase
            setattr(self, attr, initial)

        hpgroup = HPGrowthObject.getgroup(self.index)
        mpgroup = MPGrowthObject.getgroup(self.index)
        max_hp = mutate_normal(85, minimum=1, maximum=999)
        max_mp = mutate_normal(9, minimum=1, maximum=99)
        temp_level = 1
        while temp_level < self.level:
            temp_level += 1
            hpo = [o for o in hpgroup if temp_level <= o.level][-1]
            mpo = [o for o in mpgroup if temp_level <= o.level][-1]
            max_hp += hpo.increase
            max_mp += mpo.increase
        max_hp = min(999, max(max_hp, 1))
        max_mp = min(99, max(max_mp, 1))
        self.max_hp, self.hp = max_hp, max_hp
        self.max_mp, self.mp = max_mp, max_mp

        if self.level > 1:
            self.xp = sum([e.experience for e in ExperienceObject
                           if e.index < (self.level-1)])
        else:
            self.xp = 0
        self.xpnext = ExperienceObject.get(self.level-1).experience


class Accessory2Object(TableObject): pass
class ItemNameObject(TableObject, TextObject): pass
class TechNameObject(TableObject, TextObject): pass
class TechObject(TableObject): pass
class TechMPObject(TableObject): pass


class GrowthObject:
    groupshuffle_enabled = True

    @classmethod
    def mutate_all(cls):
        for group in cls.groups.values():
            for o in group:
                while o.level >= 100 or o.level == 0:
                    other = random.choice(group)
                    o.level = random.randint(2, random.randint(2, 99))
                    o.increase = max(1, other.increase)
                o.mutate()

    @classmethod
    def full_cleanup(cls):
        for group in cls.groups.values():
            while True:
                levels = [o.level for o in group]
                if len(set(levels)) == len(levels):
                    break
                for o in group:
                    o.mutate()
            levincs = sorted([(o.level, o.increase) for o in group])
            for o, (level, increase) in zip(group, levincs):
                o.level = level
                o.increase = increase
            group[-1].level = 99
        cls.cleaned = True


class HPGrowthObject(GrowthObject, TableObject):
    mutate_attributes = {
        "level": (2, 99),
        "increase": None,
        }


class MPGrowthObject(GrowthObject, TableObject):
    mutate_attributes = {
        "level": (2, 99),
        "increase": (0, 3),
        }


class CharGrowthObject(TableObject):
    mutate_attributes = {
        "power": None,
        "stamina": None,
        "magic": None,
        "hit": None,
        "evade": None,
        "mdef": None,
        }
    intershuffle_attributes = [
        "power", "stamina", "magic", "hit", "evade", "mdef"]


class ExperienceObject(TableObject):
    mutate_attributes = {"experience": (1, 65535)}


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
    all_objects = sort_good_order(all_objects)
    for ao in all_objects:
        ao.every

    '''
    techpointers = [t.pointer for t in TechObject.every]
    random.shuffle(techpointers)
    for t, tp in zip(TechObject.every, techpointers):
        t.pointer = tp
    '''
    for ao in all_objects:
        ao.full_randomize()
    for ao in all_objects:
        ao.full_cleanup()

    for c in CharStatsObject.every:
        print c.long_description
        print "---"
        print CharGrowthObject.get(c.index).long_description
        print

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
