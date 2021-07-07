# This file is an adaptation of checkers (https://github.com/ImparaAI/checkers) by ImparaAI https://impara.ai.
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

from math import ceil
from functools import reduce
import pickle

WHITE = 2
BLACK = 1


class Piece:

    def __init__(self, variant='standard'):
        self.player = None
        self.other_player = None
        self.king = False
        self.captured = False
        self.position = None
        self.board = None
        self.became_king = -100
        self.capture_move_enemies = {}
        self.variant = variant
        self.reset_for_new_board()

    def reset_for_new_board(self):
        self.possible_capture_moves = None
        self.possible_positional_moves = None

    def is_movable(self, captures):
        return (self.get_possible_capture_moves(captures) or self.get_possible_positional_moves()) and not self.captured

    def capture(self):
        self.captured = True
        self.position = None

    def move(self, new_position, move_number):
        self.position = new_position
        was_king = self.king
        self.king = self.king or self.is_on_enemy_home_row()
        if self.king != was_king:
            self.became_king = move_number

    def get_possible_capture_moves(self, captures):
        if self.possible_capture_moves is None:
            self.possible_capture_moves = self.build_possible_capture_moves(captures)

        return self.possible_capture_moves

    def build_possible_capture_moves(self, captures):
        adjacent_enemy_positions = list(filter((lambda position: position in self.board.searcher.get_positions_by_player(self.other_player)), self.get_adjacent_positions(capture=True)))
        capture_move_positions = []

        for enemy_position in adjacent_enemy_positions:
            enemy_piece = self.board.searcher.get_piece_by_position(enemy_position)
            positions_behind_enemy = self.get_position_behind_enemy(enemy_piece, captures)
            for position_behind_enemy in positions_behind_enemy:

                if (position_behind_enemy is not None) and self.board.position_is_open(position_behind_enemy):
                    capture_move_positions.append(position_behind_enemy)
                    self.capture_move_enemies[position_behind_enemy] = enemy_piece

        return self.create_moves_from_new_positions(capture_move_positions)

    def get_position_behind_enemy(self, enemy_piece, captures):
        if not self.king:
            current_row = self.get_row()
            current_column = self.get_column()
            enemy_column = enemy_piece.get_column()
            enemy_row = enemy_piece.get_row()
            if self.variant == 'frisian' or self.variant == 'frysk!':
                if current_row - enemy_row == 2 and current_column - enemy_column == 0:
                    next_row = enemy_row - 2
                    if next_row not in self.board.position_layout:
                        pass
                    else:
                        return [self.board.position_layout.get(next_row, {}).get(current_column)]
                elif current_row - enemy_row == -2 and current_column - enemy_column == 0:
                    next_row = enemy_row + 2
                    if next_row not in self.board.position_layout:
                        pass
                    else:
                        return [self.board.position_layout.get(next_row, {}).get(current_column)]
                elif current_row - enemy_row == 0 and current_column - enemy_column == 1:
                    next_column = enemy_column - 1
                    if next_column not in self.board.position_layout[current_row]:
                        pass
                    else:
                        return [self.board.position_layout.get(current_row, {}).get(next_column)]
                elif current_row - enemy_row == 0 and current_column - enemy_column == -1:
                    next_column = enemy_column + 1
                    if next_column not in self.board.position_layout[current_row]:
                        pass
                    else:
                        return [self.board.position_layout.get(current_row, {}).get(next_column)]

            column_adjustment = -1 if current_row % 2 == 0 else 1
            column_behind_enemy = current_column + column_adjustment if current_column == enemy_column else enemy_column
            row_behind_enemy = enemy_row + (enemy_row - current_row)

            return [self.board.position_layout.get(row_behind_enemy, {}).get(column_behind_enemy)]
        else:
            positions = []
            current_row = self.get_row()
            current_column = self.get_column()
            enemy_column = enemy_piece.get_column()
            enemy_row = enemy_piece.get_row()
            if self.variant == 'frisian' or self.variant == 'frysk!':
                same_row = current_row == enemy_row
                same_column = current_column == enemy_column and (current_row - enemy_row) % 2 == 0
                positions_to_check = []
                if same_row:
                    if current_column > enemy_column:
                        for add_column in range(1, self.board.width):
                            next_column = enemy_column - add_column
                            if next_column not in self.board.position_layout[current_row]:
                                pass
                            else:
                                positions.append(self.board.position_layout.get(current_row, {}).get(next_column))
                            position_to_check = current_column - add_column
                            if position_to_check not in self.board.position_layout[current_row]:
                                pass
                            else:
                                positions_to_check.append(self.board.position_layout.get(current_row, {}).get(position_to_check))
                    else:
                        for add_column in range(1, self.board.width):
                            next_column = enemy_column + add_column
                            if next_column not in self.board.position_layout[current_row]:
                                pass
                            else:
                                positions.append(self.board.position_layout.get(current_row, {}).get(next_column))
                            position_to_check = current_column + add_column
                            if position_to_check not in self.board.position_layout[current_row]:
                                pass
                            else:
                                positions_to_check.append(self.board.position_layout.get(current_row, {}).get(position_to_check))

                    new_positions = []
                    for index, position in enumerate(positions_to_check):
                        enemy_piece_found = False
                        for semi_position in positions_to_check[:index + 1]:
                            piece = self.board.searcher.get_piece_by_position(semi_position)
                            if piece is not None:
                                if piece.player == self.player or enemy_piece_found:
                                    break
                                else:
                                    enemy_piece_found = True
                            elif semi_position in captures:
                                break
                        else:
                            if position in positions:
                                new_positions.append(position)
                            continue
                        break
                    positions = new_positions

                    return positions
                elif same_column:
                    if current_row > enemy_row:
                        for add_row in range(2, self.board.height, 2):
                            next_row = enemy_row - add_row
                            if next_row not in self.board.position_layout:
                                pass
                            else:
                                positions.append(self.board.position_layout.get(next_row, {}).get(current_column))
                            position_to_check = current_row - add_row
                            if position_to_check not in self.board.position_layout:
                                pass
                            else:
                                positions_to_check.append(self.board.position_layout.get(position_to_check, {}).get(current_column))
                    else:
                        for add_row in range(2, self.board.height, 2):
                            next_row = enemy_row + add_row
                            if next_row not in self.board.position_layout:
                                pass
                            else:
                                positions.append(self.board.position_layout.get(next_row, {}).get(current_column))
                            position_to_check = current_row + add_row
                            if position_to_check not in self.board.position_layout:
                                pass
                            else:
                                positions_to_check.append(self.board.position_layout.get(position_to_check, {}).get(current_column))

                    new_positions = []
                    for index, position in enumerate(positions_to_check):
                        enemy_piece_found = False
                        for semi_position in positions_to_check[:index + 1]:
                            piece = self.board.searcher.get_piece_by_position(semi_position)
                            if piece is not None:
                                if piece.player == self.player or enemy_piece_found:
                                    break
                                else:
                                    enemy_piece_found = True
                            elif semi_position in captures:
                                break
                        else:
                            if position in positions:
                                new_positions.append(position)
                            continue
                        break
                    positions = new_positions

                    return positions
            adjacent_positions = self.get_adjacent_positions(capture=True)
            down_direction = enemy_row > current_row
            left_direction = enemy_column < current_column if current_row % 2 == 1 else enemy_column <= current_column

            legal_adjacent_positions = []
            was_king = enemy_piece.king
            enemy_piece.king = True
            for position in enemy_piece.get_adjacent_positions(capture=True):
                column = (position - 1) % self.board.width
                row = self.get_row_from_position(position)
                down_direction_possible = row > enemy_row
                left_direction_possible = column < enemy_column if enemy_row % 2 == 1 else column <= enemy_column
                if down_direction_possible == down_direction and left_direction_possible == left_direction and position in adjacent_positions:
                    legal_adjacent_positions.append(self.board.position_layout.get(row, {}).get(column))
            enemy_piece.king = was_king
            adjacent_positions = legal_adjacent_positions

            positions_to_check = []
            row_to_check = current_row
            position_to_check = self.position
            subtract_for_variant = 1 if self.variant == 'brazilian' or self.variant == 'russian' else 0
            for add in range(1, self.board.height):
                if down_direction and not left_direction and row_to_check % 2 == 1:
                    position_to_check += 5 - subtract_for_variant
                    row_to_check += 1
                elif down_direction and not left_direction and row_to_check % 2 == 0:
                    position_to_check += 6 - subtract_for_variant
                    row_to_check += 1
                elif down_direction and left_direction and row_to_check % 2 == 1:
                    position_to_check += 4 - subtract_for_variant
                    row_to_check += 1
                elif down_direction and left_direction and row_to_check % 2 == 0:
                    position_to_check += 5 - subtract_for_variant
                    row_to_check += 1
                elif not down_direction and not left_direction and row_to_check % 2 == 1:
                    position_to_check -= 5 - subtract_for_variant
                    row_to_check -= 1
                elif not down_direction and not left_direction and row_to_check % 2 == 0:
                    position_to_check -= 4 - subtract_for_variant
                    row_to_check -= 1
                elif not down_direction and left_direction and row_to_check % 2 == 1:
                    position_to_check -= 6 - subtract_for_variant
                    row_to_check -= 1
                elif not down_direction and left_direction and row_to_check % 2 == 0:
                    position_to_check -= 5 - subtract_for_variant
                    row_to_check -= 1
                if self.get_row_from_position(position_to_check) == row_to_check:
                    positions_to_check.append(position_to_check)
                else:
                    break

            for index, position in enumerate(positions_to_check):
                enemy_piece_found = False
                for semi_position in positions_to_check[:index + 1]:
                    piece = self.board.searcher.get_piece_by_position(semi_position)
                    if piece is not None:
                        if piece.player == self.player or enemy_piece_found:
                            break
                        else:
                            enemy_piece_found = True
                    elif semi_position in captures:
                        break
                else:
                    if position in adjacent_positions:
                        positions.append(position)
                    continue
                break
            return positions

    def get_possible_positional_moves(self):
        if self.possible_positional_moves is None:
            self.possible_positional_moves = self.build_possible_positional_moves()

        return self.possible_positional_moves

    def build_possible_positional_moves(self):
        new_positions = list(filter((lambda position: self.board.position_is_open(position)), self.get_adjacent_positions()))

        return self.create_moves_from_new_positions(new_positions)

    def create_moves_from_new_positions(self, new_positions):
        return [[self.position, new_position] for new_position in new_positions]

    def get_adjacent_positions(self, capture=False):
        return self.get_directional_adjacent_positions(forward=True, capture=capture) + (self.get_directional_adjacent_positions(forward=False, capture=capture) if capture or self.king else [])

    def get_column(self):
        return (self.position - 1) % self.board.width

    def get_row(self):
        return self.get_row_from_position(self.position)

    def is_on_enemy_home_row(self):
        return self.get_row() == self.get_row_from_position(1 if self.other_player == BLACK else self.board.position_count)

    def get_row_from_position(self, position):
        return ceil(position / self.board.width) - 1

    def get_directional_adjacent_positions(self, forward, capture=False):
        if not self.king:
            if (self.variant == 'frisian' or self.variant == 'frysk!') and capture:
                # forward=True includes left and up and forward=False includes right and down
                positions = []
                current_row = self.get_row()
                current_column = self.get_column()
                next_row = current_row + ((2 if self.player == BLACK else -2) * (1 if forward else -1))
                next_column = current_column + ((1 if self.player == BLACK else -1) * (1 if forward else -1))
                if next_row not in self.board.position_layout:
                    pass
                else:
                    positions.append(self.board.position_layout[next_row][current_column])
                if next_column not in self.board.position_layout[current_row]:
                    pass
                else:
                    positions.append(self.board.position_layout[current_row][next_column])

                next_row = current_row + ((1 if self.player == BLACK else -1) * (1 if forward else -1))

                if next_row not in self.board.position_layout:
                    pass
                else:

                    next_column_indexes = self.get_next_column_indexes(current_row, self.get_column())

                    positions += [self.board.position_layout[next_row][column_index] for column_index in next_column_indexes]
                return positions
            else:
                current_row = self.get_row()
                next_row = current_row + ((1 if self.player == BLACK else -1) * (1 if forward else -1))

                if next_row not in self.board.position_layout:
                    return []

                next_column_indexes = self.get_next_column_indexes(current_row, self.get_column())

                return [self.board.position_layout[next_row][column_index] for column_index in next_column_indexes]
        else:
            positions = []
            current_row = self.get_row()
            current_column = self.get_column()
            if (self.variant == 'frisian' or self.variant == 'frysk!') and capture:
                for add_column in range(1, self.board.width):
                    next_column = current_column + ((add_column if self.player == BLACK else -add_column) * (1 if forward else -1))
                    if next_column not in self.board.position_layout[current_row]:
                        positions += []
                        continue
                    positions += [self.board.position_layout[current_row][next_column]]
                for add_row in range(2, self.board.height, 2):
                    next_row = current_row + ((add_row if self.player == BLACK else -add_row) * (1 if forward else -1))
                    if next_row not in self.board.position_layout:
                        positions += []
                        continue
                    positions += [self.board.position_layout[next_row][current_column]]

            positions_diagonal_1 = []
            positions_diagonal_2 = []
            for i in range(1, self.board.height):
                next_row = current_row + ((i if self.player == BLACK else -i) * (1 if forward else -1))

                if next_row not in self.board.position_layout:
                    positions += []
                    continue

                next_column_indexes = self.get_next_column_indexes(current_row, current_column, i, True)
                if 0 <= next_column_indexes[0] < self.board.width:
                    positions_diagonal_1.append(self.board.position_layout[next_row][next_column_indexes[0]])
                if 0 <= next_column_indexes[1] < self.board.width:
                    positions_diagonal_2.append(self.board.position_layout[next_row][next_column_indexes[1]])

            for index, position in enumerate(positions_diagonal_1):
                for semi_position in positions_diagonal_1[:index + 1]:
                    piece = self.board.searcher.get_piece_by_position(semi_position)
                    if piece is not None and not capture:
                        break
                else:
                    positions.append(position)
                    continue
                break

            for index, position in enumerate(positions_diagonal_2):
                for semi_position in positions_diagonal_2[:index + 1]:
                    piece = self.board.searcher.get_piece_by_position(semi_position)
                    if piece is not None and not capture:
                        break
                else:
                    positions.append(position)
                    continue
                break

            return positions

    def get_next_column_indexes(self, current_row, current_column, i=1, unfiltered=False):
        column_indexes = [0, 0]
        start_right = True if current_row % 2 == 0 else False
        for semi_i in range(1, i + 1):
            if start_right and semi_i % 2 == 1 or not start_right and semi_i % 2 == 0:
                column_indexes[1] += 1
            else:
                column_indexes[0] -= 1

        column_indexes = list(map(lambda value: value + current_column, column_indexes))

        if unfiltered:
            return column_indexes
        else:
            return filter((lambda column_index: 0 <= column_index < self.board.width), column_indexes)

    def __setattr__(self, name, value):
        super(Piece, self).__setattr__(name, value)

        if name == 'player':
            self.other_player = BLACK if value == WHITE else WHITE


class BoardInitializer:

    def __init__(self, board, fen='startpos'):
        self.board = board
        self.fen = fen

    def initialize(self):
        self.build_position_layout()
        self.set_starting_pieces()

    def build_position_layout(self):
        self.board.position_layout = {}
        position = 1

        for row in range(self.board.height):
            self.board.position_layout[row] = {}

            for column in range(self.board.width):
                self.board.position_layout[row][column] = position
                position += 1

    def set_starting_pieces(self):
        pieces = []
        if self.fen != 'startpos':
            starting = self.fen[0]
            board = self.fen[1:]
            for index, postion in enumerate(board):
                piece = None
                if postion.lower() == 'w':
                    # Index + 1 because enumerate returns 0-49 while the board takes 1-50.
                    piece = self.create_piece(2, index + 1)
                elif postion.lower() == 'b':
                    piece = self.create_piece(1, index + 1)
                if postion == 'W' or postion == 'B':
                    piece.king = True
                if piece:
                    pieces.append(piece)
        else:
            starting_piece_count = self.board.width * self.board.rows_per_user_with_pieces
            player_starting_positions = {
                1: list(range(1, starting_piece_count + 1)),
                2: list(range(self.board.position_count - starting_piece_count + 1, self.board.position_count + 1))
            }

            for key, row in self.board.position_layout.items():
                for key, position in row.items():
                    player_number = 1 if position in player_starting_positions[1] else 2 if position in player_starting_positions[2] else None

                    if player_number:
                        pieces.append(self.create_piece(player_number, position))

        self.board.pieces = pieces

    def create_piece(self, player_number, position):
        piece = Piece(variant=self.board.variant)
        piece.player = player_number
        piece.position = position
        piece.board = self.board

        return piece


class BoardSearcher:

    def build(self, board):
        self.board = board
        self.uncaptured_pieces = list(filter(lambda piece: not piece.captured, board.pieces))
        self.open_positions = []
        self.filled_positions = []
        self.player_positions = {}
        self.player_pieces = {}
        self.position_pieces = {}

        self.build_filled_positions()
        self.build_open_positions()
        self.build_player_positions()
        self.build_player_pieces()
        self.build_position_pieces()

    def build_filled_positions(self):
        self.filled_positions = reduce((lambda open_positions, piece: open_positions + [piece.position]), self.uncaptured_pieces, [])

    def build_open_positions(self):
        self.open_positions = [position for position in range(1, self.board.position_count) if not position in self.filled_positions]

    def build_player_positions(self):
        self.player_positions = {
            1: reduce((lambda positions, piece: positions + ([piece.position] if piece.player == BLACK else [])), self.uncaptured_pieces, []),
            2: reduce((lambda positions, piece: positions + ([piece.position] if piece.player == WHITE else [])), self.uncaptured_pieces, [])
        }

    def build_player_pieces(self):
        self.player_pieces = {
            1: reduce((lambda pieces, piece: pieces + ([piece] if piece.player == BLACK else [])), self.uncaptured_pieces, []),
            2: reduce((lambda pieces, piece: pieces + ([piece] if piece.player == WHITE else [])), self.uncaptured_pieces, [])
        }

    def build_position_pieces(self):
        self.position_pieces = {piece.position: piece for piece in self.uncaptured_pieces}

    def get_pieces_by_player(self, player_number):
        return self.player_pieces[player_number]

    def get_positions_by_player(self, player_number):
        return self.player_positions[player_number]

    def get_pieces_in_play(self):
        return self.player_pieces[self.board.player_turn] if not self.board.piece_requiring_further_capture_moves else [self.board.piece_requiring_further_capture_moves]

    def get_piece_by_position(self, position):
        return self.position_pieces.get(position)


class Board:

    def __init__(self, variant='standard', fen='startpos'):
        if fen != 'startpos':
            self.player_turn = 2 if fen[0].lower() == 'w' else 1
        else:
            self.player_turn = 2
        if variant == 'brazilian' or variant == 'russian':
            self.width = 4
            self.height = 8
        else:
            self.width = 5
            self.height = 10
        self.position_count = self.width * self.height
        if variant == 'frysk!':
            self.rows_per_user_with_pieces = 1
        elif variant == 'brazilian' or variant == 'russian':
            self.rows_per_user_with_pieces = 3
        else:
            self.rows_per_user_with_pieces = 4
        self.position_layout = {}
        self.piece_requiring_further_capture_moves = None
        self.previous_move_was_capture = False
        self.variant = variant
        self.fen = fen
        self.searcher = BoardSearcher()
        BoardInitializer(self, self.fen).initialize()

    def count_movable_player_pieces(self, player_number=1, captures=None):
        if captures is None:
            captures = []
        return reduce((lambda count, piece: count + (1 if piece.is_movable(captures) else 0)), self.searcher.get_pieces_by_player(player_number), 0)

    def get_possible_moves(self, captures):
        capture_moves = self.get_possible_capture_moves(captures)

        return capture_moves if capture_moves else self.get_possible_positional_moves()

    def get_possible_capture_moves(self, captures):
        return reduce((lambda moves, piece: moves + piece.get_possible_capture_moves(captures)), self.searcher.get_pieces_in_play(), [])

    def get_possible_positional_moves(self):
        return reduce((lambda moves, piece: moves + piece.get_possible_positional_moves()), self.searcher.get_pieces_in_play(), [])

    def position_is_open(self, position):
        return not self.searcher.get_piece_by_position(position)

    def create_new_board_from_move(self, move, move_number, captures, return_captured=False):
        new_board = pickle.loads(pickle.dumps(self, -1))  # A lot faster that deepcopy
        enemy_position = None

        if move in self.get_possible_capture_moves(captures):
            if return_captured:
                enemy_position = new_board.perform_capture_move(move, move_number, captures, return_captured=return_captured)
            else:
                new_board.perform_capture_move(move, move_number, captures)
        else:
            new_board.perform_positional_move(move, move_number)

        if return_captured:
            return new_board, enemy_position
        else:
            return new_board

    def perform_capture_move(self, move, move_number, captures, return_captured=False):
        self.previous_move_was_capture = True
        piece = self.searcher.get_piece_by_position(move[0])
        originally_was_king = piece.king
        enemy_piece = piece.capture_move_enemies[move[1]]
        enemy_position = enemy_piece.position
        enemy_piece.capture()
        self.move_piece(move, move_number)
        if not originally_was_king and self.variant != 'russian':
            was_king = piece.king
            piece.king = False
            further_capture_moves_for_piece = [capture_move for capture_move in self.get_possible_capture_moves(captures + [enemy_position]) if move[1] == capture_move[0]]
            if not further_capture_moves_for_piece and was_king:
                piece.king = True
        else:
            further_capture_moves_for_piece = [capture_move for capture_move in self.get_possible_capture_moves(captures + [enemy_position]) if move[1] == capture_move[0]]

        if further_capture_moves_for_piece:
            self.piece_requiring_further_capture_moves = self.searcher.get_piece_by_position(move[1])
        else:
            self.piece_requiring_further_capture_moves = None
            self.switch_turn()
        if return_captured:
            return enemy_position

    def perform_positional_move(self, move, move_number):
        self.previous_move_was_capture = False
        self.move_piece(move, move_number)
        self.switch_turn()

    def switch_turn(self):
        self.player_turn = BLACK if self.player_turn == WHITE else WHITE

    def move_piece(self, move, move_number):
        self.searcher.get_piece_by_position(move[0]).move(move[1], move_number)
        self.pieces = sorted(self.pieces, key=lambda piece: piece.position if piece.position else 0)

    def is_valid_row_and_column(self, row, column):
        if row < 0 or row >= self.height:
            return False

        if column < 0 or column >= self.width:
            return False

        return True

    def __setattr__(self, name, value):
        super(Board, self).__setattr__(name, value)

        if name == 'pieces':
            [piece.reset_for_new_board() for piece in self.pieces]

            self.searcher.build(self)


class Game:

    def __init__(self, variant='standard', fen='startpos'):
        self.variant = variant
        self.initial_fen = fen
        self.initial_hub_fen = self.li_fen_to_hub_fen(self.initial_fen)
        self.board = Board(self.variant, self.initial_hub_fen)
        self.moves = []
        self.move_stack = []
        self.capture_stack = []
        self.not_added_move = []
        self.not_added_capture = []
        self.hub_move_stack = []
        self.consecutive_noncapture_move_limit = 1000  # The original was 40
        self.moves_since_last_capture = 0

    def copy(self):
        # At least 6 times faster than deepcopy
        return pickle.loads(pickle.dumps(self, -1))

    def move(self, move, return_captured=False):
        if move not in self.get_possible_moves():
            raise ValueError('The provided move is not possible')
        turn = self.whose_turn()

        self.board, enemy_position = self.board.create_new_board_from_move(move, len(self.move_stack) + 1, self.not_added_capture, return_captured=True)
        self.moves.append(move)
        self.moves_since_last_capture = 0 if self.board.previous_move_was_capture else self.moves_since_last_capture + 1

        if self.whose_turn() == turn:
            self.not_added_move.append(move)
            self.not_added_capture.append(enemy_position)
        else:
            li_move = self.board_to_li(self.not_added_move + [move])
            self.move_stack.append(li_move)
            self.capture_stack.append(self.not_added_capture + [enemy_position])
            self.hub_move_stack.append(self.li_to_hub(li_move, self.not_added_capture + [enemy_position]))
            self.not_added_move = []
            self.not_added_capture = []

        if return_captured:
            return self, enemy_position
        else:
            return self

    def move_limit_reached(self):
        return self.moves_since_last_capture >= self.consecutive_noncapture_move_limit

    def is_over(self):
        if self.variant == 'breakthrough':
            has_king = False
            for loc in range(1, self.board.position_count + 1):
                piece = self.board.searcher.get_piece_by_position(loc)
                if piece is not None:
                    if piece.king:
                        has_king = True
            return self.move_limit_reached() or not self.legal_moves() or has_king
        return self.move_limit_reached() or not self.legal_moves()

    def get_winner(self):
        if self.whose_turn() == BLACK and not self.board.count_movable_player_pieces(BLACK, self.not_added_capture):
            return WHITE
        elif self.whose_turn() == WHITE and not self.board.count_movable_player_pieces(WHITE, self.not_added_capture):
            return BLACK
        else:
            if self.variant == 'breakthrough':
                for loc in range(1, self.board.position_count + 1):
                    piece = self.board.searcher.get_piece_by_position(loc)
                    if piece is not None:
                        if piece.player == WHITE and piece.king:
                            return WHITE
                        elif piece.player == BLACK and piece.king:
                            return BLACK
                return None
            else:
                return None

    def get_possible_moves(self):
        return self.board.get_possible_moves(self.not_added_capture)

    def whose_turn(self):
        return self.board.player_turn

    def get_fen(self):
        playing = 'W' if self.board.player_turn == WHITE else 'B'
        fen = ''

        for loc in range(1, self.board.position_count + 1):
            piece = self.board.searcher.get_piece_by_position(loc)
            letter = 'e'
            if piece is not None:
                if piece.player == WHITE:
                    letter = 'w'
                else:
                    letter = 'b'
                if piece.king:
                    letter = letter.capitalize()
            fen += letter

        final_fen = playing + fen
        return final_fen

    def get_moves(self):
        """
        Moves are only pseudo-legal. Use legal_moves for legal moves.
        """
        turn = self.whose_turn()
        moves = []
        captured_pieces = []
        for move in self.get_possible_moves():
            game_2 = self.copy()
            _, captures = game_2.move(move, return_captured=True)
            if game_2.whose_turn() == turn:
                more_moves, more_captures = game_2.get_moves()
                for semi_move, semi_capture in zip(more_moves, more_captures):
                    moves.append([move] + semi_move)
                    captured_pieces.append([captures] + semi_capture)
            else:
                moves.append([move])
                captured_pieces.append([captures])
        return moves, captured_pieces

    def legal_moves(self):
        if self.variant == 'frisian' or self.variant == 'frysk!':
            king_value = 1.501
            man_value = 1
            moves, captures = self.get_moves()
            if not moves:
                return moves, captures
            values = []
            for capture in captures:
                value = 0
                for position in capture:
                    if position is None:
                        continue
                    piece = self.board.searcher.get_piece_by_position(position)
                    value += king_value if piece.king else man_value
                values.append(value)
            max_value = max(values)
            moves_pseudo_legal = []
            captures_pseudo_legal = []
            for move, capture, value in zip(moves, captures, values):
                if value == max_value:
                    moves_pseudo_legal.append(move)
                    captures_pseudo_legal.append(capture)
            move_with_king = bool(list(filter(lambda move: self.board.searcher.get_piece_by_position(move[0][0]).king, moves_pseudo_legal)))
            if move_with_king:
                moves_pseudo_legal_2 = []
                captures_pseudo_legal_2 = []
                for move, capture in zip(moves_pseudo_legal, captures_pseudo_legal):
                    if self.board.searcher.get_piece_by_position(move[0][0]).king and capture[0] is not None or capture[0] is None:
                        moves_pseudo_legal_2.append(move)
                        captures_pseudo_legal_2.append(capture)
            else:
                moves_pseudo_legal_2 = moves_pseudo_legal
                captures_pseudo_legal_2 = captures_pseudo_legal

            has_man = False
            for loc in range(1, self.board.position_count + 1):
                piece = self.board.searcher.get_piece_by_position(loc)
                if piece and not piece.king and piece.player == self.whose_turn():
                    has_man = True

            if has_man and len(self.move_stack) >= 6:
                last_3_moves = [self.move_stack[-6], self.move_stack[-4], self.move_stack[-2]]
                last_3_moves_same_piece = last_3_moves[0][-2:] == last_3_moves[1][:2] and last_3_moves[1][-2:] == last_3_moves[2][:2]
                was_a_capture = bool(list(filter(lambda captures: captures[0] is not None, [self.capture_stack[-6], self.capture_stack[-4], self.capture_stack[-2]])))
                piece = self.board.searcher.get_piece_by_position(int(last_3_moves[-1][-2:]))
                if piece is None:  # It is None when the piece was captured
                    is_king = False
                    is_king_for_at_least_3_moves = True
                else:
                    is_king = piece.king
                    is_king_for_at_least_3_moves = len(self.move_stack) - piece.became_king >= 6
                if is_king and last_3_moves_same_piece and not was_a_capture and is_king_for_at_least_3_moves:
                    piece_not_allowed = int(last_3_moves[2][-2:])
                    moves_legal = []
                    captures_legal = []
                    for move, capture in zip(moves_pseudo_legal_2, captures_pseudo_legal_2):
                        if move[0][0] != piece_not_allowed or capture[0] is not None:
                            moves_legal.append(move)
                            captures_legal.append(capture)
                else:
                    moves_legal = moves_pseudo_legal_2
                    captures_legal = captures_pseudo_legal_2
            else:
                moves_legal = moves_pseudo_legal_2
                captures_legal = captures_pseudo_legal_2
        elif self.variant == 'russian':
            return self.get_moves()
        else:
            moves, captures = self.get_moves()
            if not moves:
                return moves, captures
            max_len_key = max(list(map(len, moves)))
            moves_legal = []
            captures_legal = []
            for move, capture in zip(moves, captures):
                if len(move) == max_len_key:
                    moves_legal.append(move)
                    captures_legal.append(capture)
        return moves_legal, captures_legal

    def make_len_2(self, move):
        return f'0{move}' if len(str(move)) == 1 else str(move)

    def make_len_4(self, move1, move2):
        return self.make_len_2(move1) + self.make_len_2(move2)

    def board_to_li_old(self, move):
        return self.make_len_4(move[0][0], move[-1][1])

    def board_to_li(self, move):
        final_move = self.make_len_2(move[0][0])
        for semi_move in move:
            final_move += self.make_len_2(semi_move[1])
        return final_move

    def push_move(self, move):
        self.move([int(move[:2]), int(move[2:4])])

    def sort_captures(self, captures):
        """
        This function is because hub engines returns the captures in alphabetical order
        (e.g. for the move 231201 scan returns 23x01x07x18 instead of 23x01x18x07)
        """
        captures = list(map(self.make_len_2, captures))
        captures.sort()
        captures = ''.join(captures)
        return captures

    def hub_to_li_board(self, move):
        possible_moves, possible_captures = self.legal_moves()
        moves_li_board = {}
        for possible_move, possible_capture in zip(possible_moves, possible_captures):
            if possible_capture[0] is None:
                possible_capture = []
            li_move = self.board_to_li_old(possible_move) + self.sort_captures(possible_capture)
            moves_li_board[li_move] = possible_move
        board_move = moves_li_board[move]
        api_move = []
        for semi_move in board_move:
            api_move.append(self.board_to_li([semi_move]))
        return api_move, board_move

    def li_to_hub(self, move, captures):
        if captures[0] is None:
            captures = []
        hub_move = move[:2] + move[-2:] + self.sort_captures(captures)
        if captures:
            hub_move = 'x'.join([hub_move[i:i + 2] for i in range(0, len(hub_move), 2)])
        else:
            hub_move = hub_move[:2] + '-' + hub_move[2:]
        return hub_move

    def board_to_li_api(self, move):
        moves = []
        for semi_move in move:
            moves.append(self.make_len_4(semi_move[0], semi_move[1]))
        return moves

    def li_api_to_li_one(self, move):
        new_move = move[0][:2]
        for semi_move in move:
            new_move += semi_move[2:]
        return new_move

    def board_to_pdn(self, move):
        possible_moves, possible_captures = self.legal_moves()
        starts_endings = []
        for possible_move in possible_moves:
            starts_endings.append(self.make_len_4(possible_move[0][0], possible_move[-1][1]))
        if starts_endings.count(self.make_len_4(move[0][0], move[-1][1])) == 1:
            index = possible_moves.index(move)
            captures = possible_captures[index]
            if captures[0] is not None:
                return self.make_len_2(str(move[0][0])) + 'x' + self.make_len_2(str(move[-1][1]))
            else:
                return self.make_len_2(str(move[0][0])) + '-' + self.make_len_2(str(move[-1][1]))
        else:
            li_move = self.board_to_li(move)
            li_move = [li_move[i:i + 2] for i in range(0, len(li_move), 2)]
            return 'x'.join(li_move)

    def board_to_hub(self, move):
        possible_moves, possible_captures = self.legal_moves()
        li_move = self.board_to_li(move)
        moves_to_captures = {}
        for possible_move, possible_capture in zip(possible_moves, possible_captures):
            moves_to_captures[self.board_to_li(possible_move)] = possible_capture
        captures = moves_to_captures[li_move]
        return self.li_to_hub(li_move, captures)

    def li_fen_to_hub_fen(self, li_fen):
        if li_fen == 'startpos' and self.variant == 'frysk!':
            return 'Wbbbbbeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeewwwww'
        elif li_fen == 'startpos' and (self.variant == 'brazilian' or self.variant == 'russian'):
            return 'Wbbbbbbbbbbbbeeeeeeeewwwwwwwwwwww'
        elif li_fen == 'startpos':
            return 'Wbbbbbbbbbbbbbbbbbbbbeeeeeeeeeewwwwwwwwwwwwwwwwwwww'
        fen = ''
        li_fen = li_fen.split(':')
        fen += li_fen[0]
        white_pieces = li_fen[1][1:].split(',')
        black_pieces = li_fen[2][1:].split(',')

        if self.variant == 'brazilian' or self.variant == 'russian':
            position_count = 32
        else:
            position_count = 50

        for index in range(1, position_count + 1):
            str_index = str(index)
            if str_index in white_pieces:
                fen += 'w'
            elif 'K' + str_index in white_pieces:
                fen += 'W'
            elif str_index in black_pieces:
                fen += 'b'
            elif 'K' + str_index in black_pieces:
                fen += 'B'
            else:
                fen += 'e'
        return fen
