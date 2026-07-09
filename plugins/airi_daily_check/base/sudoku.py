import random

LEVEL_HOLES = {1: (20, 30), 2: (30, 40), 3: (40, 55)}

_FULL_MASK = 0x3FE


def _box(r, c):
    return (r // 3) * 3 + c // 3


def _generate_full():
    grid = [0] * 81
    rows = [0] * 9
    cols = [0] * 9
    boxes = [0] * 9

    def fill(idx):
        if idx == 81:
            return True
        r, c = divmod(idx, 9)
        b = _box(r, c)
        used = rows[r] | cols[c] | boxes[b]
        cand = [v for v in range(1, 10) if not (used & (1 << v))]
        random.shuffle(cand)
        for v in cand:
            bit = 1 << v
            grid[idx] = v
            rows[r] |= bit
            cols[c] |= bit
            boxes[b] |= bit
            if fill(idx + 1):
                return True
            grid[idx] = 0
            rows[r] ^= bit
            cols[c] ^= bit
            boxes[b] ^= bit
        return False

    fill(0)
    return grid


def _solution_count(grid, limit=2):
    rows = [0] * 9
    cols = [0] * 9
    boxes = [0] * 9
    empties = []
    for idx in range(81):
        v = grid[idx]
        r, c = divmod(idx, 9)
        if v:
            bit = 1 << v
            rows[r] |= bit
            cols[c] |= bit
            boxes[_box(r, c)] |= bit
        else:
            empties.append(idx)

    g = grid[:]
    count = 0

    def dfs():
        nonlocal count
        best = -1
        best_mask = 0
        best_cnt = 10
        for idx in empties:
            if g[idx]:
                continue
            r, c = divmod(idx, 9)
            avail = (~(rows[r] | cols[c] | boxes[_box(r, c)])) & _FULL_MASK
            cnt = bin(avail).count('1')
            if cnt == 0:
                return
            if cnt < best_cnt:
                best_cnt = cnt
                best = idx
                best_mask = avail
                if cnt == 1:
                    break
        if best == -1:
            count += 1
            return
        r, c = divmod(best, 9)
        b = _box(r, c)
        mask = best_mask
        while mask:
            low = mask & (-mask)
            g[best] = low.bit_length() - 1
            rows[r] |= low
            cols[c] |= low
            boxes[b] |= low
            dfs()
            g[best] = 0
            rows[r] ^= low
            cols[c] ^= low
            boxes[b] ^= low
            mask ^= low
            if count >= limit:
                return

    dfs()
    return count


def generate_puzzle(level):
    full = _generate_full()
    lo, hi = LEVEL_HOLES.get(level, (20, 55))
    target = random.randint(lo, hi)

    puzzle = full[:]
    cells = list(range(81))
    random.shuffle(cells)
    holes = 0
    for idx in cells:
        if holes >= target:
            break
        saved = puzzle[idx]
        puzzle[idx] = 0
        if _solution_count(puzzle, 2) == 1:
            holes += 1
        else:
            puzzle[idx] = saved

    answer = ''.join(str(full[r * 10]) for r in range(9))
    return puzzle, answer


def generate_daily():
    puzzles = [None, None, None, None]
    answers = [0, '', '', '']
    for i in range(1, 4):
        puzzles[i], answers[i] = generate_puzzle(i)
    return puzzles, answers
