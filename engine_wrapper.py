import os
import hub_engine
import backoff
import subprocess
import logging
import dxp_engine
import draughts

logger = logging.getLogger(__name__)


@backoff.on_exception(backoff.expo, BaseException, max_time=120)
def create_engine(config, variant, initial_time):
    cfg = config["engine"]
    engine_path = os.path.normpath(os.path.expanduser(os.path.join(cfg["dir"], cfg["name"])))
    engine_type = cfg.get("protocol")
    engine_options = cfg.get("engine_options")
    commands = [engine_path, cfg["engine_arguement"]]
    if engine_options:
        for k, v in engine_options.items():
            commands.append("--{}={}".format(k, v))

    stderr = None if cfg.get("silence_stderr", False) else subprocess.DEVNULL

    if engine_type == "hub":
        Engine = HubEngine
    elif engine_type == "dxp":
        Engine = DXPEngine
    elif engine_type == "homemade":
        Engine = getHomemadeEngine(cfg["name"])
    else:
        raise ValueError(
            f"    Invalid engine type: {engine_type}. Expected hub, or homemade.")
    options = cfg.get(engine_type + "_options", {}) or {}
    options['variant'] = variant
    options['initial-time'] = initial_time
    return Engine(commands, options, stderr)


class EngineWrapper:
    def __init__(self, commands, options, stderr):
        pass

    def search_for(self, board, movetime):
        pass

    def search_with_ponder(self, board, wtime, btime, winc, binc, ponder):
        pass

    def search(self, board, time_limit, ponder):
        pass

    def print_stats(self):
        for line in self.get_stats():
            logger.info(f"{line}")

    def get_stats(self):
        info = self.last_move_info
        stats = ["depth", "nps", "nodes", "score"]
        return [f"{stat}: {info[stat]}" for stat in stats if stat in info]

    def name(self):
        return self.engine.id["name"]

    def stop(self):
        pass

    def quit(self):
        pass
    
    def kill_process(self):
        pass

    def ponderhit(self):
        pass


class HubEngine(EngineWrapper):
    def __init__(self, commands, options, stderr):
        self.go_commands = options.pop("go_commands", {}) or {}
        self.engine = hub_engine.Engine(commands)
        self.engine.uci()

        if 'bb-size' in options and options['bb-size'] == 'auto':
            if 'variant' in options and options['variant'] != 'normal':
                variant = '_' + options['variant']
            else:
                variant = ''
            for number in range(1, 7):
                path = os.path.realpath(f"./data/bb{variant}/{number + 1}")
                if not os.path.isdir(path):
                    break
            else:
                number += 1
            if number == 1:
                number = 0
            options['bb-size'] = number

        if options:
            for name in options:
                self.engine.setoption(name, options[name])

        self.engine.init()

    def search_for(self, board, movetime):
        return self.search(board, hub_engine.Limit(movetime=movetime // 1000), False)

    def search_with_ponder(self, board, wtime, btime, winc, binc, ponder):
        cmds = self.go_commands
        movetime = cmds.get("movetime")
        if movetime is not None:
            movetime = float(movetime) // 1000
        if board.get_fen()[0].lower() == 'w':
            time = wtime - winc  # Because Scan adds first the increment
            inc = winc
        else:
            time = btime - binc  # Because Scan adds first the increment
            inc = binc
        time_limit = hub_engine.Limit(time=time / 1000,
                                      inc=inc / 1000,
                                      depth=cmds.get("depth"),
                                      nodes=cmds.get("nodes"),
                                      movetime=movetime)
        return self.search(board, time_limit, ponder)
    
    def search(self, board, time_limit, ponder):
        result = self.engine.play(board, time_limit, ponder=ponder)
        ponder_move = None
        self.last_move_info = self.engine.info
        self.print_stats()
        if result[0] is None:
            return None, None
        ponder_board = board.copy()
        best_move, moves = ponder_board.hub_to_li_board(result[0] + result[2])
        if result[1]:
            for move in moves:
                ponder_board.move(move)
            ponder_move, _ = ponder_board.hub_to_li_board(result[1] + result[3])
        return best_move, ponder_move

    def stop(self):
        self.engine.stop()

    def quit(self):
        self.engine.quit()
    
    def kill_process(self):
        self.engine.kill_process()

    def ponderhit(self):
        self.engine.ponderhit()


class DXPEngine(EngineWrapper):
    def __init__(self, commands, options, stderr):
        self.engine = dxp_engine.Engine(commands, options)

    def search_for(self, board, movetime):
        return self.search(board, False)

    def search_with_ponder(self, board, wtime, btime, winc, binc, ponder):
        return self.search(board, ponder)

    def search(self, board, ponder):
        result = self.engine.play(board, ponder=ponder)
        ponder_move = None
        best_move = board.board_to_li_api(result)
        return best_move, ponder_move

    def quit(self):
        self.engine.quit()

    def kill_process(self):
        self.engine.kill_process()


def getHomemadeEngine(name):
    import strategies
    return eval(f"strategies.{name}")
