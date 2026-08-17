import json


TIP_KEYS = frozenset({"fact", "direction", "breakthroughs", "weight"})


def _label(soup_id):
    return f"题目 {soup_id}" if soup_id is not None else "题目"


def _nonempty_text(value):
    return isinstance(value, str) and bool(value.strip())


def validate_tips(tips, soup_id=None):
    label = _label(soup_id)
    if not isinstance(tips, list):
        raise ValueError(f"{label}的 tips 字段必须是列表")
    if not 3 <= len(tips) <= 5:
        raise ValueError(f"{label}的 tips 字段必须包含 3 到 5 项")

    facts = set()
    total_weight = 0
    for index, tip in enumerate(tips, 1):
        item_label = f"{label}的 tips 第 {index} 项"
        if not isinstance(tip, dict):
            raise ValueError(f"{item_label}必须是字典")
        if set(tip) != TIP_KEYS:
            raise ValueError(f"{item_label}的字段必须恰好为 fact、direction、breakthroughs、weight")

        fact = tip["fact"]
        if not _nonempty_text(fact):
            raise ValueError(f"{item_label}的 fact 字段必须是非空字符串")
        stripped_fact = fact.strip()
        if stripped_fact in facts:
            raise ValueError(f"{item_label}的 fact 字段不能重复")
        facts.add(stripped_fact)

        if not _nonempty_text(tip["direction"]):
            raise ValueError(f"{item_label}的 direction 字段必须是非空字符串")

        breakthroughs = tip["breakthroughs"]
        if not isinstance(breakthroughs, list) or not 2 <= len(breakthroughs) <= 5:
            raise ValueError(f"{item_label}的 breakthroughs 字段必须是包含 2 到 5 项的列表")
        stripped_breakthroughs = []
        for breakthrough_index, breakthrough in enumerate(breakthroughs, 1):
            if not _nonempty_text(breakthrough):
                raise ValueError(
                    f"{item_label}的 breakthroughs 字段第 {breakthrough_index} 项必须是非空字符串"
                )
            stripped_breakthroughs.append(breakthrough.strip())
        if len(set(stripped_breakthroughs)) != len(stripped_breakthroughs):
            raise ValueError(f"{item_label}的 breakthroughs 字段不能包含重复项")

        weight = tip["weight"]
        if isinstance(weight, bool) or not isinstance(weight, int) or weight <= 0:
            raise ValueError(f"{item_label}的 weight 字段必须是正整数")
        total_weight += weight

    if total_weight != 100:
        raise ValueError(f"{label}的 tips 字段 weight 总和必须为 100")
    return tips


def validate_turtle_soup_bank(bank):
    if not isinstance(bank, list):
        raise ValueError("题库必须是列表")
    for index, soup in enumerate(bank):
        label = _label(index)
        if not isinstance(soup, dict):
            raise ValueError(f"{label}必须是字典")
        if not _nonempty_text(soup.get("story")):
            raise ValueError(f"{label}的 story 字段必须是非空字符串")
        if not _nonempty_text(soup.get("truth")):
            raise ValueError(f"{label}的 truth 字段必须是非空字符串")
        validate_tips(soup.get("tips"), index)
    return bank


def serialize_tips(tips):
    validate_tips(tips)
    return json.dumps(tips, ensure_ascii=False, separators=(",", ":"))
