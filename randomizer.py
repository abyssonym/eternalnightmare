from randomtools.tablereader import TableObject
from randomtools.utils import (
    classproperty, mutate_normal,
    utilrandom as random)
from randomtools.interface import (
    get_outfile, run_interface, rewrite_snes_meta,
    clean_and_write, finish_interface)
import string


RANDOMIZE = True
VERSION = 4
ALL_OBJECTS = None


texttable = [(0xA0+i, c) for (i, c) in
             enumerate(string.uppercase + string.lowercase + string.digits)]
texttable += [(0xFF, ' '), (0xE7, "'"), (0xE8, '.'), (0xEB, '-'),
              (0xDF, '?'), (0xE4, "&"), (0x2f, '*')]
texttable += [(c, i) for (i, c) in texttable]
texttable = dict(texttable)
texttable[0xEF] = "~"


def randomize_rng(address=0xFE00):
    numbers = range(0x100)
    random.shuffle(numbers)
    f = open(get_outfile(), 'r+b')
    f.seek(address)
    f.write("".join([chr(n) for n in numbers]))
    f.close()


def bytes_to_text(data):
    return "".join([texttable[d] if d in texttable else "!" for d in data])


def index_to_item_object(index):
    if index < ArmorObject.first_index:
        cls = WeaponObject
    elif index < Accessory2Object.first_index:
        cls = ArmorObject
    else:
        cls = Accessory2Object
    index -= cls.first_index
    return cls.get(index)


class TextObject(object):
    @property
    def name(self):
        return bytes_to_text(self.text)


class CharObject(object):
    @property
    def name(self):
        return {0: "Crono",
                1: "Marle",
                2: "Lucca",
                3: "Robo",
                4: "Frog",
                5: "Ayla",
                6: "Magus"}[self.index]


class ItemObject(object):
    first_index = 0

    @property
    def name(self):
        return ItemNameObject.get(self.index + self.first_index).name

    @property
    def full_index(self):
        return self.first_index + self.index

    @property
    def is_weapon(self):
        return self.full_index < ArmorObject.first_index

    @property
    def is_armor(self):
        return ArmorObject.first_index <= self.full_index < 0x7B

    @property
    def is_helmet(self):
        return 0x7B <= self.full_index < Accessory2Object.first_index

    @property
    def is_accessory(self):
        return (Accessory2Object.first_index <= self.full_index
                < ConsumableObject.first_index)

    @property
    def item2(self):
        return Item2Object.get(self.index + self.first_index)

    @property
    def rank_price(self):
        price = self.item2.price
        if ((self.is_armor or self.is_helmet) and price >= 20 and
                (self.status_enabled or self.item2.element) and
                not (hasattr(self, "repriced") and self.repriced == True)):
            if self.is_armor:
                self.item2.price *= 3
            elif self.is_helmet:
                self.item2.price *= 2
            self.item2.price = min(self.item2.price, 65000)
            self.repriced = True
        return price

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
    def every_equippable(self):
        return [i for i in self.every_item if hasattr(i, "equippable")]

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

    def make_equippable(self, index):
        if self.is_armor or self.is_helmet:
            self.item2.equippable |= (0x80 >> index)
        if self.is_accessory:
            self.equippable |= (0x80 >> index)


class WeaponObject(ItemObject, TableObject):
    flag = "q"
    flag_description = "equipment stats"
    mutate_attributes = {"power": (0, 0xFE),
                         "critrate": (0, 100),
                         }
    intershuffle_attributes = ["critrate"]

    @property
    def equippable(self):
        return self.item2.equippable

    def mutate(self):
        if self.intershuffle_valid:
            super(WeaponObject, self).mutate()


class ArmorObject(ItemObject, TableObject):
    first_index = WeaponObject.first_index + 0x5A
    flag = "q"
    mutate_attributes = {"power": (0, 99)}

    @property
    def equippable(self):
        return self.item2.equippable

    def mutate(self):
        if self.intershuffle_valid:
            super(ArmorObject, self).mutate()


class AccessoryObject(TableObject): pass


class Item2Object(TableObject):
    flag = "q"

    @property
    def name(self):
        return ItemNameObject.get(self.index).name

    @property
    def is_weapon(self):
        return 0 <= self.index < 0x5A

    def mutate(self):
        value = mutate_normal(self.price, minimum=0, maximum=65000)
        value = value * 2
        power = 0
        while value > 100:
            value /= 10
            power += 1
        value = (value * (10**power)) / 2
        self.price = value
        if self.equippable and not self.is_weapon:
            self.equippable = random.randint(1, 127) << 1


class CharStatsObject(CharObject, TableObject):
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

    def can_equip(self, item):
        if isinstance(item, int):
            item = ItemObject.get(item)
        return bool(item.equippable & (0x80 >> self.index))

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

        for attr in ["helmet", "armor"]:
            current = getattr(self, attr)
            if self.can_equip(current):
                continue
            candidates = [c for c in ItemObject.every_equippable
                          if getattr(c, "is_%s" % attr) and
                          self.can_equip(c) and
                          c.buyable]
            if not candidates:
                candidates = [c for c in ItemObject.every_equippable
                              if getattr(c, "is_%s" % attr) and
                              c.buyable]
            chosen = min(candidates, key=lambda c: c.rank_price)
            chosen.make_equippable(self.index)
            setattr(self, attr, chosen.full_index)
        current = ItemObject.get(self.accessory)
        if not self.can_equip(current):
            candidates = [c for c in Accessory2Object.every
                          if self.can_equip(c)]
            if candidates:
                chosen = random.choice(candidates)
                chosen.make_equippable(self.index)
                self.accessory = chosen.full_index


class Accessory2Object(ItemObject, TableObject):
    flag = "q"
    first_index = ArmorObject.first_index + 0x3A

    @property
    def name(self):
        return ItemNameObject.get(self.index + self.first_index).name

    @property
    def rank_price(self):
        return self.price

    def mutate(self):
        if bin(self.equippable).count('1') > 3:
            self.equippable = random.randint(1, 127) << 1


class ConsumableObject(ItemObject, TableObject):
    first_index = Accessory2Object.first_index + 0x28

    @property
    def rank_price(self):
        return self.price


class ItemNameObject(TableObject, TextObject): pass
class TechNameObject(TableObject, TextObject): pass


class TechObject(TableObject):
    flag = "k"
    flag_description = "tech power, mp, and requirements"

    mutate_attributes = {"damage": (1, 0xFE)}
    @property
    def name(self):
        return TechNameObject.get(self.index).name


class TechMPObject(TableObject):
    flag = "k"
    mutate_attributes = {"mp": (1, 99)}


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
        if not any([hasattr(o, "mutated") for o in cls.every]):
            cls.cleaned = True
            return
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


class CharGrowthObject(CharObject, TableObject):
    flag = "c"
    mutate_attributes = {
        "power": (1, 0xFE),
        "stamina": (1, 0xFE),
        "magic": (1, 0xFE),
        "hit": (1, 100),
        "evade": (1, 100),
        "mdef": (1, 0xFE),
        }
    intershuffle_attributes = [
        "power", "stamina", "magic", "hit", "evade", "mdef"]


class ExperienceObject(TableObject):
    flag = "c"
    mutate_attributes = {"experience": (1, 0xFFFE)}


class ReqMPObject(object):
    flag = 'k'
    shuffle_attributes = [("reqs",)]


class DoubleReqMPObject(ReqMPObject, TableObject): pass
class TripleReqMPObject(ReqMPObject, TableObject): pass


class ShopItemObject(TableObject):
    flag = "p"
    flag_description = "shops"

    @classmethod
    def mutate_all(cls):
        numgroups = len(cls.groups)
        reassignments = range(numgroups)
        random.shuffle(reassignments)
        reassignments = dict(zip(range(numgroups), reassignments))
        for o in cls.every:
            o.groupindex = reassignments[o.groupindex]

        for n, group in sorted(cls.groups.items()):
            for i, o in enumerate(group):
                done = [o2.item for o2 in group[:i]]
                item = ItemObject.get(o.item)
                for _ in xrange(100):
                    new_item = item.get_similar()
                    if new_item.full_index not in done:
                        break
                else:
                    candidates = [i for i in ItemObject.every_buyable
                                  if i.full_index not in done]
                    new_item = random.choice(candidates)
                o.item = new_item.full_index
            indices_sorted = sorted(group[:-1], key=lambda i: i.item)
            indices_sorted = [i.item for i in indices_sorted]
            for (a, b) in zip(group, indices_sorted):
                a.item = b


class MonsterNameObject(TableObject, TextObject): pass


class MonsterObject(TableObject):
    flag = "m"
    flag_description = "enemy stats"
    mutate_attributes = {"hp": (0, 30000),
                         "level": (0, 99),
                         "speed": (1, 17),
                         "magic": (0, 254),
                         "magic_defense": (0, 0xFE),
                         "offense": (0, 255),
                         "defense": (0, 255),
                         "evade": (1, 100),
                         "hit": (0, 100),
                         }
    intershuffle_attributes = [
        "speed", "magic", "hit",
        ("lightning", "shadow", "water", "fire"), "evade"]
    shuffle_attributes = [
        ("lightning", "shadow", "water", "fire"),
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
        return self.name != "~~~~~~~~~~~" and not self.get_bit("bosslike")

    @property
    def name(self):
        return MonsterNameObject.get(self.index).name

    def mutate(self):
        oldstats = {}
        for key in self.mutate_attributes:
            oldstats[key] = getattr(self, key)
        super(MonsterObject, self).mutate()
        if self.get_bit("bosslike"):
            for (attr, oldval) in oldstats.items():
                if getattr(self, attr) < oldval:
                    setattr(self, attr, oldval)

        def is_resistance(val):
            return val >= 128 or val in [0, 1, 2]
        elements = ["fire", "water", "lightning", "shadow"]

        while random.choice([True, False]):
            el = random.choice(elements)
            if getattr(self, el) != 4 and random.choice([True, False]):
                continue
            value = random.choice([0, 1, 2, 3, 4, 6, 8, 64,
                                   128, 129, 132, 143])
            if is_resistance(value) and not is_resistance(getattr(self, el)):
                for e in elements:
                    if e == el:
                        continue
                    if not is_resistance(getattr(self, e)):
                        break
                else:
                    continue
            setattr(self, el, value)


class DropObject(TableObject):
    flag = "t"
    mutate_attributes = {"xp": (0, 0xFFFE),
                         "gp": (0, 0xFFFE),
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
        if not self.monster.intershuffle_valid:
            return False
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

    @property
    def name(self):
        return self.monster.name

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


class ComboReqObject(TableObject):
    flag = 'k'

    @property
    def is_double(self):
        return not (1 <= self.reqs[2] <= 8)

    @property
    def is_triple(self):
        return 1 <= self.reqs[2] <= 8

    def mutate(self):
        if random.choice([True, False]):
            level = max([r for r in self.reqs if 1 <= r <= 8])
        else:
            level = random.randint(1, 4) + random.randint(0, 4)
        newreqs = [level, random.randint(1, level)]
        if self.is_triple:
            newreqs.append(random.randint(1, level))
        random.shuffle(newreqs)
        self.reqs[:len(newreqs)] = newreqs


def add_singing_mountain():
    locs = [l for l in LocationObject.every if
            l.mapindex in [0x82, 0x83, 0x84, 0x90] and l.music == 0x3c]
    for l in locs:
        l.music = 0x52


def randomize_battle_animations():
    pointers = [1, 2, 7, 0xa, 0xb, 0xc, 0xd]
    pointers = [p + 0xd4000 for p in pointers]
    short = [0, 3, 8, 0xa, 0xc]
    longg = [2, 4, 6]
    special = [0xd, 33]
    restricted = [6]
    f = open(get_outfile(), "r+b")
    for p in pointers:
        if random.choice([True, False]):
            continue
        f.seek(p)
        value = ord(f.read(1))
        container = [l for l in [short, longg] if value in l][0]
        notcontainer = [l for l in [short, longg] if l is not container][0]
        if random.randint(1, 100) == 100:
            # use special
            value = random.choice(special)
        elif random.choice([True, False]):
            # use same type
            value = random.choice(container)
        else:
            # use different type
            candidates = [v for v in notcontainer if v not in restricted]
            value = random.choice(candidates)
        f.seek(p)
        f.write(chr(value))
    f.close()


if __name__ == "__main__":
    print ("You are using the Chrono Trigger: Eternal Nightmare randomizer "
           "version %s." % VERSION)
    ALL_OBJECTS = [g for g in globals().values()
                   if isinstance(g, type) and issubclass(g, TableObject)
                   and g not in [TableObject]]
    run_interface(ALL_OBJECTS, snes=True)
    minmax = lambda x: (min(x), max(x))
    add_singing_mountain()
    randomize_battle_animations()
    clean_and_write(ALL_OBJECTS)
    randomize_rng(0xFE00)
    randomize_rng(0x3DBA61)
    rewrite_snes_meta("CT-R", VERSION, megabits=32)
    finish_interface()
