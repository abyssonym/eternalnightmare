from randomtools.tablereader import TableObject
from randomtools.utils import (
    classproperty, mutate_normal,
    utilrandom as random)
from randomtools.interface import (
    run_interface, rewrite_snes_meta, finish_interface)
import string


RANDOMIZE = True
VERSION = 1
ALL_OBJECTS = None


texttable = [(0xA0+i, c) for (i, c) in
             enumerate(string.uppercase + string.lowercase + string.digits)]
texttable += [(0xFF, ' '), (0xE7, "'"), (0xE8, '.'), (0xEB, '-'),
              (0xDF, '?'), (0xE4, "&"), (0x2f, '*')]
texttable += [(c, i) for (i, c) in texttable]
texttable = dict(texttable)
texttable[0xEF] = "~"


def bytes_to_text(data):
    return "".join([texttable[d] if d in texttable else "!" for d in data])


def index_to_item_object(index):
    if index < 0x5A:
        cls = WeaponObject
    elif index < 0x5A + 0x3A:
        cls = ArmorObject
    else:
        cls = Accessory2Object
    index -= cls.first_index
    return cls.get(index)


class TextObject(object):
    @property
    def name(self):
        return bytes_to_text(self.text)


class ItemObject(object):
    first_index = 0

    @property
    def name(self):
        return ItemNameObject.get(self.index + self.first_index).name

    @property
    def full_index(self):
        return self.first_index + self.index

    @property
    def rank_price(self):
        return Item2Object.get(self.index + self.first_index).price

    @property
    def intershuffle_valid(self):
        if isinstance(self, ConsumableObject) and self.get_bit("keyitem"):
            return False
        return self.name != "~~~~~~~~~~"

    @classproperty
    def every_item(self):
        objects = [o for o in ALL_OBJECTS
                   if issubclass(o, ItemObject) and o is not ItemObject]
        objects = [o for ob in objects for o in ob.every]
        return objects

    @classproperty
    def every_buyable(self):
        buyables = [o for o in self.every_item if o.buyable]
        return sorted(buyables,
            key=lambda b: (b.rank_price, b.index, str(type(b))))

    @classproperty
    def every_rare(self):
        return [o for o in self.every_item if o.rare]

    @property
    def buyable(self):
        return self.intershuffle_valid and (self.rank_price >= 20 or
            "Tonic" in self.name or "Heal" in self.name)

    @property
    def rare(self):
        return self.intershuffle_valid and not self.buyable

    @classmethod
    def get(self, index):
        items = [i for i in self.every_item if i.full_index == index]
        if not items:
            return None
        assert len(items) == 1
        return items[0]

    def get_similar(self):
        if self.rare:
            result = random.choice(self.every_rare)
        elif self.buyable:
            buyables = self.every_buyable
            index = buyables.index(self)
            index = mutate_normal(index, minimum=0, maximum=len(buyables)-1)
            result = buyables[index]
        else:
            result = self
        return result


class WeaponObject(ItemObject, TableObject):
    flag = "q"
    flag_description = "equipment stats"
    mutate_attributes = {"power": (0, 0xFE),
                         "critrate": (0, 100),
                         }
    intershuffle_attributes = ["critrate"]


class ArmorObject(ItemObject, TableObject):
    first_index = 0x5A
    flag = "q"
    mutate_attributes = {"power": (0, 99)}


class AccessoryObject(TableObject): pass


class ConsumableObject(ItemObject, TableObject):
    first_index = 0xBC

    @property
    def rank_price(self):
        return self.price


class Item2Object(TableObject):
    flag = "q"

    @property
    def name(self):
        return ItemNameObject.get(self.index).name

    @property
    def is_weapon(self):
        return 0 <= self.index < 0x5A

    def mutate(self):
        self.price = mutate_normal(self.price, minimum=0, maximum=65000)
        if self.equippable and not self.is_weapon:
            self.equippable = random.randint(1, 127) << 1


class CharStatsObject(TableObject):
    flag = "c"
    flag_description = "character stats"

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


class Accessory2Object(ItemObject, TableObject):
    flag = "q"
    first_index = 0x5A + 0x3A

    @property
    def name(self):
        return ItemNameObject.get(self.index + self.first_index).name

    @property
    def rank_price(self):
        return self.price

    def mutate(self):
        if bin(self.equippable).count('1') > 3:
            self.equippable = random.randint(1, 127) << 1


class ItemNameObject(TableObject, TextObject): pass
class TechNameObject(TableObject, TextObject): pass
class TechObject(TableObject): pass
class TechMPObject(TableObject): pass


class GrowthObject:
    flag = "c"
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
    flag = "c"
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
    flag = "c"
    mutate_attributes = {"experience": (1, 0xFFFE)}


class DoubleReqObject(TableObject): pass
class TripleReqObject(TableObject): pass
class ShopItemObject(TableObject): pass
class MonsterNameObject(TableObject, TextObject): pass


class MonsterObject(TableObject):
    flag = "m"
    flag_description = "enemy stats"
    mutate_attributes = {"hp": (0, 30000),
                         "level": (0, 99),
                         "speed": (1, 17),
                         "magic": (0, 254),
                         "magic_defense": (0, 100),
                         "offense": (0, 255),
                         "defense": (0, 255),
                         }
    intershuffle_attributes = [
        "speed", "magic", "offense", "hit",
        "lightning", "shadow", "water", "fire", "evade"]
    shuffle_attributes = [
        ("lightning", "shadow", "water", "fire"),
        ("offense", "magic"),
        ]

    @property
    def rank(self):
        attrs = {"hp": 1,
                 "level": 300,
                 "speed": 1750,
                 "magic": 120,
                 "magic_defense": 100,
                 "offense": 120,
                 "defense": 120,
                 }
        return sum([(b*getattr(self, a)) for (a, b) in attrs.items()])

    @property
    def intershuffle_valid(self):
        return True

    @property
    def name(self):
        return MonsterNameObject.get(self.index).name


class DropObject(TableObject):
    flag = "t"
    mutate_attributes = {"xp": (0, 0xFFFE),
                         "gp": (0, 0xFFFE),
                         #"item": ItemObject,
                         #"charm": ItemObject,
                         "tp": (0, 0xFE)}
    intershuffle_attributes = [
        "item", "charm",
        ]
    shuffle_attributes = [
        ("item", "charm"),
        ("xp", "gp"),
        ]

    @property
    def intershuffle_valid(self):
        if not (self.item or self.charm):
            return False
        item = ItemObject.get(self.item)
        charm = ItemObject.get(self.charm)
        return not (item.rare or charm.rare)

    @property
    def monster(self):
        return MonsterObject.get(self.index)

    @property
    def rank(self):
        return self.monster.rank

    def mutate(self):
        super(DropObject, self).mutate()
        self.item = ItemObject.get(self.item).get_similar().full_index
        self.charm = ItemObject.get(self.charm).get_similar().full_index
        if self.monster.get_bit("bosslike"):
            self.xp = 0
        self.gp = self.gp >> 1


class TreasureObject(TableObject):
    flag = "t"
    flag_description = "treasure"

    @property
    def contents_pretty(self):
        if self.contents & 0x8000:
            return "%s GP" % ((self.contents & 0x7fff) << 1)
        elif self.contents & 0x4000:
            return "Empty"
        else:
            try:
                return ItemNameObject.get(self.contents & 0x3fff).name
            except KeyError:
                return "??????"

    def mutate(self):
        item = None
        if self.contents & 0x8000:
            value = (self.contents & 0x7FFF) << 1
        elif self.contents & 0xFF00:
            return
        else:
            item = ItemObject.get(self.contents & 0xff)
            if item is None:
                return
            if item.rare:
                new_item = item.get_similar()
                self.contents = new_item.full_index
                return
            elif not item.buyable:
                return
            value = item.rank_price
        if random.randint(1, 20) == 20:
            value = mutate_normal(value, minimum=0, maximum=65000)
            self.contents = 0x8000 | (value >> 1)
            return
        if item is None:
            item = [i for i in ItemObject.every_buyable
                    if i.rank_price <= value][-1]
        new_item = item.get_similar()
        self.contents = new_item.full_index


class LocationObject(TableObject): pass


def add_singing_mountain():
    locs = [l for l in LocationObject.every if
            l.mapindex in [0x82, 0x83, 0x84, 0x90] and l.music == 0x3c]
    for l in locs:
        l.music = 0x52


if __name__ == "__main__":
    ALL_OBJECTS = [g for g in globals().values()
                   if isinstance(g, type) and issubclass(g, TableObject)
                   and g not in [TableObject]]
    run_interface(ALL_OBJECTS, snes=True)
    for d in DropObject.every:
        print "%x" % d.item, ItemNameObject.get(d.item).name, "%x" % d.charm, ItemNameObject.get(d.charm).name,
        print "%x %s %s %s" % (d.index, d.xp, d.gp, d.tp)
    minmax = lambda x: (min(x), max(x))
    rewrite_snes_meta("CT-R", VERSION, megabits=32)
    finish_interface()
