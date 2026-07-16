import re
import sys
import time
from typing import Optional

INIT_FEN = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"

PIECE_VALUE = {
    "k": 100000,
    "r": 900,
    "c": 450,
    "n": 400,
    "b": 200,
    "a": 200,
    "p": 100,
}

MATE = 1000000


def _pst(piece: str) -> list[list[int]]:
    table = [[0 for _ in range(9)] for _ in range(10)]
    if piece == "p":
        for x in range(10):
            for y in range(9):
                if x >= 5:
                    base = 10 + (x - 4) * 6
                    center = 3 - abs(y - 4)
                    table[x][y] = base + max(center, 0) * 2
                else:
                    table[x][y] = 0
    elif piece == "n":
        for x in range(10):
            for y in range(9):
                table[x][y] = 4 - (abs(x - 5) + abs(y - 4)) // 2 + (2 if x >= 5 else 0)
    elif piece == "c":
        for x in range(10):
            for y in range(9):
                table[x][y] = (2 if y == 4 else 0) + (1 if x >= 5 else 0)
    elif piece == "r":
        for x in range(10):
            for y in range(9):
                table[x][y] = (2 if x >= 5 else 0) + (1 if 3 <= y <= 5 else 0)
    return table


PST = {p: _pst(p) for p in ("p", "n", "c", "r")}


class SearchBoard:

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
            if mx in (4, 5):
                continue
            if self.board[mx][my] is not None:
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
                mx, my = x, (y + ny) // 2
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
            while 0 <= nx <= 9 and 0 <= ny <= 8 and self.board[nx][ny] is None:
                yield (x, y, nx, ny)
                nx, ny = nx + dx, ny + dy
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
            if x >= 5:
                steps += [(0, 1), (0, -1)]
        else:
            steps = [(-1, 0)]
            if x <= 4:
                steps += [(0, 1), (0, -1)]
        for dx, dy in steps:
            nx, ny = x + dx, y + dy
            if 0 <= nx <= 9 and 0 <= ny <= 8 and not self.is_own(self.board[nx][ny]):
                yield (x, y, nx, ny)

    def kings_face(self) -> bool:
        rk = self.find_king(True)
        bk = self.find_king(False)
        if not rk or not bk or rk[1] != bk[1]:
            return False
        y = rk[1]
        lo, hi = sorted((rk[0], bk[0]))
        return all(self.board[x][y] is None for x in range(lo + 1, hi))

    def in_check(self, red: bool) -> bool:
        if self.kings_face():
            return True
        king = self.find_king(red)
        if king is None:
            return True
        kx, ky = king
        enemy_red = not red

        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = kx + dx, ky + dy
            while 0 <= nx <= 9 and 0 <= ny <= 8:
                p = self.board[nx][ny]
                if p is not None:
                    if self.is_red(p) == enemy_red and p.lower() == "r":
                        return True
                    break
                nx, ny = nx + dx, ny + dy

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

        for mx, my, bx, by in (
            (kx + 2, ky + 1, kx + 1, ky), (kx + 2, ky - 1, kx + 1, ky),
            (kx - 2, ky + 1, kx - 1, ky), (kx - 2, ky - 1, kx - 1, ky),
            (kx + 1, ky + 2, kx, ky + 1), (kx - 1, ky + 2, kx, ky + 1),
            (kx + 1, ky - 2, kx, ky - 1), (kx - 1, ky - 2, kx, ky - 1),
        ):
            if 0 <= mx <= 9 and 0 <= my <= 8:
                p = self.board[mx][my]
                if p is not None and self.is_red(p) == enemy_red and p.lower() == "n":
                    if self.board[bx][by] is None:
                        return True

        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = kx + dx, ky + dy
            if 0 <= nx <= 9 and 0 <= ny <= 8:
                p = self.board[nx][ny]
                if p is not None and self.is_red(p) == enemy_red and p.lower() == "p":
                    if enemy_red:
                        if dx == -1 or (dy != 0 and nx >= 5):
                            return True
                    else:
                        if dx == 1 or (dy != 0 and nx <= 4):
                            return True
        return False

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
        result = []
        mover_red = self.red_to_move
        for move in self.gen_moves():
            captured = self.do_move(move)
            if not self.in_check(mover_red):
                result.append(move)
            self.undo_move(move, captured)
        return result

    def evaluate(self) -> int:
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
        _, _, nx, ny = move
        target = self.board.board[nx][ny]
        return PIECE_VALUE[target.lower()] if target else 0

    def _quiesce(self, alpha: int, beta: int, qdepth: int = 0) -> int:
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

        DELTA_MARGIN = 200

        captures = [m for m in self.board.gen_moves()
                    if self.board.board[m[2]][m[3]] is not None]
        captures.sort(key=self._move_value, reverse=True)
        for move in captures:
            target = self.board.board[move[2]][move[3]]
            if target.lower() == "k":
                return MATE
            gain = PIECE_VALUE[target.lower()]
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

        moves = self.board.gen_moves()
        moves.sort(key=self._move_value, reverse=True)
        best = -MATE - 1
        any_move = False
        for move in moves:
            target = self.board.board[move[2]][move[3]]
            if target is not None and target.lower() == "k":
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

        for depth in range(1, max_depth + 1):
            self.nodes = 0
            best_score = -MATE - 1
            current_best = best_move
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
            except Exception as e:
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
