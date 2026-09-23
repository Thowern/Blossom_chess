# intermediate.py
import json
from Blossom import Board, Move
import Blossom_Brain_06 as brain
from Score_board_02_fast import score_board

_gs = None


def _board_to_list():
    b = _gs.board
    return [[str(b[r][c]) for c in range(8)] for r in range(8)]


def _state_dict():
    last = None
    if _gs.move_log:
        m = _gs.move_log[-1]
        last = {'start': [m.start_row, m.start_col],
                'end':   [m.end_row,   m.end_col]}
    return {
        'board':          _board_to_list(),
        'white_to_move':  bool(_gs.white_to_move),
        'in_check':       bool(_gs.in_check),
        'king_square':    list(_gs.king_square),
        'checkmate':      bool(_gs.is_checkmate()),
        'stalemate':      bool(_gs.is_stalemate()),
        'draw':           bool(_gs.is_draw()),
        'last_move':      last,
        'move_log_len':   len(_gs.move_log),
    }


def new_game():
    global _gs
    _gs = Board()
    return json.dumps(_state_dict())


def get_state():
    return json.dumps(_state_dict())


def legal_moves():
    return json.dumps(_gs.get_legal_valid_moves())


def get_score():
    return float(score_board(_gs))


def try_move(sr, sc, er, ec, promotion='Q'):
    start = [int(sr), int(sc)]
    end   = [int(er), int(ec)]
    if [start, end] not in _gs.get_legal_valid_moves():
        return json.dumps(None)
    piece = str(_gs.board[start[0]][start[1]])
    is_promo = piece[1] == 'p' and (
        (piece[0] == 'w' and end[0] == 0) or (piece[0] == 'b' and end[0] == 7))
    if is_promo:
        _gs.make_move(Move(start, end, _gs.board, promotion=promotion))
    else:
        _gs.make_move(Move(start, end, _gs.board))
    return json.dumps(_state_dict())


def undo():
    if _gs.move_log:
        _gs.undo_move()
    return json.dumps(_state_dict())


def ai_move():
    moves = _gs.get_legal_valid_moves(include_promotions=brain.UNDERPROMOTION)
    mv = brain.get_ai_move(moves, _gs, Move)
    if mv is None:
        return json.dumps(None)
    if len(mv) > 2 and mv[2]:
        _gs.make_move(Move(mv[0], mv[1], _gs.board, promotion=mv[2]))
    else:
        _gs.make_move(Move(mv[0], mv[1], _gs.board))
    return json.dumps(_state_dict())