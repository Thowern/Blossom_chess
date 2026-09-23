import random as _random
import numpy as np

# riga della scacchiera (0 = 8a traversa) -> indice bitboard della traversa (0 = 1a traversa)
converter = {7: 0, 6: 1, 5: 2, 4: 3, 3: 4, 2: 5, 1: 6, 0: 7}

PIECE_NAMES = ['wp', 'wB', 'wN', 'wR', 'wQ', 'wK', 'bp', 'bB', 'bN', 'bR', 'bQ', 'bK']
PROMOTION_PIECES = ('Q', 'R', 'B', 'N')

# ----------------------------------------------------------------------
# Codici pezzo interni:  vuoto = 0
#   bianco: 1 p, 2 N, 3 B, 4 R, 5 Q, 6 K      nero: gli stessi + 8
# Le case sono indici 0..63 = riga * 8 + colonna (riga 0 = 8a traversa).
# Mossa codificata in un intero:  da | (a << 6) | (promozione << 12)
#   promozione: 0 nessuna, 2 = N, 3 = B, 4 = R, 5 = Q
# ----------------------------------------------------------------------
NAME = ['--', 'wp', 'wN', 'wB', 'wR', 'wQ', 'wK', '--',
        '--', 'bp', 'bN', 'bB', 'bR', 'bQ', 'bK', '--']
NAME_TO_CODE = {n: i for i, n in enumerate(NAME) if n != '--'}
PROMO_LETTER = {2: 'N', 3: 'B', 4: 'R', 5: 'Q'}
PROMO_CODE = {'N': 2, 'B': 3, 'R': 4, 'Q': 5}
PROMO_ORDER = (5, 4, 3, 2)

# ------------------------- tabelle precalcolate -------------------------
BIT = [1 << s for s in range(64)]
FULL = (1 << 64) - 1
ROW = [s >> 3 for s in range(64)]
COL = [s & 7 for s in range(64)]


def _inside(r, c):
    return 0 <= r < 8 and 0 <= c < 8


KNIGHT_T = []
KING_T = []
PAWN_ATT = [[], []]
PUSH = [[], []]
DBL = [[], []]
PROMO_SQ = [[], []]
RAY_R = []
RAY_B = []
RAY_Q = []

for _s in range(64):
    _r, _c = _s >> 3, _s & 7
    KNIGHT_T.append(tuple(
        (_r + dr) * 8 + _c + dc
        for dr, dc in ((-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1))
        if _inside(_r + dr, _c + dc)))
    KING_T.append(tuple(
        (_r + dr) * 8 + _c + dc
        for dr, dc in ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
        if _inside(_r + dr, _c + dc)))
    for _col, _dr in ((0, -1), (1, 1)):
        PAWN_ATT[_col].append(tuple(
            (_r + _dr) * 8 + _c + dc for dc in (-1, 1) if _inside(_r + _dr, _c + dc)))
        PUSH[_col].append((_r + _dr) * 8 + _c if _inside(_r + _dr, _c) else -1)
        _start = 6 if _col == 0 else 1
        DBL[_col].append((_r + 2 * _dr) * 8 + _c if _r == _start else -1)
        PROMO_SQ[_col].append(_r == (0 if _col == 0 else 7))

    def _ray(dr, dc, r=_r, c=_c):
        out = []
        r += dr
        c += dc
        while _inside(r, c):
            out.append(r * 8 + c)
            r += dr
            c += dc
        return tuple(out)

    rr = tuple(_ray(dr, dc) for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)))
    bb = tuple(_ray(dr, dc) for dr, dc in ((-1, -1), (-1, 1), (1, -1), (1, 1)))
    RAY_R.append(tuple(x for x in rr if x))
    RAY_B.append(tuple(x for x in bb if x))
    RAY_Q.append(RAY_R[-1] + RAY_B[-1])

SLIDE = [None, None, None, RAY_B, RAY_R, RAY_Q]   # indice = tipo pezzo (3 B, 4 R, 5 Q)

# diritti di arrocco persi quando una mossa parte da / arriva su una casa
# bit: 1 = bianco lato re, 2 = bianco lato donna, 4 = nero lato re, 8 = nero lato donna
CM = [15] * 64
CM[63] = 14
CM[56] = 13
CM[60] = 12
CM[7] = 11
CM[0] = 7
CM[4] = 3

# Zobrist
_rng = _random.Random(0xC0FFEE)
ZP = [[_rng.getrandbits(64) for _ in range(64)] for _ in range(16)]
ZC = [_rng.getrandbits(64) for _ in range(16)]
ZEP = [_rng.getrandbits(64) for _ in range(8)]
ZSIDE = _rng.getrandbits(64)


class Board:
    """
    Scacchiera ottimizzata con generatore di mosse legali.

    Interfaccia identica all'originale:
      - self.board[riga][colonna], riga 0 = 8a traversa (nero), riga 7 = 1a traversa (bianco)
      - mosse [[riga_start, col_start], [riga_end, col_end]]
      - bitboard (indice = converter[riga] * 8 + colonna) come attributi
        (wp_bitboard, ..., piece_bitboards, occupate_squares_bitboards, ...)
      - Board(), Move(start, end, board), make_move, undo_move, get_legal_valid_moves,
        in_check, king_square, is_checkmate, is_stalemate, is_draw, get_pgn

    Novità: get_legal_valid_moves(include_promotions=True), find_move(start, end, promotion),
    Board.from_fen(fen), Move(..., promotion='Q'|'R'|'B'|'N').
    """

    def __init__(self):
        self.sq = [12, 10, 11, 13, 14, 11, 10, 12,
                   9, 9, 9, 9, 9, 9, 9, 9,
                   0, 0, 0, 0, 0, 0, 0, 0,
                   0, 0, 0, 0, 0, 0, 0, 0,
                   0, 0, 0, 0, 0, 0, 0, 0,
                   0, 0, 0, 0, 0, 0, 0, 0,
                   1, 1, 1, 1, 1, 1, 1, 1,
                   4, 2, 3, 5, 6, 3, 2, 4]
        self.turn = 0                 # 0 = bianco, 1 = nero
        self.castle = 15
        self.ep = -1
        self.halfmove = 0
        self.move_log = []
        self._stack = []
        self._init_derived()

    # ------------------------------------------------------------------
    # inizializzazione stato derivato
    # ------------------------------------------------------------------
    def _init_derived(self):
        sq = self.sq
        self._start = (list(sq), self.turn, self.castle, self.ep, self.halfmove)
        self.pcs = [set(), set()]
        self.ksq = [60, 4]
        for s in range(64):
            p = sq[s]
            if p:
                self.pcs[p >> 3].add(s)
                if p & 7 == 6:
                    self.ksq[p >> 3] = s
        self._init_np()
        self._legal = None
        self._chk = None
        self._occ = None
        self._eph = self._ep_hash()
        self.hash = self._calc_hash()
        self.hist = [self.hash]

    def _init_np(self):
        """Crea scacchiera numpy e bitboard (attributi) e li riempie dalla lista interna."""
        self._bbl = [None] * 15
        self.piece_bitboards = {}
        for code in (1, 2, 3, 4, 5, 6, 9, 10, 11, 12, 13, 14):
            arr = np.zeros(64, dtype=bool)
            self._bbl[code] = arr
            self.piece_bitboards[NAME[code]] = arr
            setattr(self, NAME[code] + '_bitboard', arr)
        self.board = np.full((8, 8), '--', dtype='<U2')
        self._flat = self.board.reshape(64)
        self._rebuild_np()

    def _ep_hash(self):
        """Contributo dell'en passant all'hash: solo se un pedone può davvero catturare."""
        ep = self.ep
        if ep < 0:
            return 0
        us = self.turn
        mine = (us << 3) | 1
        for s in PAWN_ATT[us ^ 1][ep]:
            if self.sq[s] == mine:
                return ZEP[ep & 7]
        return 0

    def _calc_hash(self):
        h = 0
        for s in range(64):
            p = self.sq[s]
            if p:
                h ^= ZP[p][s]
        h ^= ZC[self.castle]
        if self.turn:
            h ^= ZSIDE
        h ^= self._eph
        return h

    def _rebuild_np(self):
        flat = self._flat
        for arr in self._bbl:
            if arr is not None:
                arr[:] = False
        sq = self.sq
        for s in range(64):
            p = sq[s]
            flat[s] = NAME[p]
            if p:
                self._bbl[p][s ^ 56] = True

    @classmethod
    def from_fen(cls, fen):
        self = cls()
        parts = fen.split()
        sq = [0] * 64
        for r, row in enumerate(parts[0].split('/')):
            c = 0
            for ch in row:
                if ch.isdigit():
                    c += int(ch)
                else:
                    color = 'w' if ch.isupper() else 'b'
                    t = 'p' if ch.lower() == 'p' else ch.upper()
                    sq[r * 8 + c] = NAME_TO_CODE[color + t]
                    c += 1
        self.sq = sq
        self.turn = 0 if (len(parts) < 2 or parts[1] == 'w') else 1
        castling = parts[2] if len(parts) > 2 else '-'
        self.castle = (1 if 'K' in castling else 0) | (2 if 'Q' in castling else 0) | \
                      (4 if 'k' in castling else 0) | (8 if 'q' in castling else 0)
        self.ep = -1
        if len(parts) > 3 and parts[3] != '-':
            self.ep = (8 - int(parts[3][1])) * 8 + 'abcdefgh'.index(parts[3][0])
        self.halfmove = int(parts[4]) if len(parts) > 4 else 0
        self.move_log = []
        self._stack = []
        self._init_derived()
        return self

    def copy(self):
        n = Board.__new__(Board)
        n.sq = self.sq[:]
        n.turn = self.turn
        n.castle = self.castle
        n.ep = self.ep
        n.halfmove = self.halfmove
        n.move_log = self.move_log[:]
        n._stack = list(self._stack)
        n._start = self._start
        n.pcs = [set(self.pcs[0]), set(self.pcs[1])]
        n.ksq = self.ksq[:]
        n._init_np()
        n._legal = self._legal
        n._chk = self._chk
        n._occ = None
        n._eph = self._eph
        n.hash = self.hash
        n.hist = self.hist[:]
        return n

    def __deepcopy__(self, memo):
        return self.copy()

    # ------------------------------------------------------------------
    # attributi di compatibilità
    # ------------------------------------------------------------------
    @property
    def white_to_move(self):
        return self.turn == 0

    @white_to_move.setter
    def white_to_move(self, value):
        self.turn = 0 if value else 1
        self._legal = None
        self._chk = None

    @property
    def in_check(self):
        c = self._chk
        if c is None:
            c = self._attacked(self.ksq[self.turn], self.turn ^ 1)
            self._chk = c
        return c

    @property
    def king_square(self):
        k = self.ksq[self.turn]
        return (k >> 3, k & 7)

    @property
    def en_passant_square(self):
        """Indice bitboard della casa di presa en passant (o None)."""
        if self.ep < 0:
            return None
        return (self.ep ^ 56)

    @property
    def wK_moved(self): return not (self.castle & 3)
    @property
    def wR_right_moved(self): return not (self.castle & 1)
    @property
    def wR_left_moved(self): return not (self.castle & 2)
    @property
    def bK_moved(self): return not (self.castle & 12)
    @property
    def bR_right_moved(self): return not (self.castle & 4)
    @property
    def bR_left_moved(self): return not (self.castle & 8)
    @property
    def wR_right_captured(self): return False
    @property
    def wR_left_captured(self): return False
    @property
    def bR_right_captured(self): return False
    @property
    def bR_left_captured(self): return False

    @property
    def move_right_log(self):
        return []

    @property
    def position_history(self):
        return self.hist

    def position_key(self):
        return self.hash

    def _occupancy(self):
        occ = self._occ
        if occ is None:
            white = np.zeros(64, dtype=bool)
            black = np.zeros(64, dtype=bool)
            for code in (1, 2, 3, 4, 5, 6):
                white |= self._bbl[code]
                black |= self._bbl[code + 8]
            occ = {'white': white, 'black': black, 'all': white | black, 'attacked': None}
            self._occ = occ
        return occ

    @property
    def occupate_squares_by_white_bitboards(self):
        return self._occupancy()['white']

    @property
    def occupate_squares_by_black_bitboards(self):
        return self._occupancy()['black']

    @property
    def occupate_squares_bitboards(self):
        return self._occupancy()['all']

    @property
    def square_attacked_by_the_enemy_bitboards(self):
        occ = self._occupancy()
        if occ['attacked'] is None:
            arr = np.zeros(64, dtype=bool)
            enemy = self.turn ^ 1
            for s in range(64):
                arr[s ^ 56] = self._attacked(s, enemy)
            occ['attacked'] = arr
        return occ['attacked']

    # funzioni mantenute per compatibilità con il vecchio codice
    def clear_cache(self):
        self._legal = None
        self._chk = None
        self._occ = None

    def update_squares_bitboards(self):
        self.clear_cache()

    def update_king_position(self):
        pass

    # ------------------------------------------------------------------
    # Attacchi
    # ------------------------------------------------------------------
    def _attacked(self, t, c):
        """True se la casa t è attaccata dai pezzi del colore c (0 bianco, 1 nero)."""
        sq = self.sq
        b = c << 3
        pawn = b | 1
        for s in PAWN_ATT[c ^ 1][t]:
            if sq[s] == pawn:
                return True
        kn = b | 2
        for s in KNIGHT_T[t]:
            if sq[s] == kn:
                return True
        ki = b | 6
        for s in KING_T[t]:
            if sq[s] == ki:
                return True
        rk = b | 4
        qn = b | 5
        for ray in RAY_R[t]:
            for s in ray:
                p = sq[s]
                if p:
                    if p == rk or p == qn:
                        return True
                    break
        bs = b | 3
        for ray in RAY_B[t]:
            for s in ray:
                p = sq[s]
                if p:
                    if p == bs or p == qn:
                        return True
                    break
        return False

    def is_square_attacked(self, square):
        """Casa (riga, colonna) attaccata dall'avversario del giocatore di turno."""
        return self._attacked(square[0] * 8 + square[1], self.turn ^ 1)

    def is_in_check(self, white_turn):
        c = 0 if white_turn else 1
        return self._attacked(self.ksq[c], c ^ 1)

    def can_castle_kingside(self, white_turn):
        sq = self.sq
        if white_turn:
            return bool(self.castle & 1 and self.ksq[0] == 60 and sq[63] == 4
                        and not sq[61] and not sq[62]
                        and not self._attacked(60, 1) and not self._attacked(61, 1)
                        and not self._attacked(62, 1))
        return bool(self.castle & 4 and self.ksq[1] == 4 and sq[7] == 12
                    and not sq[5] and not sq[6]
                    and not self._attacked(4, 0) and not self._attacked(5, 0)
                    and not self._attacked(6, 0))

    def can_castle_queenside(self, white_turn):
        sq = self.sq
        if white_turn:
            return bool(self.castle & 2 and self.ksq[0] == 60 and sq[56] == 4
                        and not sq[57] and not sq[58] and not sq[59]
                        and not self._attacked(60, 1) and not self._attacked(59, 1)
                        and not self._attacked(58, 1))
        return bool(self.castle & 8 and self.ksq[1] == 4 and sq[0] == 12
                    and not sq[1] and not sq[2] and not sq[3]
                    and not self._attacked(4, 0) and not self._attacked(3, 0)
                    and not self._attacked(2, 0))

    # ------------------------------------------------------------------
    # Generazione mosse legali (con pin e scacchi calcolati una sola volta)
    # ------------------------------------------------------------------
    def _gen(self):
        sq = self.sq
        us = self.turn
        them = us ^ 1
        bu = us << 3
        bt = them << 3
        k = self.ksq[us]
        moves = []
        add = moves.append
        attacked = self._attacked

        checkers = 0
        chk = FULL
        pins = {}

        kn = bt | 2
        for s in KNIGHT_T[k]:
            if sq[s] == kn:
                checkers += 1
                chk = BIT[s]
        pw = bt | 1
        for s in PAWN_ATT[us][k]:
            if sq[s] == pw:
                checkers += 1
                chk = BIT[s]
        qn = bt | 5
        for rays, att in ((RAY_R[k], bt | 4), (RAY_B[k], bt | 3)):
            for ray in rays:
                m = 0
                pinned = -1
                for s in ray:
                    p = sq[s]
                    if not p:
                        m |= BIT[s]
                        continue
                    if p >> 3 == us:
                        if pinned >= 0:
                            break
                        pinned = s
                        m |= BIT[s]
                        continue
                    if p == att or p == qn:
                        if pinned < 0:
                            checkers += 1
                            chk = m | BIT[s]
                        else:
                            pins[pinned] = m | BIT[s]
                    break

        if checkers < 2:
            push_us = PUSH[us]
            dbl_us = DBL[us]
            promo_us = PROMO_SQ[us]
            patt_us = PAWN_ATT[us]
            for s in self.pcs[us]:
                p = sq[s]
                t = p & 7
                if t == 6:
                    continue
                lim = chk
                if pins:
                    pm = pins.get(s)
                    if pm is not None:
                        lim &= pm
                        if not lim:
                            continue
                if t == 1:
                    f = push_us[s]
                    if f >= 0 and not sq[f]:
                        if lim & BIT[f]:
                            if promo_us[f]:
                                for pr in PROMO_ORDER:
                                    add(s | (f << 6) | (pr << 12))
                            else:
                                add(s | (f << 6))
                        d2 = dbl_us[s]
                        if d2 >= 0 and not sq[d2] and lim & BIT[d2]:
                            add(s | (d2 << 6))
                    for d in patt_us[s]:
                        q = sq[d]
                        if q and q >> 3 == them and lim & BIT[d]:
                            if promo_us[d]:
                                for pr in PROMO_ORDER:
                                    add(s | (d << 6) | (pr << 12))
                            else:
                                add(s | (d << 6))
                elif t == 2:
                    for d in KNIGHT_T[s]:
                        q = sq[d]
                        if (not q or q >> 3 == them) and lim & BIT[d]:
                            add(s | (d << 6))
                else:
                    for ray in SLIDE[t][s]:
                        for d in ray:
                            q = sq[d]
                            if not q:
                                if lim & BIT[d]:
                                    add(s | (d << 6))
                            else:
                                if q >> 3 == them and lim & BIT[d]:
                                    add(s | (d << 6))
                                break

        # re: la casa del re viene svuotata per vedere gli attacchi "a raggi X"
        sq[k] = 0
        for d in KING_T[k]:
            q = sq[d]
            if q and q >> 3 == us:
                continue
            if not attacked(d, them):
                add(k | (d << 6))
        sq[k] = bu | 6

        # arrocco
        if not checkers and self.castle:
            c = self.castle
            if us == 0:
                if k == 60:
                    if c & 1 and sq[63] == 4 and not sq[61] and not sq[62] \
                            and not attacked(61, 1) and not attacked(62, 1):
                        add(60 | (62 << 6))
                    if c & 2 and sq[56] == 4 and not sq[57] and not sq[58] and not sq[59] \
                            and not attacked(59, 1) and not attacked(58, 1):
                        add(60 | (58 << 6))
            else:
                if k == 4:
                    if c & 4 and sq[7] == 12 and not sq[5] and not sq[6] \
                            and not attacked(5, 0) and not attacked(6, 0):
                        add(4 | (6 << 6))
                    if c & 8 and sq[0] == 12 and not sq[1] and not sq[2] and not sq[3] \
                            and not attacked(3, 0) and not attacked(2, 0):
                        add(4 | (2 << 6))

        # en passant (verifica esatta simulando la presa)
        ep = self.ep
        if ep >= 0:
            mine = bu | 1
            cs = ep + 8 if us == 0 else ep - 8
            enemy_pawn = bt | 1
            if sq[cs] == enemy_pawn and not sq[ep]:
                for s in PAWN_ATT[them][ep]:
                    if sq[s] == mine:
                        sq[s] = 0
                        sq[ep] = mine
                        sq[cs] = 0
                        ok = not attacked(k, them)
                        sq[s] = mine
                        sq[ep] = 0
                        sq[cs] = enemy_pawn
                        if ok:
                            add(s | (ep << 6))

        self._legal = moves
        self._chk = checkers > 0
        return moves

    def _get_legal(self):
        m = self._legal
        if m is None:
            m = self._gen()
        return m

    # ------------------------------------------------------------------
    # Elenco mosse
    # ------------------------------------------------------------------
    def get_legal_valid_moves(self, include_promotions=False):
        """
        Mosse legali.
          - default: [[[r0, c0], [r1, c1]], ...]  (la promozione compare una volta sola, a donna)
          - include_promotions=True: [[[r0, c0], [r1, c1], 'Q'|'R'|'B'|'N'|None], ...]
        """
        R = ROW
        C = COL
        out = []
        if include_promotions:
            for m in self._get_legal():
                f = m & 63
                t = (m >> 6) & 63
                out.append([[R[f], C[f]], [R[t], C[t]], PROMO_LETTER.get(m >> 12)])
            return out
        for m in self._get_legal():
            pr = m >> 12
            if pr and pr != 5:
                continue
            f = m & 63
            t = (m >> 6) & 63
            out.append([[R[f], C[f]], [R[t], C[t]]])
        return out

    def get_legal_move_objects(self):
        """Tutte le mosse legali come oggetti Move (4 mosse per ogni promozione)."""
        b = self.board
        objs = []
        for m in self._get_legal():
            f = m & 63
            t = (m >> 6) & 63
            objs.append(Move((f >> 3, f & 7), (t >> 3, t & 7), b,
                             promotion=PROMO_LETTER.get(m >> 12, 'Q')))
        return objs

    def find_move(self, start, end, promotion='Q'):
        """Costruisce l'oggetto Move per (start, end) se è legale, altrimenti None."""
        f = int(start[0]) * 8 + int(start[1])
        t = int(end[0]) * 8 + int(end[1])
        promotion = (promotion or 'Q').upper()
        code = PROMO_CODE.get(promotion, 5)
        for m in self._get_legal():
            if (m & 63) == f and ((m >> 6) & 63) == t:
                pr = m >> 12
                if pr == 0 or pr == code:
                    return Move((f >> 3, f & 7), (t >> 3, t & 7), self.board,
                                promotion=promotion if pr else 'Q')
        return None

    def get_capture_moves(self, include_promotions=False):
        """
        Le mosse di get_legal_valid_moves (stesso formato, stesso ordine) che arrivano su una
        casa occupata. L'en passant non è incluso, come nel filtro `board[r][c] != '--'`.
        """
        sq = self.sq
        R = ROW
        C = COL
        out = []
        for m in self._get_legal():
            t = (m >> 6) & 63
            if not sq[t]:
                continue
            pr = m >> 12
            f = m & 63
            if include_promotions:
                out.append([[R[f], C[f]], [R[t], C[t]], PROMO_LETTER.get(pr)])
            else:
                if pr and pr != 5:
                    continue
                out.append([[R[f], C[f]], [R[t], C[t]]])
        return out

    def gives_check(self, move):
        """
        True se la mossa legale `move` ([[r0, c0], [r1, c1]] oppure con 3° elemento = promozione)
        dà scacco all'avversario. Equivale a make_move + in_check + undo_move, ma senza creare
        oggetti Move e senza aggiornare scacchiera numpy e bitboard.
        """
        frm = move[0][0] * 8 + move[0][1]
        to = move[1][0] * 8 + move[1][1]
        promo = 0
        if (self.sq[frm] & 7) == 1 and (to < 8 or to >= 56):
            promo = PROMO_CODE.get(move[2], 5) if len(move) > 2 and move[2] else 5
        self._do(frm, to, promo, False)
        result = self.in_check
        self._undo(False)
        return result

    def is_legal(self, start, end, promotion='Q'):
        return self.find_move(start, end, promotion) is not None

    # ------------------------------------------------------------------
    # Esecuzione / annullamento
    # ------------------------------------------------------------------
    def _do(self, frm, to, promo, sync=True):
        sq = self.sq
        us = self.turn
        them = us ^ 1
        p = sq[frm]
        cap = sq[to]
        t = p & 7
        old_castle = self.castle
        pcs_us = self.pcs[us]
        pcs_them = self.pcs[them]
        zp = ZP

        h = self.hash ^ ZSIDE ^ self._eph ^ zp[p][frm]
        newp = p
        kind = 0
        ep_new = -1

        pcs_us.discard(frm)
        if cap:
            pcs_them.discard(to)
            h ^= zp[cap][to]

        if t == 1:
            if (frm ^ to) & 7 and not cap:          # presa en passant
                kind = 1
                cs = to + 8 if us == 0 else to - 8
                ecode = sq[cs]
                sq[cs] = 0
                pcs_them.discard(cs)
                h ^= zp[ecode][cs]
            elif promo:
                newp = (us << 3) | promo
                kind = 4
            elif to - frm == 16 or frm - to == 16:
                ep_new = (frm + to) >> 1
        elif t == 6:
            self.ksq[us] = to
            d = to - frm
            if d == 2 or d == -2:
                rook = (us << 3) | 4
                if d == 2:
                    rf = to + 1
                    rt = to - 1
                    kind = 2
                else:
                    rf = to - 2
                    rt = to + 1
                    kind = 3
                sq[rf] = 0
                sq[rt] = rook
                pcs_us.discard(rf)
                pcs_us.add(rt)
                h ^= zp[rook][rf] ^ zp[rook][rt]

        sq[frm] = 0
        sq[to] = newp
        pcs_us.add(to)
        h ^= zp[newp][to]

        new_castle = old_castle & CM[frm] & CM[to]
        if new_castle != old_castle:
            h ^= ZC[old_castle] ^ ZC[new_castle]
            self.castle = new_castle

        eph = 0
        if ep_new >= 0:
            ec = to & 7
            ep_pawn = (them << 3) | 1
            if (ec > 0 and sq[to - 1] == ep_pawn) or (ec < 7 and sq[to + 1] == ep_pawn):
                eph = ZEP[ec]

        self._stack.append((frm, to, p, cap, old_castle, self.ep, self.halfmove, kind,
                            self.hash, self._eph, self._legal, self._chk, newp))

        self.ep = ep_new
        self._eph = eph
        self.hash = h ^ eph
        if t == 1 or cap:
            self.halfmove = 0
        else:
            self.halfmove += 1
        self.turn = them
        self._legal = None
        self._chk = None
        self._occ = None
        self.hist.append(self.hash)

        if sync:
            self._apply(frm, to, p, cap, newp, kind, us, False)

    def _undo(self, sync=True):
        (frm, to, p, cap, castle, ep, hm, kind, h, eph, legal, chk, newp) = self._stack.pop()
        us = self.turn ^ 1
        them = us ^ 1
        self.turn = us
        sq = self.sq
        pcs_us = self.pcs[us]

        sq[frm] = p
        sq[to] = cap
        pcs_us.discard(to)
        pcs_us.add(frm)
        if cap:
            self.pcs[them].add(to)

        if kind == 0 or kind == 4:
            if p & 7 == 6:
                self.ksq[us] = frm
        elif kind == 1:
            cs = to + 8 if us == 0 else to - 8
            sq[cs] = (them << 3) | 1
            self.pcs[them].add(cs)
        else:
            self.ksq[us] = frm
            rook = (us << 3) | 4
            if kind == 2:
                sq[to + 1] = rook
                sq[to - 1] = 0
                pcs_us.discard(to - 1)
                pcs_us.add(to + 1)
            else:
                sq[to - 2] = rook
                sq[to + 1] = 0
                pcs_us.discard(to + 1)
                pcs_us.add(to - 2)

        self.castle = castle
        self.ep = ep
        self.halfmove = hm
        self.hash = h
        self._eph = eph
        self._legal = legal
        self._chk = chk
        self._occ = None
        self.hist.pop()

        if sync:
            self._apply(frm, to, p, cap, newp, kind, us, True)

    def _apply(self, frm, to, p, cap, newp, kind, us, undo):
        """Aggiorna scacchiera numpy e bitboard in modo incrementale."""
        flat = self._flat
        bbl = self._bbl
        ch = [(frm, p, 0), (to, cap, newp)]
        if kind == 1:
            cs = to + 8 if us == 0 else to - 8
            ch.append((cs, ((us ^ 1) << 3) | 1, 0))
        elif kind == 2:
            rook = (us << 3) | 4
            ch.append((to + 1, rook, 0))
            ch.append((to - 1, 0, rook))
        elif kind == 3:
            rook = (us << 3) | 4
            ch.append((to - 2, rook, 0))
            ch.append((to + 1, 0, rook))
        for s, old, new in ch:
            if undo:
                old, new = new, old
            flat[s] = NAME[new]
            i = s ^ 56
            if old:
                bbl[old][i] = False
            if new:
                bbl[new][i] = True

    def make_move(self, move):
        to = move.end_row * 8 + move.end_col
        if self.sq[to] & 7 == 6:
            raise ValueError(f"Mossa illegale: cattura del re {move.startSq}->{move.endSq}")
        frm = move.start_row * 8 + move.start_col
        promo = PROMO_CODE[move.promotion] if move.is_pawn_promotion else 0
        self._do(frm, to, promo)
        self.move_log.append(move)
        move.en_passant_square = (self.ep ^ 56) if self.ep >= 0 else None

    def undo_move(self):
        if not self._stack:
            print("No moves to undo!")
            return
        self._undo()
        if self.move_log:
            self.move_log.pop()

    def update_castling_rights(self, move):
        pass

    # ------------------------------------------------------------------
    # Fine partita
    # ------------------------------------------------------------------
    def is_checkmate(self):
        return len(self._get_legal()) == 0 and self.in_check

    def is_stalemate(self):
        return len(self._get_legal()) == 0 and not self.in_check

    def _insufficient_material(self):
        sq = self.sq
        minors = []
        for s in self.pcs[0] | self.pcs[1]:
            t = sq[s] & 7
            if t == 6:
                continue
            if t == 1 or t == 4 or t == 5:
                return False
            minors.append((t, ((s >> 3) + (s & 7)) & 1))
        if len(minors) <= 1:
            return True
        if all(t == 3 for t, _ in minors) and len({c for _, c in minors}) == 1:
            return True
        return False

    def is_draw(self):
        if self._insufficient_material():
            return True
        if self.hist.count(self.hash) >= 3:
            return True
        if self.halfmove >= 100 and not self.is_checkmate():
            return True
        return False

    # ------------------------------------------------------------------
    # PGN
    # ------------------------------------------------------------------
    def _san_base(self, move):
        """SAN (senza + / #) di `move`, calcolata PRIMA di eseguirla su questa board."""
        files = 'abcdefgh'
        sq = self.sq
        frm = move.start_row * 8 + move.start_col
        to = move.end_row * 8 + move.end_col
        p = sq[frm]
        t = p & 7
        dst = files[move.end_col] + str(8 - move.end_row)
        capture = sq[to] != 0 or (t == 1 and move.start_col != move.end_col)

        if t == 6 and abs(move.end_col - move.start_col) == 2:
            return 'O-O' if move.end_col > move.start_col else 'O-O-O'

        if t == 1:
            san = f"{files[move.start_col]}x{dst}" if capture else dst
            if move.is_pawn_promotion:
                san += '=' + move.promotion
            return san

        others = [m for m in self._get_legal()
                  if ((m >> 6) & 63) == to and (m & 63) != frm and sq[m & 63] == p]
        dis = ''
        if others:
            sf, sr = move.start_col, move.start_row
            if all((m & 7) != sf for m in others):
                dis = files[sf]
            elif all(((m & 63) >> 3) != sr for m in others):
                dis = str(8 - sr)
            else:
                dis = files[sf] + str(8 - sr)
        return f"{'NBRQK'[t - 2]}{dis}{'x' if capture else ''}{dst}"

    def get_pgn(self, move_log=None):
        """PGN in notazione algebrica standard: "1. e4 e5 2. Nf3 Nc6 ... *"."""
        if move_log is None:
            move_log = self.move_log
        if not move_log:
            return ""

        pgn_moves = []
        temp = Board()
        sq0, turn0, castle0, ep0, hm0 = self._start
        temp.sq = list(sq0)
        temp.turn = turn0
        temp.castle = castle0
        temp.ep = ep0
        temp.halfmove = hm0
        temp._init_derived()
        for move in list(move_log):
            san = temp._san_base(move)
            temp.make_move(move)
            if temp.in_check:
                san += '#' if temp.is_checkmate() else '+'
            pgn_moves.append(san)

        parts = []
        i = 0
        if turn0 == 1:
            parts.append(f"1... {pgn_moves[0]}")
            i = 1
        while i < len(pgn_moves):
            move_no = (i + turn0) // 2 + 1
            if i + 1 < len(pgn_moves):
                parts.append(f"{move_no}. {pgn_moves[i]} {pgn_moves[i + 1]}")
            else:
                parts.append(f"{move_no}. {pgn_moves[i]}")
            i += 2

        result = '*'
        if temp.is_checkmate():
            result = '0-1' if temp.white_to_move else '1-0'
        elif temp.is_stalemate() or temp.is_draw():
            result = '1/2-1/2'

        return ' '.join(parts) + ' ' + result


class Move:
    def __init__(self, startSq, endSq, board, en_passant_square=None, promotion='Q'):
        sr, sc = startSq
        er, ec = endSq
        self.startSq = startSq
        self.endSq = endSq
        self.start_row = sr
        self.start_col = sc
        self.end_row = er
        self.end_col = ec
        try:
            pm = board[sr, sc]
            pc = board[er, ec]
        except TypeError:
            pm = board[sr][sc]
            pc = board[er][ec]
        pm = str(pm)
        pc = str(pc)
        self.pieceMoved = pm
        self.pieceCaptured = pc
        self.is_pawn_promotion = False
        self.is_en_passant = False
        self.is_castle = False
        self.en_passant_square = en_passant_square
        self.promotion = None

        t = pm[1]
        if t == 'K':
            if sc - ec == 2 or ec - sc == 2:
                self.is_castle = True
        elif t == 'p':
            if pc == '--' and sc != ec:
                self.is_en_passant = True
            if (er == 0 and pm[0] == 'w') or (er == 7 and pm[0] == 'b'):
                self.is_pawn_promotion = True
                promotion = (promotion or 'Q').upper()
                if promotion not in PROMO_CODE:
                    raise ValueError(f"Promozione non valida: {promotion}")
                self.promotion = promotion

        self.moveID = (sr * 1000 + sc * 100 + er * 10 + ec, pm)