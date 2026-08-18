def soup_number_to_id(soup_number, soup_count):
    if isinstance(soup_number, int) and 1 <= soup_number <= soup_count:
        return soup_number - 1
    return None


def soup_id_to_number(soup_id):
    return soup_id + 1
