#!/usr/bin/env python3
"""
Terminal Snake game implemented with Python's curses module.

Controls:
- Arrow keys or WASD to move
- P to pause/resume
- Q to quit during a game
- On game over: R to restart, Q to quit

Run:
  python3 snake.py

This game adapts to your terminal size. For a comfortable experience,
use a terminal of at least ~24 rows by ~60 columns.
"""
from __future__ import annotations

import curses
import random
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class Point:
    row: int
    col: int


class Direction:
    UP: Point = Point(-1, 0)
    DOWN: Point = Point(1, 0)
    LEFT: Point = Point(0, -1)
    RIGHT: Point = Point(0, 1)


KEYS_TO_DIRECTION = {
    curses.KEY_UP: Direction.UP,
    curses.KEY_DOWN: Direction.DOWN,
    curses.KEY_LEFT: Direction.LEFT,
    curses.KEY_RIGHT: Direction.RIGHT,
    ord('w'): Direction.UP,
    ord('W'): Direction.UP,
    ord('s'): Direction.DOWN,
    ord('S'): Direction.DOWN,
    ord('a'): Direction.LEFT,
    ord('A'): Direction.LEFT,
    ord('d'): Direction.RIGHT,
    ord('D'): Direction.RIGHT,
}


class SnakeGame:
    """Encapsulates all game logic and rendering for Snake."""

    BORDER_THICKNESS: int = 1
    MIN_ROWS: int = 18
    MIN_COLS: int = 40

    COLOR_PAIR_SNAKE: int = 1
    COLOR_PAIR_APPLE: int = 2
    COLOR_PAIR_HEADER: int = 3
    COLOR_PAIR_GAMEOVER: int = 4

    def __init__(self, stdscr: "curses._CursesWindow") -> None:
        self.stdscr = stdscr
        curses.curs_set(0)
        curses.noecho()
        curses.cbreak()
        self.stdscr.keypad(True)

        self._initialize_colors()

        total_rows, total_cols = self.stdscr.getmaxyx()
        if total_rows < self.MIN_ROWS + 2 or total_cols < self.MIN_COLS:
            self._render_resize_message(total_rows, total_cols)
            self._wait_for_resize()
            total_rows, total_cols = self.stdscr.getmaxyx()

        header_rows = 1
        footer_rows = 1
        self.header_height = header_rows
        self.footer_height = footer_rows

        board_rows = max(self.MIN_ROWS, total_rows - (header_rows + footer_rows))
        board_cols = max(self.MIN_COLS, total_cols)

        self.header_win = curses.newwin(header_rows, board_cols, 0, 0)
        self.footer_win = curses.newwin(footer_rows, board_cols, total_rows - footer_rows, 0)
        self.game_win = curses.newwin(board_rows, board_cols, header_rows, 0)

        self.game_win.keypad(True)
        self.game_win.nodelay(True)

        self.board_rows = board_rows
        self.board_cols = board_cols

        self.score: int = 0
        self.snake: List[Point] = []
        self.direction: Point = Direction.RIGHT
        self.pending_direction: Optional[Point] = None
        self.food: Optional[Point] = None
        self.paused: bool = False
        self.game_over: bool = False

        self._reset_state()

    def _initialize_colors(self) -> None:
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            # Snake: green
            curses.init_pair(self.COLOR_PAIR_SNAKE, curses.COLOR_GREEN, -1)
            # Apple: red
            curses.init_pair(self.COLOR_PAIR_APPLE, curses.COLOR_RED, -1)
            # Header/footer: cyan
            curses.init_pair(self.COLOR_PAIR_HEADER, curses.COLOR_CYAN, -1)
            # Game over: yellow on red if available
            curses.init_pair(self.COLOR_PAIR_GAMEOVER, curses.COLOR_YELLOW, curses.COLOR_RED)

    def _render_resize_message(self, rows: int, cols: int) -> None:
        self.stdscr.clear()
        message_lines = [
            "Terminal too small for Snake.",
            f"Current size: {rows}x{cols}",
            f"Minimum size: {self.MIN_ROWS + 2}x{self.MIN_COLS}",
            "Resize the terminal and press any key...",
        ]
        start_row = max(0, rows // 2 - len(message_lines) // 2)
        for i, line in enumerate(message_lines):
            col = max(0, (cols - len(line)) // 2)
            try:
                self.stdscr.addstr(start_row + i, col, line)
            except curses.error:
                pass
        self.stdscr.refresh()

    def _wait_for_resize(self) -> None:
        self.stdscr.nodelay(False)
        self.stdscr.getch()
        self.stdscr.nodelay(True)

    def _reset_state(self) -> None:
        self.score = 0
        center_row = self.board_rows // 2
        center_col = self.board_cols // 2
        self.snake = [
            Point(center_row, center_col + 1),
            Point(center_row, center_col),
            Point(center_row, center_col - 1),
        ]
        self.direction = Direction.RIGHT
        self.pending_direction = None
        self.food = self._spawn_food()
        self.paused = False
        self.game_over = False

    def _spawn_food(self) -> Point:
        occupied = set(self.snake)
        while True:
            candidate = Point(
                random.randint(self.BORDER_THICKNESS, self.board_rows - self.BORDER_THICKNESS - 1),
                random.randint(self.BORDER_THICKNESS, self.board_cols - self.BORDER_THICKNESS - 1),
            )
            if candidate not in occupied:
                return candidate

    def _render_header(self) -> None:
        self.header_win.erase()
        header_text = f"Snake | Score: {self.score}  |  P: Pause  Q: Quit"
        try:
            if curses.has_colors():
                self.header_win.attron(curses.color_pair(self.COLOR_PAIR_HEADER))
            self.header_win.addstr(0, 1, header_text[: self.board_cols - 2])
        except curses.error:
            pass
        finally:
            if curses.has_colors():
                self.header_win.attroff(curses.color_pair(self.COLOR_PAIR_HEADER))
        self.header_win.noutrefresh()

    def _render_footer(self) -> None:
        self.footer_win.erase()
        if self.paused:
            footer_text = "Paused - Press P to resume"
        else:
            footer_text = "Use Arrow keys or WASD. Eat apples, avoid walls and yourself."
        col = max(1, (self.board_cols - len(footer_text)) // 2)
        try:
            if curses.has_colors():
                self.footer_win.attron(curses.color_pair(self.COLOR_PAIR_HEADER))
            self.footer_win.addstr(0, col, footer_text[: self.board_cols - col - 1])
        except curses.error:
            pass
        finally:
            if curses.has_colors():
                self.footer_win.attroff(curses.color_pair(self.COLOR_PAIR_HEADER))
        self.footer_win.noutrefresh()

    def _render_board(self) -> None:
        self.game_win.erase()
        try:
            self.game_win.border()
        except curses.error:
            pass

        for index, segment in enumerate(self.snake):
            try:
                if index == 0:
                    ch = '@'
                else:
                    ch = '#'
                if curses.has_colors():
                    self.game_win.attron(curses.color_pair(self.COLOR_PAIR_SNAKE))
                self.game_win.addch(segment.row, segment.col, ch)
            except curses.error:
                pass
            finally:
                if curses.has_colors():
                    self.game_win.attroff(curses.color_pair(self.COLOR_PAIR_SNAKE))

        if self.food is not None:
            try:
                if curses.has_colors():
                    self.game_win.attron(curses.color_pair(self.COLOR_PAIR_APPLE))
                self.game_win.addch(self.food.row, self.food.col, 'O')
            except curses.error:
                pass
            finally:
                if curses.has_colors():
                    self.game_win.attroff(curses.color_pair(self.COLOR_PAIR_APPLE))

        self.game_win.noutrefresh()

    def _opposite(self, a: Point, b: Point) -> bool:
        return a.row == -b.row and a.col == -b.col

    def _apply_input(self, ch: int) -> Optional[str]:
        if ch in (ord('q'), ord('Q')):
            return 'quit'
        if ch in (ord('p'), ord('P')):
            self.paused = not self.paused
            return 'paused'
        new_direction = KEYS_TO_DIRECTION.get(ch)
        if new_direction is not None and not self._opposite(new_direction, self.direction):
            self.pending_direction = new_direction
        return None

    def _next_head(self) -> Point:
        move = self.pending_direction or self.direction
        return Point(self.snake[0].row + move.row, self.snake[0].col + move.col)

    def _is_collision(self, point: Point) -> bool:
        if (
            point.row <= 0
            or point.row >= self.board_rows - 1
            or point.col <= 0
            or point.col >= self.board_cols - 1
        ):
            return True
        return point in self.snake

    def _tick_duration_ms(self) -> int:
        growth = max(0, len(self.snake) - 3)
        speedup_steps = growth // 4
        return max(45, 140 - 7 * speedup_steps)

    def _game_over_screen(self) -> str:
        message_title = "GAME OVER"
        message_info = f"Score: {self.score}"
        message_hint = "Press R to restart or Q to quit"
        center_row = self.header_height + self.board_rows // 2
        center_col = self.board_cols // 2

        def draw_line(text: str, row_offset: int) -> None:
            col = max(0, center_col - len(text) // 2)
            try:
                if curses.has_colors():
                    self.stdscr.attron(curses.color_pair(self.COLOR_PAIR_GAMEOVER))
                self.stdscr.addstr(center_row + row_offset, col, text)
            except curses.error:
                pass
            finally:
                if curses.has_colors():
                    self.stdscr.attroff(curses.color_pair(self.COLOR_PAIR_GAMEOVER))

        draw_line(message_title, -1)
        draw_line(message_info, 0)
        draw_line(message_hint, 1)
        self.stdscr.refresh()

        self.stdscr.nodelay(False)
        choice = 'quit'
        while True:
            ch = self.stdscr.getch()
            if ch in (ord('r'), ord('R')):
                choice = 'restart'
                break
            if ch in (ord('q'), ord('Q')):
                choice = 'quit'
                break
        self.stdscr.nodelay(True)
        return choice

    def play(self) -> None:
        while True:
            self._reset_state()
            loop_result = self._play_single_round()
            if loop_result == 'quit':
                break

    def _play_single_round(self) -> str:
        last_render_time = 0.0
        while True:
            self._render_header()
            self._render_footer()
            self._render_board()
            curses.doupdate()

            if self.paused:
                self.game_win.timeout(-1)
                ch = self.game_win.getch()
                action = self._apply_input(ch)
                if action == 'quit':
                    return 'quit'
                continue

            tick_ms = self._tick_duration_ms()
            self.game_win.timeout(tick_ms)
            ch = self.game_win.getch()
            action = self._apply_input(ch)
            if action == 'quit':
                return 'quit'

            if self.pending_direction is not None:
                self.direction = self.pending_direction
                self.pending_direction = None

            new_head = self._next_head()
            if self._is_collision(new_head):
                self.game_over = True
                self._render_board()
                curses.doupdate()
                return self._game_over_screen()

            self.snake.insert(0, new_head)
            if self.food is not None and new_head == self.food:
                self.score += 1
                self.food = self._spawn_food()
            else:
                self.snake.pop()

            now = time.time()
            if now - last_render_time > 0.2:
                last_render_time = now



def main(stdscr: "curses._CursesWindow") -> None:
    game = SnakeGame(stdscr)
    game.play()


if __name__ == "__main__":
    curses.wrapper(main)
