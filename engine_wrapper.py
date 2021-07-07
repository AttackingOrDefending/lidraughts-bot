import os
import hub_engine
import backoff
import subprocess
import logging

logger = logging.getLogger(__name__)


@backoff.on_exception(backoff.expo, BaseException, max_time=120)
def create_engine(config):
    cfg = config["engine"]
    engine_path = os.path.realpath(os.path.join(cfg["dir"], cfg["name"]))
    engine_type = cfg.get("protocol")
    engine_options = cfg.get("engine_options")
    commands = [engine_path, cfg["engine_arguement"]]
    if engine_options:
        for k, v in engine_options.items():
            commands.append("--{}={}".format(k, v))

    stderr = None if cfg.get("silence_stderr", False) else subprocess.DEVNULL

    if engine_type == "hub":
        Engine = HubEngine
    elif engine_type == "homemade":
        Engine = getHomemadeEngine(cfg["name"])
    else:
        raise ValueError(
            f"    Invalid engine type: {engine_type}. Expected hub, or homemade.")
    options = cfg.get(engine_type + "_options", {}) or {}
    return Engine(commands, options, stderr)


class EngineWrapper:
    def __init__(self, commands, options, stderr):
        pass

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

        if 'bb-size' in options:
            if options['bb-size'] == 'auto':
                if 'variant' not in options:  # Normal variant
                    options['bb-size'] = 6
                elif options['variant'] == 'normal':  # Normal variant
                    options['bb-size'] = 6
                elif options['variant'] == 'bt':  # Breakthrough variant
                    options['bb-size'] = 7
                elif options['variant'] == 'frisian':  # Frisian variant
                    options['bb-size'] = 5
                elif options['variant'] == 'losing':  # Losing variant
                    options['bb-size'] = 5
                elif options['variant'] == 'killer':  # Killer variant. Not in lidraughts
                    options['bb-size'] = 6

        if options:
            for name in options:
                self.engine.setoption(name, options[name])

        self.engine.init()
    
    def stop(self):
        self.engine.stop()

    def quit(self):
        self.engine.quit()
    
    def kill_process(self):
        self.engine.kill_process()

    def ponderhit(self):
        self.engine.ponderhit()


def getHomemadeEngine(name):
    import strategies
    return eval(f"strategies.{name}")
