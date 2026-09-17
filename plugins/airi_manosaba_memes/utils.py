import struct
from pathlib import Path

from .models import Character, Statement

CHARACTER_NAME_MAP = {
    "梅露露": Character.MERURU,
    "诺亚": Character.NOAH,
    "汉娜": Character.HANNA,
    "奈叶香": Character.NANOKA,
    "亚里沙": Character.ALISA,
    "米莉亚": Character.MIRIA,
    "雪莉": Character.SHERRY,
    "艾玛": Character.EMA,
    "玛格": Character.MARGO,
    "安安": Character.ANAN,
    "可可": Character.COCO,
    "希罗": Character.HIRO,
    "蕾雅": Character.LEIA,
    "雪": Character.YUKI,
    "典狱长": Character.WARDEN,
    "看守": Character.JAILER,
}
CHARACTER_NAMES = tuple(CHARACTER_NAME_MAP)
CREATURE_BASE_CHARACTERS = {
    character: Character(character.value.removeprefix("Creature"))
    for character in Character if character.value.startswith("Creature")
}
CHARACTER_NAME_MAP.update({
    "黑化" + name: creature
    for name, base in tuple(CHARACTER_NAME_MAP.items())
    for creature, original in CREATURE_BASE_CHARACTERS.items() if base == original
})
CHARACTER_DISPLAY_NAMES = {
    character.value: name for name, character in CHARACTER_NAME_MAP.items()
}
CHARACTER_NAME_MAP.update({
    "樱羽艾玛": Character.EMA,
    "二阶堂希罗": Character.HIRO,
    "夏目安安": Character.ANAN,
    "城崎诺亚": Character.NOAH,
    "莲见蕾雅": Character.LEIA,
    "佐伯米莉亚": Character.MIRIA,
    "宝生玛格": Character.MARGO,
    "黑部奈叶香": Character.NANOKA,
    "紫藤亚里沙": Character.ALISA,
    "橘雪莉": Character.SHERRY,
    "远野汉娜": Character.HANNA,
    "泽渡可可": Character.COCO,
    "冰上梅露露": Character.MERURU,
    "月代雪": Character.YUKI,
    "Yuki": Character.YUKI,
    "Warden": Character.WARDEN,
    "Jailer": Character.JAILER,
})
for creature, base in CREATURE_BASE_CHARACTERS.items():
    CHARACTER_NAME_MAP[creature.value] = creature
    for name, character in tuple(CHARACTER_NAME_MAP.items()):
        if character == base:
            for alias in ("黑化" + name, "魔女化" + name, name + "（黑化）"):
                CHARACTER_NAME_MAP[alias] = creature


def get_png_size(file_path: Path) -> tuple[int, int]:

    with file_path.open("rb") as file:
        file.seek(16)
        return struct.unpack(">II", file.read(8))


def get_magic_statement(text: str) -> Statement:


    mapping = {
        "梅露露": Statement.MAGIC_CHIYUSAISEI,
        "诺亚": Statement.MAGIC_EKITAISOUSA,
        "汉娜": Statement.MAGIC_FUYUU,
        "奈叶香": Statement.MAGIC_GENSHI,
        "亚里沙": Statement.MAGIC_HAKKA,
        "米莉亚": Statement.MAGIC_IREKAWARI,
        "雪莉": Statement.MAGIC_KAIRIKI,
        "艾玛": Statement.MAGIC_MAJOGOROSHI,
        "玛格": Statement.MAGIC_MONOMANE,
        "安安": Statement.MAGIC_SENNOU,
        "可可": Statement.MAGIC_SENRIGAN,
        "希罗": Statement.MAGIC_SHINIMODORI,
        "蕾雅": Statement.MAGIC_SHISENYUUDOU,
        "雪": Statement.MAGIC_SHISENYUUDOU,
    }
    character = get_character(text)
    character = CREATURE_BASE_CHARACTERS.get(character, character)
    return mapping[CHARACTER_DISPLAY_NAMES[character.value]]


def get_statement(statement: str, arg: str | None = None) -> Statement:


    match statement:
        case "赞同":
            return Statement.AGREEMENT
        case "疑问":
            return Statement.DOUBT
        case "伪证":
            return Statement.PURJURY
        case "反驳":
            return Statement.REFUTATION
        case "魔法":
            return get_magic_statement(arg)
        case _:
            assert False, "Invalid statement type"


def get_character(character: str) -> Character:


    return CHARACTER_NAME_MAP[character]
