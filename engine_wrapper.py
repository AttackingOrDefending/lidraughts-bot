import os
import backoff
import subprocess
import logging
from draughts.engine import HubEngine as hub_engine
from draughts.engine import DXPEngine as dxp_engine
from draughts.engine import CheckerBoardEngine as cb_engine
from draughts.engine import Limit

logger = logging.getLogger(__name__)


@backoff.on_exception(backoff.expo, BaseException, max_time=120)
def create_engine(config, variant, initial_time):
    cfg = config["engine"]
    engine_path = os.path.normpath(os.path.expanduser(os.path.join(cfg["dir"], cfg["name"])))
    engine_working_dir = cfg.get("working_dir") or os.getcwd()
    engine_type = cfg.get("protocol")
    engine_options = cfg.get("engine_options")
    draw_or_resign = cfg.get("draw_or_resign") or {}
    commands = [engine_path, cfg["engine_arguement"]]
    if engine_options:
        for k, v in engine_options.items():
            commands.append(f"--{k}={v}")

    stderr = None if cfg.get("silence_stderr", False) else subprocess.DEVNULL

    if engine_type == "hub":
        Engine = HubEngine
    elif engine_type == "dxp":
        Engine = DXPEngine
    elif engine_type == "cb":
        Engine = CheckerBoardEngine
    elif engine_type == "homemade":
        Engine = getHomemadeEngine(cfg["name"])
    else:
        raise ValueError(
            f"    Invalid engine type: {engine_type}. Expected hub, dxp, cb, or homemade.")
    options = cfg.get(f"{engine_type}_options") or {}
    options["variant"] = variant
    options["initial-time"] = initial_time
    return Engine(commands, options, stderr, draw_or_resign, cwd=engine_working_dir)


class EngineWrapper:
    def __init__(self, options, draw_or_resign):
        self.scores = []
        self.draw_or_resign = draw_or_resign
        self.go_commands = options.pop("go_commands") or {}
        self.last_move_info = {}

    def search_for(self, board, movetime, draw_offered):
        return self.search(board, Limit(movetime=movetime // 1000), False, draw_offered)

    def search_with_ponder(self, board, wtime, btime, winc, binc, ponder, draw_offered):
        cmds = self.go_commands
        movetime = cmds.get("movetime")
        if movetime is not None:
            movetime = float(movetime) // 1000
        if board.get_fen()[0].lower() == "w":
            time = wtime
            inc = winc
        else:
            time = btime
            inc = binc
        time_limit = Limit(time=time / 1000,
                           inc=inc / 1000,
                           depth=cmds.get("depth"),
                           nodes=cmds.get("nodes"),
                           movetime=movetime)
        return self.search(board, time_limit, ponder, draw_offered)

    def offer_draw_or_resign(self, result, board):
        def mate_score_to_score(score):
            if "cp" in score:
                return score.get("cp", float("nan"))
            else:
                win = score.get("win", float("nan"))
                if win > 0:
                    return 10000 - win
                else:
                    return -10000 - win

        if self.draw_or_resign.get("offer_draw_enabled", False) and len(self.scores) >= self.draw_or_resign.get("offer_draw_moves", 5):
            scores = self.scores[-self.draw_or_resign.get("offer_draw_moves", 5):]
            pieces_on_board = len(list(filter(bool, board.board.pieces)))
            scores_near_draw = lambda score: abs(mate_score_to_score(score)) <= self.draw_or_resign.get("offer_draw_score", 0)
            if len(scores) == len(list(filter(scores_near_draw, scores))) and pieces_on_board <= self.draw_or_resign.get("offer_draw_pieces", 10):
                result.draw_offered = True

        if self.draw_or_resign.get("resign_enabled", False) and len(self.scores) >= self.draw_or_resign.get("resign_moves", 3):
            scores = self.scores[-self.draw_or_resign.get("resign_moves", 3):]
            scores_near_loss = lambda score: mate_score_to_score(score) <= self.draw_or_resign.get("resign_score", -1000)
            if len(scores) == len(list(filter(scores_near_loss, scores))):
                result.resigned = True
        return result

    def search(self, board, time_limit, ponder, draw_offered):
        pass

    def print_stats(self):
        for line in self.get_stats():
            logger.info(f"{line}")

    def get_stats(self):
        info = self.last_move_info
        stats = ["depth", "nps", "nodes", "score"]
        return [f"{stat}: {info[stat]}" for stat in stats if stat in info]

    def name(self):
        return self.engine.id.get("name", "")

    def stop(self):
        pass

    def quit(self):
        pass

    def kill_process(self):
        pass

    def ponderhit(self):
        pass


class HubEngine(EngineWrapper):
    def __init__(self, commands, options, stderr, draw_or_resign, cwd=None):
        super().__init__(options, draw_or_resign)
        self.engine = hub_engine(commands, cwd=cwd)

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

        if options:
            for name in options:
                self.engine.setoption(name, options[name])

        self.engine.init()

    def search(self, board, time_limit, ponder, draw_offered):
        result = self.engine.play(board, time_limit, ponder=ponder)
        self.last_move_info = result.info
        self.scores.append(self.last_move_info.get("score", {"win": 1}))
        result = self.offer_draw_or_resign(result, board)
        self.print_stats()
        return result

    def stop(self):
        self.engine.stop()

    def quit(self):
        self.engine.quit()

    def kill_process(self):
        self.engine.kill_process()

    def ponderhit(self):
        self.engine.ponderhit()


class DXPEngine(EngineWrapper):
    def __init__(self, commands, options, stderr, draw_or_resign, cwd=None):
        super().__init__(commands, options, stderr, draw_or_resign)
        self.engine = dxp_engine(commands, options)

    def search_for(self, board, movetime, draw_offered):
        return self.search(board, None, False, False)

    def search_with_ponder(self, board, wtime, btime, winc, binc, ponder, draw_offered):
        return self.search(board, None, False, False)

    def search(self, board, time_limit, ponder, draw_offered):
        return self.engine.play(board)

    def quit(self):
        self.engine.quit()

    def kill_process(self):
        self.engine.kill_process()


class CheckerBoardEngine(EngineWrapper):
    def __init__(self, commands, options, stderr, draw_or_resign, cwd=None):
        super().__init__(commands, options, stderr, draw_or_resign)
        self.engine = cb_engine(commands)
        if options:
            for name in options:
                self.engine.setoption(name, options[name])

    def search(self, board, time_limit, ponder, draw_offered):
        cb_result_to_score = {0: 0, 1: 100, 2: -100, 3: 100}
        result = self.engine.play(board, time_limit)
        self.last_move_info = result.info
        self.scores.append(cb_result_to_score[self.last_move_info.get("result", 1)])
        result = self.offer_draw_or_resign(result, board)
        self.print_stats()
        return result

    def kill_process(self):
        self.engine.kill_process()


def getHomemadeEngine(name):
    import strategies
    return eval(f"strategies.{name}")
