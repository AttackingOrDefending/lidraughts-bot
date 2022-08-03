import os
import draughts
import draughts.engine
import subprocess
import logging
from enum import Enum

logger = logging.getLogger(__name__)


def create_engine(config, variant, initial_time):
    cfg = config["engine"]
    engine_path = os.path.join(cfg["dir"], cfg["name"])
    engine_working_dir = cfg.get("working_dir") or os.getcwd()
    engine_type = cfg.get("protocol")
    engine_options = cfg.get("engine_options")
    draw_or_resign = cfg.get("draw_or_resign") or {}
    commands = [engine_path, cfg["engine_argument"]]
    if engine_options:
        for k, v in engine_options.items():
            commands.append(f"--{k}={v}")

    stderr = None if cfg.get("silence_stderr", False) else subprocess.DEVNULL

    if engine_type == "hub":
        Engine = HubEngine
    elif engine_type == "dxp":
        Engine = DXPEngine
    elif engine_type == "cb":
        Engine = CBEngine
    elif engine_type == "homemade":
        Engine = getHomemadeEngine(cfg["name"])
    else:
        raise ValueError(
            f"    Invalid engine type: {engine_type}. Expected hub, dxp, cb, or homemade.")
    options = cfg.get(f"{engine_type}_options") or {}
    options["variant"] = variant
    options["initial-time"] = initial_time
    logger.debug(f"Starting engine: {' '.join(commands)}")
    return Engine(commands, options, stderr, draw_or_resign, cwd=engine_working_dir)


class Termination(str, Enum):
    MATE = "mate"
    TIMEOUT = "outoftime"
    RESIGN = "resign"
    ABORT = "aborted"
    DRAW = "draw"


class GameEnding(str, Enum):
    WHITE_WINS = "1-0"
    BLACK_WINS = "0-1"
    DRAW = "1/2-1/2"
    INCOMPLETE = "*"


def translate_termination(termination, board, winner_color):
    if termination == Termination.MATE:
        return f"{winner_color.title()} mates"
    elif termination == Termination.TIMEOUT:
        return "Time forfeiture"
    elif termination == Termination.RESIGN:
        resigner = "black" if winner_color == "white" else "white"
        return f"{resigner.title()} resigns"
    elif termination == Termination.ABORT:
        return "Game aborted"
    elif termination == Termination.DRAW:
        if board.is_fifty_moves():
            return "50-move rule"
        elif board.is_repetition():
            return "Threefold repetition"
        else:
            return "Draw by agreement"
    elif termination:
        return termination
    else:
        return ""


PONDERPV_CHARACTERS = 12  # the length of ", ponderpv: "
MAX_CHAT_MESSAGE_LEN = 140  # maximum characters in a chat message


class EngineWrapper:
    def __init__(self, options, draw_or_resign):
        self.scores = []
        self.draw_or_resign = draw_or_resign
        self.go_commands = options.pop("go_commands", {}) or {}
        self.last_move_info = {}
        self.move_commentary = []
        self.comment_start_index = None

    def search_for(self, board, movetime, draw_offered):
        return self.search(board, draughts.engine.Limit(movetime=movetime / 1000), False, draw_offered)

    def first_search(self, board, movetime, draw_offered):
        # No pondering after the first move since a different clock is used afterwards.
        return self.search_for(board, movetime, draw_offered)

    def search_with_ponder(self, board, wtime, btime, winc, binc, ponder, draw_offered):
        if board.whose_turn() == draughts.WHITE:
            time = wtime
            inc = winc
        else:
            time = btime
            inc = binc
        time_limit = draughts.engine.Limit(time=time / 1000,
                                           inc=inc / 1000)
        return self.search(board, time_limit, ponder, draw_offered)

    def add_go_commands(self, time_limit):
        movetime = self.go_commands.get("movetime")
        if movetime is not None:
            movetime_sec = float(movetime) / 1000
            if time_limit.movetime is None or time_limit.movetime > movetime_sec:
                time_limit.movetime = movetime_sec
        time_limit.depth = self.go_commands.get("depth")
        time_limit.nodes = self.go_commands.get("nodes")
        return time_limit

    def offer_draw_or_resign(self, result, board):
        def actual(score):
            if "cp" in score:
                return score.get("cp", float("nan"))
            else:
                win = score.get("win", float("nan"))
                if win > 0:
                    return 10000 - win
                else:
                    return -10000 - win

        can_offer_draw = self.draw_or_resign.get("offer_draw_enabled", False)
        draw_offer_moves = self.draw_or_resign.get("offer_draw_moves", 5)
        draw_score_range = self.draw_or_resign.get("offer_draw_score", 0)
        draw_max_piece_count = self.draw_or_resign.get("offer_draw_pieces", 10)
        pieces_on_board = len(board.board.pieces)
        enough_pieces_captured = pieces_on_board <= draw_max_piece_count

        if can_offer_draw and len(self.scores) >= draw_offer_moves and enough_pieces_captured:
            scores = self.scores[-draw_offer_moves:]

            def score_near_draw(score):
                return abs(actual(score)) <= draw_score_range
            if len(scores) == len(list(filter(score_near_draw, scores))):
                result.draw_offered = True

        resign_enabled = self.draw_or_resign.get("resign_enabled", False)
        min_moves_for_resign = self.draw_or_resign.get("resign_moves", 3)
        resign_score = self.draw_or_resign.get("resign_score", -1000)

        if resign_enabled and len(self.scores) >= min_moves_for_resign:
            scores = self.scores[-min_moves_for_resign:]

            def score_near_loss(score):
                return actual(score) <= resign_score
            if len(scores) == len(list(filter(score_near_loss, scores))):
                result.resigned = True
        return result

    def search(self, board, time_limit, ponder, draw_offered):
        pass

    def process_playresult(self, board, result):
        self.last_move_info = result.info.copy()
        self.move_commentary.append(self.last_move_info.copy())
        if self.comment_start_index is None:
            self.comment_start_index = len(board.move_stack)
        self.scores.append(self.last_move_info.get("score", {"win": 1}))
        result = self.offer_draw_or_resign(result, board)
        self.last_move_info["ponderpv"] = self.last_move_info.get("pv", "")[1:-1].split()
        self.print_stats()
        return result

    def comment_index(self, move_stack_index):
        if self.comment_start_index is None:
            return -1
        else:
            return move_stack_index - self.comment_start_index

    def comment_for_board_index(self, index):
        comment_index = self.comment_index(index)
        if comment_index < 0 or comment_index % 2 != 0:
            return None

        try:
            return self.move_commentary[comment_index // 2]
        except IndexError:
            return None

    def add_null_comment(self):
        if self.comment_start_index is not None:
            self.move_commentary.append(None)

    def print_stats(self):
        for line in self.get_stats():
            logger.info(line)

    def get_stats(self, for_chat=False):
        info = self.last_move_info.copy()
        stats = ["depth", "nps", "nodes", "score", "ponderpv"]
        if for_chat:
            bot_stats = [f"{stat}: {info[stat]}" for stat in stats if stat in info and stat != "ponderpv"]
            len_bot_stats = len(", ".join(bot_stats)) + PONDERPV_CHARACTERS
            ponder_pv = info["ponderpv"]
            ponder_pv = ponder_pv.split()
            try:
                while len(" ".join(ponder_pv)) + len_bot_stats > MAX_CHAT_MESSAGE_LEN:
                    ponder_pv.pop()
                if ponder_pv[-1].endswith("."):
                    ponder_pv.pop()
                info["ponderpv"] = " ".join(ponder_pv)
            except IndexError:
                pass
        return [f"{stat}: {info[stat]}" for stat in stats if stat in info]

    def get_opponent_info(self, game):
        pass

    def name(self):
        return self.engine.id.get("name", "")

    def report_game_result(self, game, board):
        pass

    def stop(self):
        pass

    def quit(self):
        pass

    def kill_process(self):
        self.engine.kill_process()

    def ponderhit(self):
        pass


class HubEngine(EngineWrapper):
    def __init__(self, commands, options, stderr, draw_or_resign, **popen_args):
        super().__init__(options, draw_or_resign)
        self.engine = draughts.engine.HubEngine(commands, **popen_args)

        if "bb-size" in options and options["bb-size"] == "auto":
            if "variant" in options and options["variant"] != "normal":
                variant = f'_{options["variant"]}'
            else:
                variant = ""
            for number in range(1, 7):
                path = os.path.realpath(f"./data/bb{variant}/{number + 1}")
                if not os.path.isdir(path):
                    break
            else:
                number += 1
            if number == 1:
                number = 0
            options["bb-size"] = number

        self.engine.configure(options)
        self.engine.init()

    def search(self, board, time_limit, ponder, draw_offered):
        time_limit = self.add_go_commands(time_limit)
        result = self.engine.play(board, time_limit, ponder=ponder)
        return self.process_playresult(board, result)

    def stop(self):
        self.engine.stop()

    def quit(self):
        self.engine.quit()

    def ponderhit(self):
        self.engine.ponderhit()


class DXPEngine(EngineWrapper):
    def __init__(self, commands, options, stderr, draw_or_resign, **popen_args):
        super().__init__(options, draw_or_resign)
        self.engine = draughts.engine.DXPEngine(commands, options=options, **popen_args)

    def search(self, board, time_limit, ponder, draw_offered):
        if ponder:
            return draughts.engine.PlayResult(None, None)
        time_limit = self.add_go_commands(time_limit)
        result = self.engine.play(board)
        return self.process_playresult(board, result)

    def quit(self):
        self.engine.quit()


class CBEngine(EngineWrapper):
    def __init__(self, commands, options, stderr, draw_or_resign, **popen_args):
        super().__init__(options, draw_or_resign)
        self.engine = draughts.engine.CheckerBoardEngine(commands)
        self.engine.configure(options)

    def search(self, board, time_limit, ponder, draw_offered):
        if ponder:
            return draughts.engine.PlayResult(None, None)
        time_limit = self.add_go_commands(time_limit)
        result = self.engine.play(board, time_limit)
        return self.process_playresult(board, result)


def getHomemadeEngine(name):
    import strategies
    return getattr(strategies, name)
