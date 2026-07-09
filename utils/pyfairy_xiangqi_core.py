import re
import sys
import time
from typing import Optional

INIT_FEN = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"

# 棋子基础价值（红方视角，正值）
PIECE_VALUE = {
    "k": 100000,
    "r": 900,
    "c": 450,
    "n": 400,
    "b": 200,
    "a": 200,
    "p": 100,
}

MATE = 1000000  # 将死分值，需大于任何常规局面分


def _pst(piece: str) -> list[list[int]]:
    """返回红方视角下某种棋子的位置价值表 table[x][y]（x=0 为红方底线）。"""
    table = [[0 for _ in range(9)] for _ in range(10)]
    if piece == "p":
        # 兵/卒：过河后价值提升，越靠近对方底线越高，居中略优
        for x in range(10):
            for y in range(9):
                if x >= 5:  # 已过河
                    base = 10 + (x - 4) * 6
                    center = 3 - abs(y - 4)
                    table[x][y] = base + max(center, 0) * 2
                else:
                    table[x][y] = 0
    elif piece == "n":  # 马：居中且向前更活跃
        for x in range(10):
            for y in range(9):
                table[x][y] = 4 - (abs(x - 5) + abs(y - 4)) // 2 + (2 if x >= 5 else 0)
    elif piece == "c":  # 炮：中路、向前略优
        for x in range(10):
            for y in range(9):
                table[x][y] = (2 if y == 4 else 0) + (1 if x >= 5 else 0)
    elif piece == "r":  # 车：过河及中路略优
        for x in range(10):
            for y in range(9):
                table[x][y] = (2 if x >= 5 else 0) + (1 if 3 <= y <= 5 else 0)
    return table


PST = {p: _pst(p) for p in ("p", "n", "c", "r")}


class SearchBoard:
    """轻量级棋盘，仅用于搜索。规则与 board.py 保持一致。"""

    def __init__(self, fen: str = INIT_FEN):
        self.board: list[list[Optional[str]]] = [
            [None for _ in range(9)] for _ in range(10)
        ]
        self.red_to_move = True
        self.from_fen(fen)

    def from_fen(self, fen: str):
        board_fen, moveside = fen.split(" ")[0], fen.split(" ")[1]
        self.board = [[None for _ in range(9)] for _ in range(10)]
        for i, line_fen in enumerate(board_fen.split("/")[::-1]):
            j = 0
            for ch in line_fen:
                if ch.isdigit():
                    j += int(ch)
                elif re.fullmatch(r"[kabnrcpKABNRCP]", ch):
                    self.board[i][j] = ch
                    j += 1
                else:
                    raise ValueError("Illegal character in fen string!")
        self.red_to_move = moveside != "b"

    # ---- 基础工具 ----
    @staticmethod
    def is_red(piece: str) -> bool:
        return piece.isupper()

    def is_own(self, piece: Optional[str]) -> bool:
        return piece is not None and self.is_red(piece) == self.red_to_move

    def is_enemy(self, piece: Optional[str]) -> bool:
        return piece is not None and self.is_red(piece) != self.red_to_move

    def find_king(self, red: bool) -> Optional[tuple[int, int]]:
        target = "K" if red else "k"
        for x in range(10):
            for y in range(9):
                if self.board[x][y] == target:
                    return (x, y)
        return None

    # ---- 走法生成（伪合法，即不检查走后是否被将军）----
    def gen_moves(self) -> list[tuple[int, int, int, int]]:
        moves = []
        for x in range(10):
            for y in range(9):
                piece = self.board[x][y]
                if piece is None or not self.is_own(piece):
                    continue
                moves.extend(self._piece_moves(x, y, piece))
        return moves

    def _piece_moves(self, x: int, y: int, piece: str):
        t = piece.lower()
        if t == "k":
            yield from self._king_moves(x, y)
        elif t == "a":
            yield from self._advisor_moves(x, y)
        elif t == "b":
            yield from self._bishop_moves(x, y)
        elif t == "n":
            yield from self._knight_moves(x, y)
        elif t == "r":
            yield from self._rook_moves(x, y)
        elif t == "c":
            yield from self._cannon_moves(x, y)
        elif t == "p":
            yield from self._pawn_moves(x, y)

    def _in_palace(self, x: int, y: int) -> bool:
        return (0 <= x <= 2 or 7 <= x <= 9) and 3 <= y <= 5

    def _king_moves(self, x, y):
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if self._in_palace(nx, ny) and not self.is_own(self.board[nx][ny]):
                yield (x, y, nx, ny)
        # 飞将：同列、中间无子时可直接“吃掉”对方将（照面规则）。
        # 生成该伪着法后，搜索里的吃王检测会将其视为必杀，从而正确处理照面。
        enemy_king = "k" if self.is_red(self.board[x][y]) else "K"
        for dxk in (1, -1):
            nx = x + dxk
            while 0 <= nx <= 9:
                p = self.board[nx][y]
                if p is not None:
                    if p == enemy_king:
                        yield (x, y, nx, y)
                    break
                nx += dxk

    def _advisor_moves(self, x, y):
        for dx, dy in ((1, 1), (-1, -1), (1, -1), (-1, 1)):
            nx, ny = x + dx, y + dy
            if self._in_palace(nx, ny) and not self.is_own(self.board[nx][ny]):
                yield (x, y, nx, ny)

    def _bishop_moves(self, x, y):
        for dx, dy in ((2, 2), (-2, -2), (2, -2), (-2, 2)):
            nx, ny = x + dx, y + dy
            if not (0 <= nx <= 9 and 0 <= ny <= 8):
                continue
            mx, my = (x + nx) // 2, (y + ny) // 2
            # 不能过河：象眼所在行不为 4/5（即两侧各守本方九宫外的半边）
            if mx in (4, 5):
                continue
            if self.board[mx][my] is not None:  # 塞象眼
                continue
            if not self.is_own(self.board[nx][ny]):
                yield (x, y, nx, ny)

    def _knight_moves(self, x, y):
        for dx, dy in (
            (2, 1), (-2, -1), (-2, 1), (2, -1),
            (1, 2), (-1, -2), (-1, 2), (1, -2),
        ):
            nx, ny = x + dx, y + dy
            if not (0 <= nx <= 9 and 0 <= ny <= 8):
                continue
            if abs(dx) == 1:
                mx, my = x, (y + ny) // 2  # 蹩马腿
            else:
                mx, my = (x + nx) // 2, y
            if self.board[mx][my] is not None:
                continue
            if not self.is_own(self.board[nx][ny]):
                yield (x, y, nx, ny)

    def _rook_moves(self, x, y):
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            while 0 <= nx <= 9 and 0 <= ny <= 8:
                target = self.board[nx][ny]
                if target is None:
                    yield (x, y, nx, ny)
                else:
                    if self.is_enemy(target):
                        yield (x, y, nx, ny)
                    break
                nx, ny = nx + dx, ny + dy

    def _cannon_moves(self, x, y):
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            # 未越子前正常移动
            while 0 <= nx <= 9 and 0 <= ny <= 8 and self.board[nx][ny] is None:
                yield (x, y, nx, ny)
                nx, ny = nx + dx, ny + dy
            # 遇到炮架，跳过它继续找第一个棋子
            nx, ny = nx + dx, ny + dy
            while 0 <= nx <= 9 and 0 <= ny <= 8:
                target = self.board[nx][ny]
                if target is not None:
                    if self.is_enemy(target):
                        yield (x, y, nx, ny)
                    break
                nx, ny = nx + dx, ny + dy

    def _pawn_moves(self, x, y):
        red = self.is_red(self.board[x][y])
        if red:
            steps = [(1, 0)]
            if x >= 5:  # 过河
                steps += [(0, 1), (0, -1)]
        else:
            steps = [(-1, 0)]
            if x <= 4:  # 过河
                steps += [(0, 1), (0, -1)]
        for dx, dy in steps:
            nx, ny = x + dx, y + dy
            if 0 <= nx <= 9 and 0 <= ny <= 8 and not self.is_own(self.board[nx][ny]):
                yield (x, y, nx, ny)

    # ---- 局面合法性 ----
    def kings_face(self) -> bool:
        """将帅是否照面（同列且中间无子）。"""
        rk = self.find_king(True)
        bk = self.find_king(False)
        if not rk or not bk or rk[1] != bk[1]:
            return False
        y = rk[1]
        lo, hi = sorted((rk[0], bk[0]))
        return all(self.board[x][y] is None for x in range(lo + 1, hi))

    def in_check(self, red: bool) -> bool:
        """判断 red 方是否被将军（其王是否被对方攻击，或将帅照面）。"""
        if self.kings_face():
            return True
        king = self.find_king(red)
        if king is None:
            return True  # 王不存在，视作最坏
        kx, ky = king
        enemy_red = not red

        # 车/将（沿直线，中间无子）
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = kx + dx, ky + dy
            while 0 <= nx <= 9 and 0 <= ny <= 8:
                p = self.board[nx][ny]
                if p is not None:
                    if self.is_red(p) == enemy_red and p.lower() == "r":
                        return True
                    break
                nx, ny = nx + dx, ny + dy

        # 炮（隔一子攻击）
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = kx + dx, ky + dy
            screen = False
            while 0 <= nx <= 9 and 0 <= ny <= 8:
                p = self.board[nx][ny]
                if p is not None:
                    if not screen:
                        screen = True
                    else:
                        if self.is_red(p) == enemy_red and p.lower() == "c":
                            return True
                        break
                nx, ny = nx + dx, ny + dy

        # 马（考虑蹩马腿；从王的角度反推马的位置）
        for mx, my, bx, by in (
            (kx + 2, ky + 1, kx + 1, ky), (kx + 2, ky - 1, kx + 1, ky),
            (kx - 2, ky + 1, kx - 1, ky), (kx - 2, ky - 1, kx - 1, ky),
            (kx + 1, ky + 2, kx, ky + 1), (kx - 1, ky + 2, kx, ky + 1),
            (kx + 1, ky - 2, kx, ky - 1), (kx - 1, ky - 2, kx, ky - 1),
        ):
            if 0 <= mx <= 9 and 0 <= my <= 8:
                p = self.board[mx][my]
                if p is not None and self.is_red(p) == enemy_red and p.lower() == "n":
                    if self.board[bx][by] is None:  # 马腿未被塞
                        return True

        # 兵/卒
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = kx + dx, ky + dy
            if 0 <= nx <= 9 and 0 <= ny <= 8:
                p = self.board[nx][ny]
                if p is not None and self.is_red(p) == enemy_red and p.lower() == "p":
                    if enemy_red:  # 红兵向 +x 前进，攻击其上方；过河后可横攻
                        if dx == -1 or (dy != 0 and nx >= 5):
                            return True
                    else:  # 黑卒向 -x 前进
                        if dx == 1 or (dy != 0 and nx <= 4):
                            return True
        return False

    # ---- 走子/撤销 ----
    def do_move(self, move) -> Optional[str]:
        x, y, nx, ny = move
        captured = self.board[nx][ny]
        self.board[nx][ny] = self.board[x][y]
        self.board[x][y] = None
        self.red_to_move = not self.red_to_move
        return captured

    def undo_move(self, move, captured: Optional[str]):
        x, y, nx, ny = move
        self.board[x][y] = self.board[nx][ny]
        self.board[nx][ny] = captured
        self.red_to_move = not self.red_to_move

    def legal_moves(self) -> list[tuple[int, int, int, int]]:
        """完全合法的走法（走后本方不被将军、将帅不照面）。"""
        result = []
        mover_red = self.red_to_move
        for move in self.gen_moves():
            captured = self.do_move(move)
            if not self.in_check(mover_red):
                result.append(move)
            self.undo_move(move, captured)
        return result

    # ---- 评估 ----
    def evaluate(self) -> int:
        """返回当前行动方视角的分值。"""
        score = 0
        for x in range(10):
            for y in range(9):
                p = self.board[x][y]
                if p is None:
                    continue
                t = p.lower()
                val = PIECE_VALUE[t]
                if t in PST:
                    if self.is_red(p):
                        val += PST[t][x][y]
                    else:
                        val += PST[t][9 - x][y]
                score += val if self.is_red(p) else -val
        return score if self.red_to_move else -score


class TimeUp(Exception):
    pass


class Engine:
    def __init__(self):
        self.board = SearchBoard()
        self.deadline: Optional[float] = None
        self.nodes = 0

    def set_position(self, tokens: list[str]):
        idx = 0
        if tokens and tokens[0] == "fen":
            # fen 由 6 个字段组成
            fen = " ".join(tokens[1:7])
            self.board = SearchBoard(fen)
            idx = 7
        elif tokens and tokens[0] == "startpos":
            self.board = SearchBoard(INIT_FEN)
            idx = 1
        else:
            self.board = SearchBoard(INIT_FEN)
        if idx < len(tokens) and tokens[idx] == "moves":
            for m in tokens[idx + 1:]:
                self.board.do_move(self._parse_ucci(m))

    @staticmethod
    def _parse_ucci(m: str) -> tuple[int, int, int, int]:
        y1 = ord(m[0]) - ord("a")
        x1 = int(m[1])
        y2 = ord(m[2]) - ord("a")
        x2 = int(m[3])
        return (x1, y1, x2, y2)

    @staticmethod
    def _to_ucci(move) -> str:
        x, y, nx, ny = move
        return f"{chr(ord('a') + y)}{x}{chr(ord('a') + ny)}{nx}"

    def _move_value(self, move) -> int:
        """走法排序用的启发值：优先吃大子。"""
        _, _, nx, ny = move
        target = self.board.board[nx][ny]
        return PIECE_VALUE[target.lower()] if target else 0

    def _quiesce(self, alpha: int, beta: int, qdepth: int = 0) -> int:
        """静态搜索：在叶子节点继续解算吃子，直到局面"安静"，
        消除固定深度带来的水平线效应（偶数层吃亏/奇数层占便宜的振荡）。
        qdepth: 静态搜索深度（最大 6 层，超出则仅评估）。
        Delta pruning: 跳过吃子价值+容差无法提升 alpha 的着法，避免深入无望的兑子。
        """
        self.nodes += 1
        if self.nodes % 4096 == 0 and self.deadline and time.monotonic() > self.deadline:
            raise TimeUp

        stand_pat = self.board.evaluate()
        if stand_pat >= beta:
            return beta
        if stand_pat > alpha:
            alpha = stand_pat

        if qdepth >= 6:
            return alpha

        DELTA_MARGIN = 200  # 容差：允许局面进一步变化的最大分值

        captures = [m for m in self.board.gen_moves()
                    if self.board.board[m[2]][m[3]] is not None]
        captures.sort(key=self._move_value, reverse=True)
        for move in captures:
            target = self.board.board[move[2]][move[3]]
            if target.lower() == "k":
                return MATE  # 能吃将
            gain = PIECE_VALUE[target.lower()]
            # Delta pruning：即便拿到这颗子 + 容差，也无法超越 alpha，跳过
            if stand_pat + gain + DELTA_MARGIN < alpha:
                continue
            captured = self.board.do_move(move)
            score = -self._quiesce(-beta, -alpha, qdepth + 1)
            self.board.undo_move(move, captured)
            if score >= beta:
                return beta
            if score > alpha:
                alpha = score
        return alpha

    def _negamax(self, depth: int, alpha: int, beta: int) -> int:
        self.nodes += 1
        if self.nodes % 4096 == 0 and self.deadline and time.monotonic() > self.deadline:
            raise TimeUp

        if depth <= 0:
            return self._quiesce(alpha, beta)

        # 伪合法走法 + 吃王检测：不在每个节点做代价高昂的合法性过滤，
        # 而是允许送将，交由对方“吃掉将”来反驳（将值 100000）。这样
        # 走后被将/照面的走法自然会被剪掉，速度提升一个数量级。
        moves = self.board.gen_moves()
        moves.sort(key=self._move_value, reverse=True)
        best = -MATE - 1
        any_move = False
        for move in moves:
            target = self.board.board[move[2]][move[3]]
            if target is not None and target.lower() == "k":
                # 能直接吃掉对方将 = 必杀，越靠近根（depth 越大）越好
                return MATE - (100 - depth)
            any_move = True
            captured = self.board.do_move(move)
            score = -self._negamax(depth - 1, -beta, -alpha)
            self.board.undo_move(move, captured)
            if score > best:
                best = score
            if best > alpha:
                alpha = best
            if alpha >= beta:
                break
        if not any_move:
            # 困毙：无子可动，判负
            return -MATE + (100 - depth)
        return best

    def search(self, max_time_ms: int, max_depth: int) -> str:
        moves = self.board.legal_moves()
        if not moves:
            return "0000"
        if len(moves) == 1:
            return self._to_ucci(moves[0])

        self.deadline = time.monotonic() + max_time_ms / 1000.0
        best_move = moves[0]

        # 迭代加深：depth 1 必定完成，之后受时间约束
        for depth in range(1, max_depth + 1):
            self.nodes = 0
            best_score = -MATE - 1
            current_best = best_move
            # 把上一轮最佳着法排到最前，提升剪枝效果
            moves.sort(key=lambda m: (m == best_move, self._move_value(m)), reverse=True)
            try:
                alpha, beta = -MATE - 1, MATE + 1
                for move in moves:
                    captured = self.board.do_move(move)
                    score = -self._negamax(depth - 1, -beta, -alpha)
                    self.board.undo_move(move, captured)
                    if score > best_score:
                        best_score = score
                        current_best = move
                    if score > alpha:
                        alpha = score
                best_move = current_best
            except TimeUp:
                break
            # 已找到必胜杀棋，无需继续加深
            if best_score >= MATE - 1000:
                break
            if depth > 1 and self.deadline and time.monotonic() > self.deadline:
                break
        return self._to_ucci(best_move)


def main():
    engine = Engine()
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        cmd = parts[0]

        if cmd == "ucci":
            print("id name PyFairyXiangqi")
            print("id author AiriCore")
            print("ucciok")
            sys.stdout.flush()
        elif cmd == "isready":
            print("readyok")
            sys.stdout.flush()
        elif cmd == "position":
            try:
                engine.set_position(parts[1:])
            except Exception as e:  # 位置解析失败不应让引擎崩溃
                print(f"info string position error: {e}")
                sys.stdout.flush()
        elif cmd == "go":
            max_time, max_depth = 1000, 12
            i = 1
            while i < len(parts):
                if parts[i] == "time" and i + 1 < len(parts):
                    max_time = int(parts[i + 1])
                    i += 2
                elif parts[i] == "depth" and i + 1 < len(parts):
                    max_depth = int(parts[i + 1])
                    i += 2
                else:
                    i += 1
            best = engine.search(max_time, max_depth)
            print(f"bestmove {best}")
            sys.stdout.flush()
        elif cmd in ("stop",):
            continue
        elif cmd in ("quit", "exit"):
            break


if __name__ == "__main__":
    main()
