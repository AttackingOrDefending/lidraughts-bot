import argparse
import draughts
from draughts.engine import PlayResult
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
from config import load_config
from conversation import Conversation, ChatLine
from functools import partial
from requests.exceptions import ChunkedEncodingError, ConnectionError, HTTPError, ReadTimeout
from urllib3.exceptions import ProtocolError
from ColorLogger import enable_color_logging
from collections import defaultdict

logger = logging.getLogger(__name__)

from http.client import RemoteDisconnected

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
                    event = json.loads(line.decode('utf-8'))
                    control_queue.put_nowait(event)
                else:
                    control_queue.put_nowait({"type": "ping"})
        except Exception:
            pass


def do_correspondence_ping(control_queue, period):
    while not terminated:
        time.sleep(period)
        control_queue.put_nowait({"type": "correspondence_ping"})


def listener_configurer(level, filename):
    logging.basicConfig(level=level, filename=filename,
                        format="%(asctime)-15s: %(message)s")
    enable_color_logging(level)


def logging_listener_proc(queue, configurer, level, log_filename):
    configurer(level, log_filename)
    logger = logging.getLogger()
    while not terminated:
        try:
            logger.handle(queue.get())
        except Exception:
            pass


def game_logging_configurer(queue, level):
    if sys.platform == 'win32':
        h = logging.handlers.QueueHandler(queue)
        root = logging.getLogger()
        root.handlers.clear()
        root.addHandler(h)
        root.setLevel(level)


def start(li, user_profile, engine_factory, config, logging_level, log_filename):
    challenge_config = config["challenge"]
    max_games = challenge_config.get("concurrency", 1)
    logger.info("You're now connected to {} and awaiting challenges.".format(config["url"]))
    manager = multiprocessing.Manager()
    challenge_queue = manager.list()
    control_queue = manager.Queue()
    control_stream = multiprocessing.Process(target=watch_control_stream, args=[control_queue, li])
    control_stream.start()
    correspondence_cfg = config.get("correspondence", {}) or {}
    correspondence_checkin_period = correspondence_cfg.get("checkin_period", 600)
    correspondence_pinger = multiprocessing.Process(target=do_correspondence_ping, args=[control_queue, correspondence_checkin_period])
    correspondence_pinger.start()
    correspondence_queue = manager.Queue()
    correspondence_queue.put("")
    startup_correspondence_games = [game["gameId"] for game in li.get_ongoing_games() if game["perf"] == 'correspondence']
    wait_for_correspondence_ping = False

    busy_processes = 0
    queued_processes = 0

    logging_queue = manager.Queue()
    logging_listener = multiprocessing.Process(target=logging_listener_proc, args=(logging_queue, listener_configurer, logging_level, log_filename))
    logging_listener.start()

    with logging_pool.LoggingPool(max_games + 1) as pool:
        while not terminated:
            try:
                event = control_queue.get()
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
                logger.info("+++ Process Free. Total Queued: {}. Total Used: {}".format(queued_processes, busy_processes))
            elif event["type"] == "challenge":
                chlng = model.Challenge(event["challenge"])
                if chlng.is_supported(challenge_config):
                    challenge_queue.append(chlng)
                    if (challenge_config.get("sort_by", "best") == "best"):
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
                        logger.info("Decline {} for reason '{}'".format(chlng, reason))
                    except Exception:
                        pass
            elif event["type"] == "gameStart":
                game_id = event["game"]["id"]
                if game_id in startup_correspondence_games:
                    logger.info("--- Enqueue {}".format(config["url"] + game_id))
                    correspondence_queue.put(game_id)
                    startup_correspondence_games.remove(game_id)
                else:
                    if queued_processes > 0:
                        queued_processes -= 1
                    busy_processes += 1
                    logger.info("--- Process Used. Total Queued: {}. Total Used: {}".format(queued_processes, busy_processes))
                    pool.apply_async(play_game, [li, game_id, control_queue, engine_factory, user_profile, config, challenge_queue, correspondence_queue, logging_queue, game_logging_configurer, logging_level])

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
                        logger.info("--- Process Used. Total Queued: {}. Total Used: {}".format(queued_processes, busy_processes))
                        pool.apply_async(play_game, [li, game_id, control_queue, engine_factory, user_profile, config, challenge_queue, correspondence_queue, logging_queue, game_logging_configurer, logging_level])

            while ((queued_processes + busy_processes) < max_games and challenge_queue):  # keep processing the queue until empty or max_games is reached
                chlng = challenge_queue.pop(0)
                try:
                    logger.info("Accept {}".format(chlng))
                    queued_processes += 1
                    li.accept_challenge(chlng.id)
                    logger.info("--- Process Queue. Total Queued: {}. Total Used: {}".format(queued_processes, busy_processes))
                except (HTTPError, ReadTimeout) as exception:
                    if isinstance(exception, HTTPError) and exception.response.status_code == 404:  # ignore missing challenge
                        logger.info("Skip missing {}".format(chlng))
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
def play_game(li, game_id, control_queue, engine_factory, user_profile, config, challenge_queue, correspondence_queue, logging_queue, logging_configurer, logging_level):
    logging_configurer(logging_queue, logging_level)
    logger = logging.getLogger(__name__)

    response = li.get_game_stream(game_id)
    lines = response.iter_lines()

    # Initial response of stream will be the full game info. Store it
    initial_state = json.loads(next(lines).decode('utf-8'))
    game = model.Game(initial_state, user_profile["username"], li.baseUrl, config.get("abort_time", 20))

    initial_time = (game.state['wtime'] if game.my_color == "white" else game.state['btime']) / 1000
    variant = parse_variant(game.variant_name)
    engine = engine_factory(variant, initial_time)
    conversation = Conversation(game, engine, li, __version__, challenge_queue)

    logger.info("+++ {}".format(game))

    is_correspondence = game.perf_name == "Correspondence"
    correspondence_cfg = config.get("correspondence", {}) or {}
    correspondence_move_time = correspondence_cfg.get("move_time", 60) * 1000

    engine_cfg = config["engine"]
    ponder_cfg = correspondence_cfg if is_correspondence else engine_cfg
    can_ponder = ponder_cfg.get('ponder', False) and engine_cfg['protocol'] in ['hub', 'strategy']
    move_overhead = config.get("move_overhead", 1000)
    move_overhead_inc = config.get("move_overhead_inc", 100)
    delay_seconds = config.get("rate_limiting_delay", 0)/1000
    greeting_cfg = config.get("greeting", {}) or {}
    keyword_map = defaultdict(str, me=game.me.name, opponent=game.opponent.name)
    get_greeting = lambda greeting: str(greeting_cfg.get(greeting, "") or "").format_map(keyword_map)
    hello = get_greeting("hello")
    goodbye = get_greeting("goodbye")
    board = draughts.Game(game.variant_name.lower(), game.initial_fen)
    moves, old_moves = [], []

    ponder_thread = None
    ponder_uci = None

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
                upd = json.loads(binary_chunk.decode('utf-8')) if binary_chunk else None

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
                        board.push_move(move)
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
                        best_move = get_pondering_results(ponder_thread, ponder_uci, game, board, engine)
                        if best_move.move is None:
                            best_move = choose_move(engine, board, game, draw_offered, start_time, move_overhead, move_overhead_inc)
                    move_attempted = True
                    if best_move.resign:
                        li.resign(game.id)
                    else:
                        li.make_move(game.id, best_move)
                    ponder_thread, ponder_uci = start_pondering(engine, board, game, can_ponder, best_move, start_time, move_overhead, move_overhead_inc)
                    time.sleep(delay_seconds)
                elif is_game_over(board):
                    conversation.send_message("player", goodbye)
                elif len(board.move_stack) == 0:
                    correspondence_disconnect_time = correspondence_cfg.get("disconnect_time", 300)

                wb = 'w' if board.whose_turn() == draughts.WHITE else 'b'
                game.ping(config.get("abort_time", 20), (upd[f"{wb}time"] + upd[f"{wb}inc"]) / 1000 + 60, correspondence_disconnect_time)
            elif u_type == "ping":
                if is_correspondence and not is_engine_move(game, board) and game.should_disconnect_now():
                    break
                elif game.should_abort_now():
                    logger.info("Aborting {} by lack of activity".format(game.url()))
                    li.abort(game.id)
                    break
                elif game.should_terminate_now():
                    logger.info("Terminating {} by lack of activity".format(game.url()))
                    if game.is_abortable():
                        li.abort(game.id)
                    break
        except (HTTPError, ReadTimeout, RemoteDisconnected, ChunkedEncodingError, ConnectionError, ProtocolError):
            if move_attempted:
                continue
            if game.id not in (ongoing_game["gameId"] for ongoing_game in li.get_ongoing_games()):
                break
        except StopIteration:
            break

    engine.stop()
    engine.quit()
    if ponder_thread is not None:
        ponder_thread.join()
    engine.kill_process()

    if is_correspondence and not is_game_over(board):
        logger.info("--- Disconnecting from {}".format(game.url()))
        correspondence_queue.put(game_id)
    else:
        logger.info("--- {} Game over".format(game.url()))

    control_queue.put_nowait({"type": "local_game_done"})


def parse_variant(variant):
    variant = variant.lower()

    if variant in ["standard", "fromposition"]:
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
    logger.info("Searching for time {}".format(search_time))
    return engine.search_for(board, search_time, draw_offered)


def choose_first_move(engine, board, draw_offered):
    # need to hardcode first movetime (10000 ms) since Lidraughts has 30 sec limit.
    return choose_move_time(engine, board, 10000, draw_offered)


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

    logger.info("Searching for wtime {} btime {}".format(wtime, btime))
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

    logger.info("Pondering for wtime {} btime {}".format(wtime, btime))
    ponder_thread = threading.Thread(target=ponder_thread_func, args=(game, engine, ponder_board, wtime, btime, winc, binc))
    ponder_thread.start()
    return ponder_thread, best_move.ponder.li_one_move


def get_pondering_results(ponder_thread, ponder_uci, game, board, engine):
    no_move = PlayResult(None, None)
    if ponder_thread is None:
        return no_move

    move_uci = board.move_stack[-1].li_one_move
    if ponder_uci == move_uci:
        engine.ponderhit()
        ponder_thread.join()
        return ponder_results[game.id]
    else:
        engine.stop()
        ponder_thread.join()
        return no_move


def check_for_draw_offer(game):
    return game.state.get(f'{game.opponent_color[0]}draw', False)


def fake_thinking(config, board, game):
    if config.get("fake_think_time") and len(board.move_stack) > 9:
        delay = min(game.clock_initial, game.my_remaining_seconds()) * 0.015
        accel = 1 - max(0, min(100, len(board.move_stack) - 20)) / 150
        sleep = min(5, delay * accel)
        time.sleep(sleep)


def print_move_number(board):
    logger.info("")
    logger.info("move: {}".format(len(board.move_stack) // 2 + 1))


def is_engine_move(game, board):
    return game.is_white == (board.whose_turn() == draughts.WHITE)


def is_game_over(board):
    return board.is_over()


def intro():
    return r"""
    .   _/|
    .  // o\
    .  || ._)  lidraughts-bot %s
    .  //__\
    .  )___(   Play on Lidraughts with a bot
    """ % __version__


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Play on Lidraughts with a bot')
    parser.add_argument('-u', action='store_true', help='Add this flag to upgrade your account to a bot account.')
    parser.add_argument('-v', action='store_true', help='Verbose output. Changes log level from INFO to DEBUG.')
    parser.add_argument('--config', help='Specify a configuration file (defaults to ./config.yml)')
    parser.add_argument('-l', '--logfile', help="Log file to append logs to.", default=None)
    args = parser.parse_args()

    logging_level = logging.DEBUG if args.v else logging.INFO
    logging.basicConfig(level=logging_level, filename=args.logfile,
                        format="%(asctime)-15s: %(message)s")
    enable_color_logging(debug_lvl=logging_level)
    logger.info(intro())
    CONFIG = load_config(args.config or "./config.yml")
    li = lidraughts.Lidraughts(CONFIG["token"], CONFIG["url"], __version__, logging_level)

    user_profile = li.get_profile()
    username = user_profile["username"]
    is_bot = user_profile.get("title") == "BOT"
    logger.info("Welcome {}!".format(username))

    if args.u and not is_bot:
        is_bot = upgrade_account(li)

    if is_bot:
        engine_factory = partial(engine_wrapper.create_engine, CONFIG)
        start(li, user_profile, engine_factory, CONFIG, logging_level, args.logfile)
    else:
        logger.error("{} is not a bot account. Please upgrade it to a bot account!".format(user_profile["username"]))
