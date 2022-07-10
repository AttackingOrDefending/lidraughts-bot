import argparse
import draughts
import draughts.engine
import engine_wrapper
import model
import json
import lidraughts
import logging
import logging.handlers
import multiprocessing
import logging_pool
import signal
import time
import backoff
import sys
import threading
import os
from config import load_config
from conversation import Conversation, ChatLine
from requests.exceptions import ChunkedEncodingError, ConnectionError, HTTPError, ReadTimeout
from rich.logging import RichHandler
from collections import defaultdict
from http.client import RemoteDisconnected

logger = logging.getLogger(__name__)

__version__ = "1.2.0"

terminated = False


def signal_handler(signal, frame):
    global terminated
    logger.debug("Recieved SIGINT. Terminating client.")
    terminated = True


signal.signal(signal.SIGINT, signal_handler)


def is_final(exception):
    return isinstance(exception, HTTPError) and exception.response.status_code < 500


def upgrade_account(li):
    if li.upgrade_to_bot_account() is None:
        return False

    logger.info("Succesfully upgraded to Bot Account!")
    return True


def watch_control_stream(control_queue, li):
    while not terminated:
        try:
            response = li.get_event_stream()
            lines = response.iter_lines()
            for line in lines:
                if line:
                    event = json.loads(line.decode("utf-8"))
                    control_queue.put_nowait(event)
                else:
                    control_queue.put_nowait({"type": "ping"})
        except Exception:
            pass


def do_correspondence_ping(control_queue, period):
    while not terminated:
        time.sleep(period)
        control_queue.put_nowait({"type": "correspondence_ping"})


def logging_configurer(level, filename):
    console_handler = RichHandler()
    console_formatter = logging.Formatter("%(message)s")
    console_handler.setFormatter(console_formatter)
    all_handlers = [console_handler]

    if filename:
        file_handler = logging.FileHandler(filename, delay=True)
        FORMAT = "%(asctime)s %(name)s %(levelname)s %(message)s"
        file_formatter = logging.Formatter(FORMAT)
        file_handler.setFormatter(file_formatter)
        all_handlers.append(file_handler)

    logging.basicConfig(level=level,
                        handlers=all_handlers,
                        force=True)


def logging_listener_proc(queue, configurer, level, log_filename):
    configurer(level, log_filename)
    logger = logging.getLogger()
    while not terminated:
        try:
            logger.handle(queue.get())
        except Exception:
            pass


def game_logging_configurer(queue, level):
    if sys.platform == "win32":
        h = logging.handlers.QueueHandler(queue)
        root = logging.getLogger()
        root.handlers.clear()
        root.addHandler(h)
        root.setLevel(level)


def start(li, user_profile, config, logging_level, log_filename, one_game=False):
    challenge_config = config["challenge"]
    max_games = challenge_config.get("concurrency", 1)
    logger.info(f"You're now connected to {config['url']} and awaiting challenges.")
    manager = multiprocessing.Manager()
    challenge_queue = manager.list()
    control_queue = manager.Queue()
    control_stream = multiprocessing.Process(target=watch_control_stream, args=[control_queue, li])
    control_stream.start()
    correspondence_cfg = config.get("correspondence") or {}
    correspondence_checkin_period = correspondence_cfg.get("checkin_period", 600)
    correspondence_pinger = multiprocessing.Process(target=do_correspondence_ping, args=[control_queue, correspondence_checkin_period])
    correspondence_pinger.start()
    correspondence_queue = manager.Queue()
    correspondence_queue.put("")
    startup_correspondence_games = [game["gameId"] for game in li.get_ongoing_games() if game["perf"] == "correspondence"]
    wait_for_correspondence_ping = False

    busy_processes = 0
    queued_processes = 0

    logging_queue = manager.Queue()
    logging_listener = multiprocessing.Process(target=logging_listener_proc, args=(logging_queue, logging_configurer, logging_level, log_filename))
    logging_listener.start()

    with logging_pool.LoggingPool(max_games + 1) as pool:
        while not terminated:
            try:
                event = control_queue.get()
                if event.get("type") != "ping":
                    logger.debug(f"Event: {event}")
            except InterruptedError:
                continue

            if event.get("type") is None:
                logger.warning("Unable to handle response from lidraughts.org:")
                logger.warning(event)
                if event.get("error") == "Missing scope":
                    logger.warning('Please check that the API access token for your bot has the scope "Play games with the bot API".')
                continue

            if event["type"] == "terminated":
                break
            elif event["type"] == "local_game_done":
                busy_processes -= 1
                logger.info(f"+++ Process Free. Total Queued: {queued_processes}. Total Used: {busy_processes}")
                if one_game:
                    break
            elif event["type"] == "challenge":
                chlng = model.Challenge(event["challenge"])
                if chlng.is_supported(challenge_config):
                    challenge_queue.append(chlng)
                    if challenge_config.get("sort_by", "best") == "best":
                        list_c = list(challenge_queue)
                        list_c.sort(key=lambda c: -c.score())
                        challenge_queue = list_c
                else:
                    try:
                        reason = "generic"
                        challenge = config["challenge"]
                        if not chlng.is_supported_variant(challenge["variants"]):
                            reason = "variant"
                        if not chlng.is_supported_time_control(challenge["time_controls"], challenge.get("max_increment", 180), challenge.get("min_increment", 0), challenge.get("max_base", 315360000), challenge.get("min_base", 0)):
                            reason = "timeControl"
                        if not chlng.is_supported_mode(challenge["modes"]):
                            reason = "casual" if chlng.rated else "rated"
                        if not challenge.get("accept_bot", False) and chlng.challenger_is_bot:
                            reason = "noBot"
                        if challenge.get("only_bot", False) and not chlng.challenger_is_bot:
                            reason = "onlyBot"
                        li.decline_challenge(chlng.id, reason=reason)
                        logger.info(f"Decline {chlng} for reason '{reason}'")
                    except Exception:
                        pass
            elif event["type"] == "gameStart":
                game_id = event["game"]["id"]
                if game_id in startup_correspondence_games:
                    logger.info(f'--- Enqueue {config["url"] + game_id}')
                    correspondence_queue.put(game_id)
                    startup_correspondence_games.remove(game_id)
                else:
                    if queued_processes > 0:
                        queued_processes -= 1
                    busy_processes += 1
                    logger.info(f"--- Process Used. Total Queued: {queued_processes}. Total Used: {busy_processes}")
                    pool.apply_async(play_game, [li, game_id, control_queue, user_profile, config, challenge_queue, correspondence_queue, logging_queue, game_logging_configurer, logging_level])

            is_correspondence_ping = event["type"] == "correspondence_ping"
            is_local_game_done = event["type"] == "local_game_done"
            if (is_correspondence_ping or (is_local_game_done and not wait_for_correspondence_ping)) and not challenge_queue:
                if is_correspondence_ping and wait_for_correspondence_ping:
                    correspondence_queue.put("")

                wait_for_correspondence_ping = False
                while (busy_processes + queued_processes) < max_games:
                    game_id = correspondence_queue.get()
                    # stop checking in on games if we have checked in on all games since the last correspondence_ping
                    if not game_id:
                        if is_correspondence_ping and not correspondence_queue.empty():
                            correspondence_queue.put("")
                        else:
                            wait_for_correspondence_ping = True
                            break
                    else:
                        busy_processes += 1
                        logger.info(f"--- Process Used. Total Queued: {queued_processes}. Total Used: {busy_processes}")
                        pool.apply_async(play_game, [li, game_id, control_queue, user_profile, config, challenge_queue, correspondence_queue, logging_queue, game_logging_configurer, logging_level])

            while (queued_processes + busy_processes) < max_games and challenge_queue:  # keep processing the queue until empty or max_games is reached
                chlng = challenge_queue.pop(0)
                try:
                    logger.info(f"Accept {chlng}")
                    queued_processes += 1
                    li.accept_challenge(chlng.id)
                    logger.info(f"--- Process Queue. Total Queued: {queued_processes}. Total Used: {busy_processes}")
                except (HTTPError, ReadTimeout) as exception:
                    if isinstance(exception, HTTPError) and exception.response.status_code == 404:  # ignore missing challenge
                        logger.info(f"Skip missing {chlng}")
                    queued_processes -= 1

            control_queue.task_done()

    logger.info("Terminated")
    control_stream.terminate()
    control_stream.join()
    correspondence_pinger.terminate()
    correspondence_pinger.join()
    logging_listener.terminate()
    logging_listener.join()


ponder_results = {}


@backoff.on_exception(backoff.expo, BaseException, max_time=600, giveup=is_final)
def play_game(li, game_id, control_queue, user_profile, config, challenge_queue, correspondence_queue, logging_queue, game_logging_configurer, logging_level):
    game_logging_configurer(logging_queue, logging_level)
    logger = logging.getLogger(__name__)

    response = li.get_game_stream(game_id)
    lines = response.iter_lines()

    # Initial response of stream will be the full game info. Store it
    initial_state = json.loads(next(lines).decode("utf-8"))
    logger.debug(f"Initial state: {initial_state}")
    game = model.Game(initial_state, user_profile["username"], li.baseUrl, config.get("abort_time", 20))

    initial_time = (game.state["wtime"] if game.my_color == "white" else game.state["btime"]) / 1000
    variant = parse_variant(game.variant_name)
    engine = engine_wrapper.create_engine(config, variant, initial_time)
    conversation = Conversation(game, engine, li, __version__, challenge_queue)

    logger.info(f"+++ {game}")

    is_correspondence = game.perf_name == "Correspondence"
    correspondence_cfg = config.get("correspondence") or {}
    correspondence_move_time = correspondence_cfg.get("move_time", 60) * 1000

    engine_cfg = config["engine"]
    ponder_cfg = correspondence_cfg if is_correspondence else engine_cfg
    can_ponder = ponder_cfg.get("ponder", False)
    move_overhead = config.get("move_overhead", 1000)
    move_overhead_inc = config.get("move_overhead_inc", 100)
    delay_seconds = config.get("rate_limiting_delay", 0)/1000

    greeting_cfg = config.get("greeting") or {}
    keyword_map = defaultdict(str, me=game.me.name, opponent=game.opponent.name)
    get_greeting = lambda greeting: str(greeting_cfg.get(greeting) or "").format_map(keyword_map)
    hello = get_greeting("hello")
    goodbye = get_greeting("goodbye")

    board = draughts.Game(game.variant_name.lower(), game.initial_fen)
    moves, old_moves = [], []
    ponder_thread = None
    ponder_li_one = None

    first_move = True
    correspondence_disconnect_time = 0
    while not terminated:
        move_attempted = False
        try:
            if first_move:
                upd = game.state
                first_move = False
            else:
                binary_chunk = next(lines)
                upd = json.loads(binary_chunk.decode("utf-8")) if binary_chunk else None
            logger.debug(f"Game state: {upd}")

            u_type = upd["type"] if upd else "ping"
            if u_type == "chatLine":
                conversation.react(ChatLine(upd), game)
            elif u_type == "gameState":
                game.state = upd

                start_time = time.perf_counter_ns()
                if upd["moves"] and len(upd["moves"].split()[-1]) != 4:
                    continue
                moves = upd["moves"].split()
                moves_to_get = len(moves) - len(old_moves)
                if moves_to_get > 0:
                    for move in moves[-moves_to_get:]:
                        board.push_str_move(move)
                old_moves = moves

                if not is_game_over(board) and is_engine_move(game, board):
                    if len(board.move_stack) < 2:
                        conversation.send_message("player", hello)
                    fake_thinking(config, board, game)
                    print_move_number(board)
                    correspondence_disconnect_time = correspondence_cfg.get("disconnect_time", 300)

                    draw_offered = check_for_draw_offer(game)

                    if len(board.move_stack) < 2:
                        best_move = choose_first_move(engine, board, draw_offered)
                    elif is_correspondence:
                        best_move = choose_move_time(engine, board, correspondence_move_time, draw_offered)
                    else:
                        best_move = get_pondering_results(ponder_thread, ponder_li_one, game, board, engine)
                        if best_move.move is None:
                            best_move = choose_move(engine, board, game, draw_offered, start_time, move_overhead, move_overhead_inc)
                    move_attempted = True
                    if best_move.resigned and len(board.move_stack) >= 2:
                        li.resign(game.id)
                    else:
                        li.make_move(game.id, best_move)
                    ponder_thread, ponder_li_one = start_pondering(engine, board, game, can_ponder, best_move, start_time, move_overhead, move_overhead_inc)
                    time.sleep(delay_seconds)
                elif is_game_over(board):
                    engine.report_game_result(game, board)
                    tell_user_game_result(game, board)
                    conversation.send_message("player", goodbye)
                elif len(board.move_stack) == 0:
                    correspondence_disconnect_time = correspondence_cfg.get("disconnect_time", 300)

                wb = "w" if board.whose_turn() == draughts.WHITE else "b"
                game.ping(config.get("abort_time", 20), (upd[f"{wb}time"] + upd[f"{wb}inc"]) / 1000 + 60, correspondence_disconnect_time)
            elif u_type == "ping":
                if is_correspondence and not is_engine_move(game, board) and game.should_disconnect_now():
                    break
                elif game.should_abort_now():
                    logger.info(f"Aborting {game.url()} by lack of activity")
                    li.abort(game.id)
                    break
                elif game.should_terminate_now():
                    logger.info(f"Terminating {game.url()} by lack of activity")
                    if game.is_abortable():
                        li.abort(game.id)
                    break
        except (HTTPError, ReadTimeout, RemoteDisconnected, ChunkedEncodingError, ConnectionError):
            if move_attempted:
                continue
            if game.id not in (ongoing_game["gameId"] for ongoing_game in li.get_ongoing_games()):
                break
        except StopIteration:
            break

    engine.stop()
    engine.quit()

    try:
        print_pgn_game_record(li, config, game, board, engine)
    except Exception as e:
        logger.warning(f"Error writing game record: {repr(e)}")

    if is_correspondence and not is_game_over(board):
        logger.info(f"--- Disconnecting from {game.url()}")
        correspondence_queue.put(game_id)
    else:
        logger.info(f"--- {game.url()} Game over")

    control_queue.put_nowait({"type": "local_game_done"})


def parse_variant(variant):
    variant = variant.lower()

    if variant in ["standard", "from position"]:
        return "normal"
    elif variant == "breakthrough":
        return "bt"
    elif variant == "antidraughts":
        return "losing"
    elif variant == "frysk!":
        return "frisian"
    else:
        return variant


def choose_move_time(engine, board, search_time, draw_offered):
    logger.info(f"Searching for time {search_time}")
    return engine.search_for(board, search_time, draw_offered)


def choose_first_move(engine, board, draw_offered):
    # need to hardcode first movetime (10000 ms) since Lidraughts has 30 sec limit.
    search_time = 10000
    logger.info(f"Searching for time {search_time}")
    return engine.first_search(board, search_time, draw_offered)


def choose_move(engine, board, game, draw_offered, start_time, move_overhead, move_overhead_inc):
    wtime = game.state["wtime"]
    btime = game.state["btime"]
    winc = game.state["winc"]
    binc = game.state["binc"]
    pre_move_time = int((time.perf_counter_ns() - start_time) / 1000000)
    if board.whose_turn() == draughts.WHITE:
        wtime = max(0, wtime - move_overhead - pre_move_time)
        winc = max(0, winc - move_overhead_inc)
    else:
        btime = max(0, btime - move_overhead - pre_move_time)
        binc = max(0, binc - move_overhead_inc)

    logger.info(f"Searching for wtime {wtime} btime {btime}")
    return engine.search_with_ponder(board, wtime, btime, winc, binc, False, draw_offered)


def start_pondering(engine, board, game, can_ponder, best_move, start_time, move_overhead, move_overhead_inc):
    if not can_ponder or best_move.ponder is None:
        return None, None

    ponder_board = board.copy()
    for move in best_move.move.board_move:
        ponder_board.move(move)
    for move in best_move.ponder.board_move:
        ponder_board.move(move)

    wtime = game.state["wtime"]
    btime = game.state["btime"]
    winc = game.state["winc"]
    binc = game.state["binc"]
    setup_time = int((time.perf_counter_ns() - start_time) / 1000000)
    if board.whose_turn() == draughts.WHITE:
        wtime = wtime - move_overhead - setup_time + winc
        winc = winc - move_overhead_inc
    else:
        btime = btime - move_overhead - setup_time + binc
        binc = binc - move_overhead_inc

    def ponder_thread_func(game, engine, board, wtime, btime, winc, binc):
        global ponder_results
        best_move = engine.search_with_ponder(board, wtime, btime, winc, binc, True, False)
        ponder_results[game.id] = best_move

    logger.info(f"Pondering for wtime {wtime} btime {btime}")
    ponder_thread = threading.Thread(target=ponder_thread_func, args=(game, engine, ponder_board, wtime, btime, winc, binc))
    ponder_thread.start()
    return ponder_thread, best_move.ponder.li_one_move


def get_pondering_results(ponder_thread, ponder_li_one, game, board, engine):
    no_move = draughts.engine.PlayResult(None, None)
    if ponder_thread is None:
        return no_move

    move_li_one = board.move_stack[-1].li_one_move
    if ponder_li_one == move_li_one:
        engine.ponderhit()
        ponder_thread.join()
        return ponder_results[game.id]
    else:
        engine.stop()
        ponder_thread.join()
        return no_move


def check_for_draw_offer(game):
    return game.state.get(f"{game.opponent_color[0]}draw", False)


def fake_thinking(config, board, game):
    if config.get("fake_think_time") and len(board.move_stack) > 9:
        delay = min(game.clock_initial, game.my_remaining_seconds()) * 0.015
        accel = 1 - max(0, min(100, len(board.move_stack) - 20)) / 150
        sleep = min(5, delay * accel)
        time.sleep(sleep)


def print_move_number(board):
    logger.info("")
    logger.info(f"move: {len(board.move_stack) // 2 + 1}")


def is_engine_move(game, board):
    return game.is_white == (board.whose_turn() == draughts.WHITE)


def is_game_over(board):
    return board.is_over()


def tell_user_game_result(game, board):
    winner = game.state.get("winner")
    termination = game.state.get("status")

    winning_name = game.white.name if winner == "white" else game.black.name
    losing_name = game.white.name if winner == "black" else game.black.name

    if winner is not None:
        logger.info(f"{winning_name} won!")
    elif termination == engine_wrapper.Termination.DRAW:
        logger.info("Game ended in draw.")
    else:
        logger.info("Game adjourned.")

    if termination == engine_wrapper.Termination.MATE:
        logger.info("Game won by checkmate.")
    elif termination == engine_wrapper.Termination.TIMEOUT:
        logger.info(f"{losing_name} forfeited on time.")
    elif termination == engine_wrapper.Termination.RESIGN:
        logger.info(f"{losing_name} resigned.")
    elif termination == engine_wrapper.Termination.ABORT:
        logger.info("Game aborted.")
    elif termination == engine_wrapper.Termination.DRAW:
        if board.is_fifty_moves():
            logger.info("Game drawn by 50-move rule.")
        elif board.is_repetition():
            logger.info("Game drawn by threefold repetition.")
        else:
            logger.info("Game drawn by agreement.")
    elif termination:
        logger.info(f"Game ended by {termination}")


def print_pgn_game_record(li, config, game, board, engine):
    game_directory = config.get("pgn_directory")
    if not game_directory:
        return

    try:
        os.mkdir(game_directory)
    except FileExistsError:
        pass

    game_file_name = f"{game.white.name} vs {game.black.name} - {game.id}.pgn"
    game_file_name = "".join(c for c in game_file_name if c not in '<>:"/\\|?*')
    game_path = os.path.join(game_directory, game_file_name)

    lidraughts_game_record = li.get_game_pgn(game.id)

    with open(game_path, "w") as game_record_destination:
        game_record_destination.write(lidraughts_game_record)


def intro():
    return r"""
    .   _/|
    .  // o\
    .  || ._)  lidraughts-bot %s
    .  //__\
    .  )___(   Play on Lidraughts with a bot
    """ % __version__


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Play on Lidraughts with a bot")
    parser.add_argument("-u", action="store_true", help="Upgrade your account to a bot account.")
    parser.add_argument("-v", action="store_true",
                        help="Make output more verbose. Include all communication with lichess.org.")
    parser.add_argument("--config", help="Specify a configuration file (defaults to ./config.yml)")
    parser.add_argument("-l", "--logfile", help="Record all console output to a log file.", default=None)
    args = parser.parse_args()

    logging_level = logging.DEBUG if args.v else logging.INFO
    logging_configurer(logging_level, args.logfile)
    logger.info(intro(), extra={"highlighter": None})
    CONFIG = load_config(args.config or "./config.yml")
    li = lidraughts.Lidraughts(CONFIG["token"], CONFIG["url"], __version__, logging_level)

    user_profile = li.get_profile()
    username = user_profile["username"]
    is_bot = user_profile.get("title") == "BOT"
    logger.info(f"Welcome {username}!")

    if args.u and not is_bot:
        is_bot = upgrade_account(li)

    if is_bot:
        start(li, user_profile, CONFIG, logging_level, args.logfile)
    else:
        logger.error(f"{username} is not a bot account. Please upgrade it to a bot account!")
