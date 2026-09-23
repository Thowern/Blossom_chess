piece_score = {
    'p': 100,
    'N': 288,
    'B': 345,
    'R': 480,
    'Q': 1077,
    'K': 30
}

from Score_board_02_fast import score_board
import time
import random
from convert import format_move_log

INITIAL_SX = 20
T_MAX_DEPTH = 8
TIME_LIMIT = 0.5

# True: l'AI considera anche le sottopromozioni (torre, alfiere, cavallo).
# In quel caso le mosse hanno 3 elementi: [[r0, c0], [r1, c1], 'Q'|'R'|'B'|'N'|None].
# False: promuove sempre a donna, come prima.
UNDERPROMOTION = True

# --- parametri della ricerca ---
MATE = 1_000_000            # valore del matto; il matto a ply p vale MATE - p
MATE_BOUND = MATE - 1000    # oltre questa soglia un punteggio è "di matto"
LMR_INDEX = 4               # dalla mossa di indice >= 4 (quiete) si riduce di 1 ply
DELTA_MARGIN = 200          # margine del delta pruning in quiescenza
QS_CHECK_SX = 10            # quante mosse di "evasione" al massimo in quiescenza sotto scacco
TT_MAX = 500_000            # dimensione massima della tabella di trasposizione

EXACT, LOWER, UPPER = 0, 1, 2

_tt = {}      # hash -> (depth, flag, score, best_move)
_path = []    # hash delle posizioni dalla radice al nodo corrente (patta per ripetizione)

best_move = None
DEPTH = 0


def _legal(gs):
    """Mosse legali (con le promozioni a T, A, C se UNDERPROMOTION è attivo)."""
    return gs.get_legal_valid_moves(include_promotions=UNDERPROMOTION)


def _captures(gs):
    """Mosse legali che finiscono su una casa occupata (stesso ordine di get_legal_valid_moves)."""
    fast = getattr(gs, 'get_capture_moves', None)
    if fast is not None:
        return fast(include_promotions=UNDERPROMOTION)
    board = gs.board
    return [move for move in _legal(gs) if board[move[1][0], move[1][1]][1] != '-']


def _make_move(gs, Move, move):
    """Esegue la mossa, promozione compresa (3° elemento della mossa, se presente)."""
    if len(move) > 2 and move[2]:
        gs.make_move(Move(move[0], move[1], gs.board, promotion=move[2]))
    else:
        gs.make_move(Move(move[0], move[1], gs.board))


def _try_make(gs, Move, move):
    try:
        _make_move(gs, Move, move)
        return True
    except Exception:
        print("Errore: mossa non valida dall'AI")
        print("Mossa AI:", move)
        print("Mosse eseguite:", format_move_log(gs.move_log))
        return False


def _hash(gs):
    h = gs.hash
    return h() if callable(h) else h


def _to_tt(score, ply):
    """I punteggi di matto nella TT sono relativi al nodo, non alla radice."""
    if score > MATE_BOUND:
        return score + ply
    if score < -MATE_BOUND:
        return score - ply
    return score


def _from_tt(score, ply):
    if score > MATE_BOUND:
        return score - ply
    if score < -MATE_BOUND:
        return score + ply
    return score


def _is_promotion(board, move):
    piece = board[move[0][0], move[0][1]]
    return (piece == 'wp' and move[1][0] == 0) or (piece == 'bp' and move[1][0] == 7)


def order_moves(moves, gs, Move, first=None, use_check=True):
    """Ordina le mosse. `first` (mossa della TT / iterazione precedente) va in testa.
    use_check=False salta il test di scacco (più veloce, per i nodi interni)."""
    board = gs.board

    def move_value(move):
        value = 0
        if first is not None and move == first:
            value += 10000
        capturing_piece = board[move[0][0], move[0][1]]
        captured_piece = board[move[1][0], move[1][1]]
        if captured_piece != '--':
            value += piece_score[captured_piece[1]] / piece_score[capturing_piece[1]]
        if (capturing_piece == 'wp' and move[1][0] == 0) or (capturing_piece == 'bp' and move[1][0] == 7):
            # la promozione a donna resta in testa, le altre subito dopo
            value += 20 if (len(move) < 3 or move[2] in (None, 'Q')) else 10
        if use_check and check_controll(move, gs, Move):
            value += 5
        return value

    moves.sort(key=move_value, reverse=True)
    return moves


def check_controll(move, gs, Move):
    if gs.board[move[1][0], move[1][1]][1] == 'K':
        print('damn')
        print([move[0], move[1]])
        print(gs.board)
        print(gs.get_pgn(gs.move_log))
        return False

    # percorso veloce: stesso risultato di make_move + in_check + undo_move
    gives_check = getattr(gs, 'gives_check', None)
    if gives_check is not None:
        return gives_check(move)

    try:
        _make_move(gs, Move, move)
    except Exception:
        print("Errore: mossa non valida dall'AI")
        print("Mossa AI:", [move[0], move[1]])
        print("Mosse eseguite:", format_move_log(gs.move_log))
        return False
    controll = gs.in_check
    gs.undo_move()
    return controll


def get_ai_move(valid_moves, gs, Move):
    random.shuffle(valid_moves)
    valid_moves = order_moves(valid_moves, gs, Move)

    return iterative_deepening(valid_moves, gs, Move)


def iterative_deepening(valid_moves, gs, Move):
    global best_move, DEPTH
    best_move = None
    completed_move = None
    start_time = time.time()
    _path.clear()
    if len(_tt) > TT_MAX:
        _tt.clear()

    max_depth = 2 if len(gs.move_log) < 2 else T_MAX_DEPTH

    DEPTH = 1
    while DEPTH <= max_depth:
        if time.time() - start_time >= TIME_LIMIT:
            break

        score = get_best_move(valid_moves, gs, Move, DEPTH, gs.white_to_move,
                              float('-inf'), float('inf'), INITIAL_SX, 0)

        if best_move is None:  # nessuna mossa (matto/stallo alla radice)
            break
        completed_move = best_move

        # la migliore di questa iterazione parte per prima nella prossima
        if completed_move in valid_moves:
            valid_moves.remove(completed_move)
            valid_moves.insert(0, completed_move)

        # matto trovato: inutile andare più a fondo
        if abs(score) > MATE_BOUND:
            break

        DEPTH += 1
    print(DEPTH)
    return completed_move


def get_best_move(valid_moves, gs, Move, depth, white_turn, alpha, beta, sx, ply):
    """Minimax con alpha-beta, TT, patta per ripetizione, matto/stallo e LMR.
    valid_moves è già passato (e ordinato) solo alla radice; altrove è None e si genera qui."""
    global best_move

    if sx <= 0 or depth == 0:
        return quiescence_search(gs, Move, alpha, beta, white_turn, sx, ply)

    key = _hash(gs)

    # patta per ripetizione: la posizione è già comparsa nel percorso corrente
    if ply > 0 and key in _path:
        return 0

    # tabella di trasposizione
    tt_move = None
    entry = _tt.get(key)
    if entry is not None:
        e_depth, e_flag, e_score, e_move = entry
        tt_move = e_move
        if ply > 0 and e_depth >= depth:
            s = _from_tt(e_score, ply)
            if e_flag == EXACT:
                return s
            if e_flag == LOWER:
                alpha = max(alpha, s)
            else:
                beta = min(beta, s)
            if alpha >= beta:
                return s

    if valid_moves is None:
        valid_moves = order_moves(_legal(gs), gs, Move, first=tt_move, use_check=False)

    # nessuna mossa: matto (più vicino = meglio) oppure stallo (patta)
    if not valid_moves:
        if gs.in_check:
            return -(MATE - ply) if white_turn else (MATE - ply)
        return 0

    orig_alpha, orig_beta = alpha, beta
    maximizing = white_turn
    best_score = float('-inf') if maximizing else float('inf')
    best_local = None

    _path.append(key)
    for index, move in enumerate(valid_moves):
        board = gs.board
        captured = board[move[1][0], move[1][1]][1] != '-'
        sxdec = 3 if captured else 1   # letto PRIMA della mossa

        _make_move(gs, Move, move)

        new_depth = depth - 1
        reduced = False
        # Late Move Reduction: solo mosse quiete che non danno scacco
        if index >= LMR_INDEX and depth > 2 and not captured and not gs.in_check:
            new_depth -= 1
            reduced = True

        new_sx = sx - sxdec
        score = get_best_move(None, gs, Move, new_depth, not white_turn, alpha, beta, new_sx, ply + 1)

        # se la mossa ridotta sembra migliorare la finestra, ricerca piena
        if reduced and ((maximizing and score > alpha) or (not maximizing and score < beta)):
            score = get_best_move(None, gs, Move, depth - 1, not white_turn, alpha, beta, new_sx, ply + 1)

        gs.undo_move()

        if maximizing:
            if score > best_score:
                best_score = score
                best_local = move
                if ply == 0:
                    best_move = move
            if score > alpha:
                alpha = score
        else:
            if score < best_score:
                best_score = score
                best_local = move
                if ply == 0:
                    best_move = move
            if score < beta:
                beta = score

        if beta <= alpha:
            break
    _path.pop()

    # salvataggio in TT
    if best_score <= orig_alpha:
        flag = UPPER
    elif best_score >= orig_beta:
        flag = LOWER
    else:
        flag = EXACT
    old = _tt.get(key)
    if old is None or depth >= old[0]:
        _tt[key] = (depth, flag, _to_tt(best_score, ply), best_local)

    return best_score


def quiescence_search(gs, Move, alpha, beta, white_turn, sx, ply):
    maximizing = white_turn
    stand_pat = None

    if gs.in_check and sx > -QS_CHECK_SX:
        # sotto scacco non si può "passare": si cercano tutte le evasioni
        moves = order_moves(_legal(gs), gs, Move, use_check=False)
        if not moves:
            return -(MATE - ply) if maximizing else (MATE - ply)
    else:
        stand_pat = score_board(gs)
        if maximizing:
            if stand_pat >= beta:
                return beta
            if alpha < stand_pat:
                alpha = stand_pat
        else:
            if stand_pat <= alpha:
                return alpha
            if beta > stand_pat:
                beta = stand_pat
        moves = order_moves(_captures(gs), gs, Move)

    board = gs.board
    for move in moves:
        target = board[move[1][0], move[1][1]][1]
        if target == 'K':
            print('damn')
            print(move)
            print(gs.board)
            print(gs.get_pgn(gs.move_log))
            continue

        # delta pruning (non sotto scacco e non per le promozioni)
        if stand_pat is not None and not _is_promotion(board, move):
            gain = piece_score.get(target, 100)  # casa vuota = en passant
            if maximizing:
                if stand_pat + gain + DELTA_MARGIN < alpha:
                    continue
            else:
                if stand_pat - gain - DELTA_MARGIN > beta:
                    continue

        if not _try_make(gs, Move, move):
            continue
        score = quiescence_search(gs, Move, alpha, beta, not white_turn, sx - 1, ply + 1)
        gs.undo_move()

        if maximizing:
            if score >= beta:
                return beta
            if score > alpha:
                alpha = score
        else:
            if score <= alpha:
                return alpha
            if score < beta:
                beta = score

    return alpha if maximizing else beta