"""Utility per convertire e formattare il move_log prodotto da `Blossom_cache.Board`.

Funzionalità:
- `format_move_log(move_log)` : ritorna una stringa leggibile con numerazione e notazione tipo SAN base (incl. O-O, O-O-O, promozioni, e.p., catture).
- `move_log_to_engine_list(move_log)` : ritorna la lista di mosse in formato engine (lista di coppie [[r,c],[r,c]]), utile per riapplicare mosse.
- `uci_from_move(move)` : ritorna la mossa in formato UCI semplice (es. e2e4).

Esempio d'uso:
    from Blossom_cache import Board
    b = Board()
    # ... fai mosse con b.make_move(...)
    print(format_move_log(b.move_log))
"""

from Blossom import Move

FILES = 'abcdefgh'


def square_to_alg(square):
    """Converte (row, col) -> notazione algebrica, es. (6,4) -> e2"""
    row, col = square
    file = FILES[col]
    rank = str(8 - row)
    return f"{file}{rank}"


def uci_from_move(move: Move) -> str:
    """Restituisce la mossa in formato UCI compatto, es. e2e4"""
    return f"{square_to_alg(move.startSq)}{square_to_alg(move.endSq)}"


def format_move(move: Move) -> str:
    """Restituisce una stringa leggibile della mossa (SAN-like ma semplice).

    - Alfieri/Cavalli/Torri/Funzioni: N,B,R,Q,K + (x se cattura) + destinazione
    - Pedoni: e4 o exd5 se cattura
    - Arrocco: O-O / O-O-O
    - Promozione: e8=Q o exd8=Q
    - En passant: aggiunge " e.p." all'output
    Include sempre la coppia di coordinate originali tra parentesi per rimuovere ambiguità.
    """
    piece = move.pieceMoved
    dest = square_to_alg(move.endSq)
    src = square_to_alg(move.startSq)

    # Arrocco
    if move.is_castle:
        return 'O-O' if move.end_col - move.start_col == 2 else 'O-O-O'

    # Promozione
    promo = ''
    if move.is_pawn_promotion:
        # assumiamo promozione a Donna
        promo = '=Q'

    # Cattura
    is_capture = move.pieceCaptured != '--' or move.is_en_passant

    if piece.endswith('p'):
        if is_capture:
            notation = f"{FILES[move.start_col]}x{dest}"
        else:
            notation = dest
        notation += promo
        if move.is_en_passant:
            notation += ' e.p.'
    else:
        # pezzo diverso dal pedone: usa lettera (N,B,B etc)
        piece_letter = piece[1]
        notation = f"{piece_letter}"
        if is_capture:
            notation += 'x'
        notation += dest
        if move.is_pawn_promotion:
            notation += promo

    # aggiungo coordinate per chiarezza
    notation += f" ({src}->{dest})"
    return notation


def format_move_log(move_log) -> str:
    """Formatta l'intero move_log (lista di Move) in stringa numerata.

    Restituisce qualcosa del tipo:
    1. e4 e5
    2. Nf3 Nf6
    ...
    """
    lines = []
    for i in range(0, len(move_log), 2):
        move_no = i // 2 + 1
        white = format_move(move_log[i])
        black = ''
        if i + 1 < len(move_log):
            black = format_move(move_log[i + 1])
        lines.append(f"{move_no}. {white} {black}".strip())
    return "\n".join(lines)


def move_log_to_engine_list(move_log):
    """Converte una lista di Move in una lista compatibile con l'engine
    (lista di coppie [[r,c],[r,c]]), estraendo gli start/end come liste.
    """
    engine_moves = []
    for m in move_log:
        engine_moves.append([[m.start_row, m.start_col], [m.end_row, m.end_col]])
    return engine_moves


if __name__ == '__main__':
    # Demo rapido solo se eseguito come script
    from Blossom import Board, Move
    b = Board()
    print('Posizione iniziale:')
    print(format_move_log(b.move_log))

    # qualche mossa di prova
    m1 = Move((6,4),(4,4), b.board)  # e2-e4
    b.make_move(m1)
    m2 = Move((1,4),(3,4), b.board)  # e7-e5
    b.make_move(m2)
    m3 = Move((7,6),(5,5), b.board)  # g1-f3
    b.make_move(m3)

    print('\nMove log formattato:')
    print(format_move_log(b.move_log))
    print('\nMove log engine-like:')
    print(move_log_to_engine_list(b.move_log))
