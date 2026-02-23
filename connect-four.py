#!/usr/bin/env python3
"""
Connect Four — Joel vs Meridian
A classic game on the desktop. Joel plays Red, Meridian plays Blue.
Meridian uses a minimax AI with alpha-beta pruning.

Built by Meridian, Feb 20 2026.
"""

import tkinter as tk
from tkinter import messagebox
import random
import threading

# Board dimensions
ROWS = 6
COLS = 7
CELL_SIZE = 80
PADDING = 10

# Colors
BG = "#1a1a2e"
BOARD_COLOR = "#0f3460"
EMPTY_COLOR = "#16213e"
JOEL_COLOR = "#e74c3c"      # Red
MERIDIAN_COLOR = "#3498db"   # Blue
HIGHLIGHT = "#f1c40f"        # Yellow highlight
TEXT_COLOR = "#ecf0f1"

# Players
JOEL = 1
MERIDIAN = 2
EMPTY = 0


class ConnectFour(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Connect Four — Joel vs Meridian")
        self.configure(bg=BG)
        self.resizable(False, False)

        self.board = [[EMPTY] * COLS for _ in range(ROWS)]
        self.current_player = JOEL  # Joel goes first
        self.game_over = False
        self.hover_col = -1

        self._build_ui()
        self._draw_board()

    def _build_ui(self):
        # Header
        header = tk.Frame(self, bg=BG)
        header.pack(fill=tk.X, padx=10, pady=(10, 0))

        self.status_label = tk.Label(
            header, text="Joel's turn (Red)",
            font=("Monospace", 16, "bold"), fg=JOEL_COLOR, bg=BG
        )
        self.status_label.pack(side=tk.LEFT)

        self.score_label = tk.Label(
            header, text="Drop a disc!",
            font=("Monospace", 11), fg=TEXT_COLOR, bg=BG
        )
        self.score_label.pack(side=tk.RIGHT)

        # Canvas for the board
        canvas_width = COLS * CELL_SIZE + 2 * PADDING
        canvas_height = ROWS * CELL_SIZE + 2 * PADDING
        self.canvas = tk.Canvas(
            self, width=canvas_width, height=canvas_height,
            bg=BOARD_COLOR, highlightthickness=0
        )
        self.canvas.pack(padx=10, pady=10)
        self.canvas.bind("<Motion>", self._on_hover)
        self.canvas.bind("<Button-1>", self._on_click)

        # Footer with buttons
        footer = tk.Frame(self, bg=BG)
        footer.pack(fill=tk.X, padx=10, pady=(0, 10))

        tk.Button(
            footer, text="New Game", font=("Monospace", 10),
            bg=BOARD_COLOR, fg=TEXT_COLOR, relief=tk.FLAT,
            command=self._new_game, padx=10, pady=5
        ).pack(side=tk.LEFT)

        tk.Label(
            footer, text="Joel=Red  Meridian=Blue",
            font=("Monospace", 9), fg="#666", bg=BG
        ).pack(side=tk.RIGHT)

    def _draw_board(self):
        self.canvas.delete("all")
        for r in range(ROWS):
            for c in range(COLS):
                x = PADDING + c * CELL_SIZE + CELL_SIZE // 2
                y = PADDING + r * CELL_SIZE + CELL_SIZE // 2
                radius = CELL_SIZE // 2 - 6

                if self.board[r][c] == JOEL:
                    color = JOEL_COLOR
                elif self.board[r][c] == MERIDIAN:
                    color = MERIDIAN_COLOR
                else:
                    color = EMPTY_COLOR

                self.canvas.create_oval(
                    x - radius, y - radius, x + radius, y + radius,
                    fill=color, outline=BOARD_COLOR, width=2
                )

        # Hover indicator
        if self.hover_col >= 0 and not self.game_over and self.current_player == JOEL:
            x = PADDING + self.hover_col * CELL_SIZE + CELL_SIZE // 2
            y = PADDING // 2
            self.canvas.create_oval(
                x - 15, y - 5, x + 15, y + 15,
                fill=JOEL_COLOR, outline=""
            )

    def _on_hover(self, event):
        col = (event.x - PADDING) // CELL_SIZE
        if 0 <= col < COLS:
            self.hover_col = col
        else:
            self.hover_col = -1
        self._draw_board()

    def _on_click(self, event):
        if self.game_over or self.current_player != JOEL:
            return

        col = (event.x - PADDING) // CELL_SIZE
        if 0 <= col < COLS:
            if self._drop_piece(col, JOEL):
                self._draw_board()
                if self._check_winner(JOEL):
                    self._end_game("Joel wins!")
                    return
                if self._is_full():
                    self._end_game("Draw!")
                    return
                self.current_player = MERIDIAN
                self.status_label.config(text="Meridian is thinking...", fg=MERIDIAN_COLOR)
                self.score_label.config(text="")
                self.update()
                # Meridian plays in a separate thread
                threading.Thread(target=self._meridian_move, daemon=True).start()

    def _drop_piece(self, col, player):
        for r in range(ROWS - 1, -1, -1):
            if self.board[r][col] == EMPTY:
                self.board[r][col] = player
                return True
        return False

    def _undo_piece(self, col):
        for r in range(ROWS):
            if self.board[r][col] != EMPTY:
                self.board[r][col] = EMPTY
                return

    def _check_winner(self, player):
        # Horizontal
        for r in range(ROWS):
            for c in range(COLS - 3):
                if all(self.board[r][c + i] == player for i in range(4)):
                    return True
        # Vertical
        for r in range(ROWS - 3):
            for c in range(COLS):
                if all(self.board[r + i][c] == player for i in range(4)):
                    return True
        # Diagonal down-right
        for r in range(ROWS - 3):
            for c in range(COLS - 3):
                if all(self.board[r + i][c + i] == player for i in range(4)):
                    return True
        # Diagonal up-right
        for r in range(3, ROWS):
            for c in range(COLS - 3):
                if all(self.board[r - i][c + i] == player for i in range(4)):
                    return True
        return False

    def _is_full(self):
        return all(self.board[0][c] != EMPTY for c in range(COLS))

    def _get_valid_moves(self):
        return [c for c in range(COLS) if self.board[0][c] == EMPTY]

    def _evaluate_window(self, window, player):
        opponent = JOEL if player == MERIDIAN else MERIDIAN
        score = 0
        count = window.count(player)
        empty = window.count(EMPTY)
        opp_count = window.count(opponent)

        if count == 4:
            score += 100
        elif count == 3 and empty == 1:
            score += 5
        elif count == 2 and empty == 2:
            score += 2

        if opp_count == 3 and empty == 1:
            score -= 4

        return score

    def _evaluate_board(self, player):
        score = 0

        # Center column preference
        center = [self.board[r][COLS // 2] for r in range(ROWS)]
        score += center.count(player) * 3

        # Horizontal
        for r in range(ROWS):
            for c in range(COLS - 3):
                window = [self.board[r][c + i] for i in range(4)]
                score += self._evaluate_window(window, player)

        # Vertical
        for r in range(ROWS - 3):
            for c in range(COLS):
                window = [self.board[r + i][c] for i in range(4)]
                score += self._evaluate_window(window, player)

        # Diagonals
        for r in range(ROWS - 3):
            for c in range(COLS - 3):
                window = [self.board[r + i][c + i] for i in range(4)]
                score += self._evaluate_window(window, player)
        for r in range(3, ROWS):
            for c in range(COLS - 3):
                window = [self.board[r - i][c + i] for i in range(4)]
                score += self._evaluate_window(window, player)

        return score

    def _minimax(self, depth, alpha, beta, maximizing):
        valid_moves = self._get_valid_moves()

        if self._check_winner(MERIDIAN):
            return None, 100000
        if self._check_winner(JOEL):
            return None, -100000
        if not valid_moves or depth == 0:
            return None, self._evaluate_board(MERIDIAN)

        if maximizing:
            value = float('-inf')
            best_col = random.choice(valid_moves)
            for col in valid_moves:
                self._drop_piece(col, MERIDIAN)
                _, new_score = self._minimax(depth - 1, alpha, beta, False)
                self._undo_piece(col)
                if new_score > value:
                    value = new_score
                    best_col = col
                alpha = max(alpha, value)
                if alpha >= beta:
                    break
            return best_col, value
        else:
            value = float('inf')
            best_col = random.choice(valid_moves)
            for col in valid_moves:
                self._drop_piece(col, JOEL)
                _, new_score = self._minimax(depth - 1, alpha, beta, True)
                self._undo_piece(col)
                if new_score < value:
                    value = new_score
                    best_col = col
                beta = min(beta, value)
                if alpha >= beta:
                    break
            return best_col, value

    def _meridian_move(self):
        # Think for a moment (AI should feel deliberate)
        import time
        time.sleep(0.8)

        col, score = self._minimax(5, float('-inf'), float('inf'), True)

        if col is not None:
            self._drop_piece(col, MERIDIAN)
            self.after(0, self._after_meridian_move, col)

    def _after_meridian_move(self, col):
        self._draw_board()
        if self._check_winner(MERIDIAN):
            self._end_game("Meridian wins!")
            return
        if self._is_full():
            self._end_game("Draw!")
            return
        self.current_player = JOEL
        self.status_label.config(text="Joel's turn (Red)", fg=JOEL_COLOR)
        self.score_label.config(text=f"Meridian played column {col + 1}")

    def _end_game(self, message):
        self.game_over = True
        self.status_label.config(text=message, fg=HIGHLIGHT)
        self.score_label.config(text="Click 'New Game' to play again")
        self._draw_board()

    def _new_game(self):
        self.board = [[EMPTY] * COLS for _ in range(ROWS)]
        self.current_player = JOEL
        self.game_over = False
        self.hover_col = -1
        self.status_label.config(text="Joel's turn (Red)", fg=JOEL_COLOR)
        self.score_label.config(text="Drop a disc!")
        self._draw_board()


if __name__ == "__main__":
    game = ConnectFour()
    game.mainloop()
