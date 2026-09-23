import pygame as p
from Blossom import Board, Move
import Blossom_Brain_06 as brain
from Blossom_Brain_06 import get_ai_move
from Score_board_tab import score_board


# Constants
BOARD_WIDTH = BOARD_HEIGHT = 600
DIMENSION = 8
SQ_SIZE = BOARD_HEIGHT // DIMENSION
MAX_FPS = 15
IMAGES = {}
SIDEBAR_WIDTH = int(BOARD_WIDTH/10)
BORDER_WIDTH = int(BOARD_WIDTH/100)

PROMOTION_CHOICES = ['Q', 'R', 'B', 'N']
PROMOTION_KEYS = {p.K_q: 'Q', p.K_r: 'R', p.K_b: 'B', p.K_n: 'N'}

p.init()


def load_images():
    """Load the images for the chess pieces and resize them to the appropriate size."""
    pieces = ['wp', 'wR', 'wN', 'wB', 'wQ', 'wK', 'bp', 'bR', 'bN', 'bB', 'bQ', 'bK']
    for piece in pieces:
        image = p.image.load("imag/" + piece + ".png")
        resized_image = p.transform.scale(image, (SQ_SIZE, SQ_SIZE))
        IMAGES[piece] = resized_image


def flip_rc(row, col, flipped):
    """
    Converte una coppia (riga, colonna) tra coordinate scacchiera e coordinate schermo.
    La trasformazione è la stessa nei due sensi (ruotare due volte riporta al punto di
    partenza), quindi la stessa funzione serve sia per disegnare sia per interpretare i click.
    """
    return (7 - row, 7 - col) if flipped else (row, col)


def is_promotion_move(gs, start, end):
    """True se il pezzo in `start` è un pedone che arriva all'ultima traversa."""
    piece = gs.board[start[0]][start[1]]
    return piece[1] == 'p' and ((piece[0] == 'w' and end[0] == 0) or (piece[0] == 'b' and end[0] == 7))


def choose_promotion(screen, clock, color):
    """
    Mostra un riquadro con Donna, Torre, Alfiere, Cavallo.
    Ritorna 'Q', 'R', 'B' o 'N', oppure None se la scelta viene annullata
    (Esc, click fuori dal riquadro, chiusura della finestra).
    Si può scegliere anche con i tasti Q, R, B, N.
    """
    background = screen.copy()
    pad = BORDER_WIDTH * 2
    label_h = 12
    panel = p.Rect(0, 0, 4 * SQ_SIZE + 2 * pad, SQ_SIZE + 2 * pad + label_h)
    panel.center = (BORDER_WIDTH + BOARD_WIDTH // 2, BORDER_WIDTH + BOARD_HEIGHT // 2)
    buttons = [p.Rect(panel.x + pad + i * SQ_SIZE, panel.y + pad + label_h, SQ_SIZE, SQ_SIZE)
               for i in range(4)]
    font = p.font.SysFont("verdana", 15, False, False)
    label = font.render("Promote to (Esc = cancel)", True, p.Color(57, 134, 247))

    while True:
        for e in p.event.get():
            if e.type == p.QUIT:
                p.event.post(p.event.Event(p.QUIT))   # lascia che main() chiuda il programma
                return None
            elif e.type == p.KEYDOWN:
                if e.key == p.K_ESCAPE:
                    return None
                if e.key in PROMOTION_KEYS:
                    return PROMOTION_KEYS[e.key]
            elif e.type == p.MOUSEBUTTONDOWN and e.button == 1:
                for letter, rect in zip(PROMOTION_CHOICES, buttons):
                    if rect.collidepoint(e.pos):
                        return letter
                if not panel.collidepoint(e.pos):
                    return None

        screen.blit(background, (0, 0))
        p.draw.rect(screen, p.Color(238, 230, 154), panel)
        p.draw.rect(screen, p.Color("black"), panel, BORDER_WIDTH)
        screen.blit(label, (panel.centerx - label.get_width() // 2, panel.y + pad // 2 + 2))
        mouse = p.mouse.get_pos()
        for letter, rect in zip(PROMOTION_CHOICES, buttons):
            if rect.collidepoint(mouse):
                p.draw.rect(screen, p.Color(179, 181, 227), rect)
            screen.blit(IMAGES[color + letter], rect)
            p.draw.rect(screen, p.Color('gray'), rect, 1)
        p.display.flip()
        clock.tick(MAX_FPS)


def make_ai_move(gs, ai_move):
    """Esegue la mossa dell'AI, promozione compresa (3° elemento della mossa, se presente)."""
    if len(ai_move) > 2 and ai_move[2]:
        gs.make_move(Move(ai_move[0], ai_move[1], gs.board, promotion=ai_move[2]))
    else:
        gs.make_move(Move(ai_move[0], ai_move[1], gs.board))


def main():
    global game_over
    screen = p.display.set_mode((BOARD_WIDTH + SIDEBAR_WIDTH + 2 * BORDER_WIDTH, BOARD_HEIGHT + 2 * BORDER_WIDTH))
    clock = p.time.Clock()
    screen.fill(p.Color(238, 230, 154))

    gs = Board()
    valid_moves = gs.get_legal_valid_moves()
    move_made = False
    animate_move_flag = False

    load_images()

    running = True
    sq_selected = ()
    player_clicks = []
    game_over = False

    player_white = False
    player_black = False

    # Orientamento della scacchiera: False = dal punto di vista del bianco (in basso),
    # True = dal punto di vista del nero. Si aggiorna solo quando tocca a un umano
    # muovere, così in una partita 1 contro AI la scacchiera resta ferma dal punto di
    # vista dell'unico umano, mentre in una partita 1 contro 1 gira a ogni cambio turno.
    flipped = not player_white and player_black

    score = 0.5
    current_score = score

    while running:
        human_turn = (gs.white_to_move and player_white) or (not gs.white_to_move and player_black)
        if human_turn:
            flipped = not gs.white_to_move

        for e in p.event.get():
            if e.type == p.QUIT:
                running = False
            elif e.type == p.MOUSEBUTTONDOWN:
                if not game_over and human_turn:
                    location = p.mouse.get_pos()
                    screen_col = (location[0] - BORDER_WIDTH) // SQ_SIZE
                    screen_row = (location[1] - BORDER_WIDTH) // SQ_SIZE
                    if 0 <= screen_col < DIMENSION and 0 <= screen_row < DIMENSION:
                        row, col = flip_rc(screen_row, screen_col, flipped)
                        if sq_selected == (row, col):
                            sq_selected = ()
                            player_clicks = []
                        else:
                            sq_selected = [row, col]
                            player_clicks.append(sq_selected)
                        if len(player_clicks) == 2:
                            move = [player_clicks[0], player_clicks[1]]
                            if move in valid_moves:
                                promotion = 'Q'
                                cancelled = False
                                if is_promotion_move(gs, player_clicks[0], player_clicks[1]):
                                    color = gs.board[player_clicks[0][0]][player_clicks[0][1]][0]
                                    promotion = choose_promotion(screen, clock, color)
                                    cancelled = promotion is None
                                if not cancelled:
                                    gs.make_move(Move(player_clicks[0], player_clicks[1], gs.board,
                                                      promotion=promotion))
                                    move_made = True
                                    animate_move_flag = True
                                sq_selected = ()
                                player_clicks = []
                            else:
                                player_clicks = [sq_selected]

            elif e.type == p.KEYDOWN:
                if e.key == p.K_z:
                    gs.undo_move()
                    move_made = True
                    game_over = False

        if not game_over and not human_turn:
            # se l'AI può sottopromuovere, deve vedere anche le promozioni a T, A, C
            ai_moves = gs.get_legal_valid_moves(include_promotions=brain.UNDERPROMOTION)
            ai_move = get_ai_move(ai_moves, gs, Move)
            if ai_move is not None:
                make_ai_move(gs, ai_move)

                move_made = True
                animate_move_flag = True

        if move_made:
            if animate_move_flag:
                if gs.move_log:
                    animate_move(gs.move_log[-1], screen, gs.board, clock, gs, flipped)

            valid_moves = gs.get_legal_valid_moves()
            score = score_board(gs)
            move_made = False

        draw_game_state(screen, gs, valid_moves, sq_selected, flipped)
        current_score = animate_sidebar(screen, current_score, score)

        if gs.is_checkmate():
            game_over = True
            if gs.white_to_move:
                draw_endgame_text(screen, "Black wins")
            else:
                draw_endgame_text(screen, "White wins")

        elif gs.is_stalemate():
            game_over = True
            draw_endgame_text(screen, "Stalemate")

        elif gs.is_draw():
            game_over = True
            draw_endgame_text(screen, "Draw")

        clock.tick(MAX_FPS)
        p.display.flip()

def draw_game_state(screen, gs, valid_moves, sq_selected, flipped):
    draw_board(screen)
    highlight_last_move(screen, gs, flipped)
    highlight_valid_moves(screen, gs, valid_moves, sq_selected, flipped)
    draw_pieces(screen, gs.board, flipped)

def draw_board(screen):
    board_rect = p.Rect(BORDER_WIDTH, BORDER_WIDTH, BOARD_WIDTH, BOARD_HEIGHT)
    p.draw.rect(screen, p.Color("black"), board_rect, BORDER_WIDTH)  # Draw the border around the board
    colors = [p.Color('white'), p.Color(158,203,200)]
    for r in range(DIMENSION):
        for c in range(DIMENSION):
            color = colors[((r + c) % 2)]
            p.draw.rect(screen, color, p.Rect(c * SQ_SIZE + BORDER_WIDTH, r * SQ_SIZE + BORDER_WIDTH, SQ_SIZE, SQ_SIZE))
    # Il motivo a scacchi è simmetrico per rotazione di 180°, quindi non dipende
    # dall'orientamento: non serve nessun parametro `flipped` qui.


def highlight_valid_moves(screen, gs, valid_moves, sq_selected, flipped):
    s = p.Surface((SQ_SIZE, SQ_SIZE))
    if sq_selected:
        r, c = sq_selected
        piece = gs.board[r][c]

        screen_r, screen_c = flip_rc(r, c, flipped)
        rect_position = (screen_c * SQ_SIZE + BORDER_WIDTH, screen_r * SQ_SIZE + BORDER_WIDTH)

        # Highlight selected square
        s.fill((179, 181, 227))
        screen.blit(s, rect_position)
        p.draw.rect(screen, p.Color('gray'), (rect_position[0], rect_position[1], SQ_SIZE, SQ_SIZE), 1)

        # Highlight possible moves
        s.fill((238, 230, 154))
        if (piece[0] == 'w' and gs.white_to_move) or (piece[0] == 'b' and not gs.white_to_move):
            for move in valid_moves:
                if move[0][0] == r and move[0][1] == c:
                    dest_r, dest_c = flip_rc(move[1][0], move[1][1], flipped)
                    rect_position = (dest_c * SQ_SIZE + BORDER_WIDTH, dest_r * SQ_SIZE + BORDER_WIDTH)
                    screen.blit(s, rect_position)
                    p.draw.rect(screen, p.Color('gray'), (rect_position[0], rect_position[1], SQ_SIZE, SQ_SIZE), 1)

    s.fill(p.Color(240, 176, 64))
    if gs.in_check:
        king_r, king_c = flip_rc(gs.king_square[0], gs.king_square[1], flipped)
        rect_position = (king_c * SQ_SIZE + BORDER_WIDTH, king_r * SQ_SIZE + BORDER_WIDTH)
        screen.blit(s, rect_position)
        p.draw.rect(screen, p.Color('gray'), (rect_position[0], rect_position[1], SQ_SIZE, SQ_SIZE), 1)

def highlight_last_move(screen, gs, flipped):
    """Highlights the last move made on the board."""
    if len(gs.move_log) > 0:
        last_move = gs.move_log[-1]
        s = p.Surface((SQ_SIZE, SQ_SIZE))
        s.fill(p.Color(183, 230, 187))

        start_r, start_c = flip_rc(last_move.start_row, last_move.start_col, flipped)
        rect_position = (start_c * SQ_SIZE + BORDER_WIDTH, start_r * SQ_SIZE + BORDER_WIDTH)
        screen.blit(s, rect_position)
        p.draw.rect(screen, p.Color('gray'), (rect_position[0], rect_position[1], SQ_SIZE, SQ_SIZE), 1)

        end_r, end_c = flip_rc(last_move.end_row, last_move.end_col, flipped)
        rect_position = (end_c * SQ_SIZE + BORDER_WIDTH, end_r * SQ_SIZE + BORDER_WIDTH)
        screen.blit(s, rect_position)
        p.draw.rect(screen, p.Color('gray'), (rect_position[0], rect_position[1], SQ_SIZE, SQ_SIZE), 1)


def draw_pieces(screen, board, flipped):
    for r in range(DIMENSION):
        for c in range(DIMENSION):
            piece = board[r][c]
            if piece != "--":
                screen_r, screen_c = flip_rc(r, c, flipped)
                screen.blit(IMAGES[piece], p.Rect(screen_c * SQ_SIZE + BORDER_WIDTH, screen_r * SQ_SIZE + BORDER_WIDTH, SQ_SIZE, SQ_SIZE))

def draw_endgame_text(screen, text):
    font = p.font.SysFont("verdana", int(BOARD_WIDTH / 10), True, False)
    text_surface = font.render(text, True, p.Color(57, 134, 247))
    text_rect = p.Rect(0, 0, BOARD_WIDTH, BOARD_HEIGHT).move(
        BOARD_WIDTH // 2 - text_surface.get_width() // 2 + BORDER_WIDTH,
        BOARD_HEIGHT // 2 - text_surface.get_height() // 2 + BORDER_WIDTH
    )
    screen.blit(text_surface, text_rect)
    text_surface = font.render(text, True, p.Color(240, 176, 64))
    screen.blit(text_surface, text_rect.move(2, 2))

def animate_move(move, screen, board, clock, gs, flipped):
    """Animate a move on the board."""
    colors = [p.Color("white"), p.Color("gray")]

    start_r, start_c = flip_rc(move.start_row, move.start_col, flipped)
    end_r, end_c = flip_rc(move.end_row, move.end_col, flipped)
    delta_row = end_r - start_r
    delta_col = end_c - start_c
    frames_per_square = 5
    frame_count = (abs(delta_row) + abs(delta_col)) * frames_per_square

    for frame in range(frame_count + 1):
        r, c = (start_r + delta_row * frame / frame_count,
                start_c + delta_col * frame / frame_count) if frame_count else (start_r, start_c)
        draw_board(screen)
        draw_pieces(screen, board, flipped)
        # La colorazione a scacchi è simmetrica per rotazione di 180°, quindi la parità
        # (riga+colonna) della casa d'arrivo è la stessa sia in coordinate scacchiera
        # sia in coordinate schermo: non serve trasformarla.
        color = colors[(move.end_row + move.end_col) % 2]
        end_square = p.Rect(end_c * SQ_SIZE + BORDER_WIDTH, end_r * SQ_SIZE + BORDER_WIDTH, SQ_SIZE, SQ_SIZE)
        p.draw.rect(screen, color, end_square)
        if move.pieceCaptured != '--':
            screen.blit(IMAGES[move.pieceCaptured], end_square)
        screen.blit(IMAGES[move.pieceMoved], p.Rect(c * SQ_SIZE + BORDER_WIDTH, r * SQ_SIZE + BORDER_WIDTH, SQ_SIZE, SQ_SIZE))
        p.display.flip()
        clock.tick(60)

def animate_sidebar(screen, current_score, target_score):
    """Animates the sidebar to gradually fill towards the target score."""
    step = 0.01
    if current_score < target_score:
        current_score = min(current_score + step, target_score)
    elif current_score > target_score:
        current_score = max(current_score - step, target_score)
    draw_sidebar(screen, current_score)
    return current_score

def draw_sidebar(screen, score):
    """Draws a sidebar that fills with white and black based on the score."""
    sidebar_rect = p.Rect(BOARD_WIDTH + 2 * BORDER_WIDTH, BORDER_WIDTH, SIDEBAR_WIDTH, BOARD_HEIGHT)
    p.draw.rect(screen, p.Color("gray"), sidebar_rect)

    white_height = int(score * BOARD_HEIGHT)
    black_height = BOARD_HEIGHT - white_height

    if white_height > 0:
        white_rect = p.Rect(BOARD_WIDTH + 2 * BORDER_WIDTH, BORDER_WIDTH, SIDEBAR_WIDTH, white_height)
        p.draw.rect(screen, p.Color("white"), white_rect)
    
    if black_height > 0:
        black_rect = p.Rect(BOARD_WIDTH + 2 * BORDER_WIDTH, BORDER_WIDTH + white_height, SIDEBAR_WIDTH, black_height)
        p.draw.rect(screen, p.Color(158,203,200), black_rect)

if __name__ == "__main__":
    main()