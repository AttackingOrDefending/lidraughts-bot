import pytest
import zipfile
import requests
import time
import yaml
import draughts
import draughts.engine
import threading
import os
import sys
import stat
import shutil
import importlib
if __name__ == "__main__":
    sys.exit(f"The script {os.path.basename(__file__)} should only be run by pytest.")
shutil.copyfile("lidraughts.py", "correct_lidraughts.py")
shutil.copyfile("test_bot/lidraughts.py", "lidraughts.py")
lidraughts_bot = importlib.import_module("lidraughts-bot")

platform = sys.platform
file_extension = ".exe" if platform == "win32" else ""
hub_engine_path = f"./TEMP/kr_hub{file_extension}"


def download_scan():
    windows_linux_mac = ""
    if platform == "linux":
        windows_linux_mac = "_linux"
    elif platform == "darwin":
        windows_linux_mac = "_mac"
    response = requests.get("https://hjetten.home.xs4all.nl/scan/scan_31.zip", allow_redirects=True)
    with open("./TEMP/scan_zip.zip", "wb") as file:
        file.write(response.content)
    with zipfile.ZipFile("./TEMP/scan_zip.zip", "r") as zip_ref:
        zip_ref.extractall("./TEMP/")
    shutil.copyfile(f"./TEMP/scan_31/scan{windows_linux_mac}{file_extension}", f"./TEMP/scan{file_extension}")
    shutil.copyfile("./TEMP/scan_31/scan.ini", "scan.ini")
    if os.path.exists("data"):
        shutil.rmtree("data")
    shutil.copytree("./TEMP/scan_31/data", "data")
    if windows_linux_mac != "":
        st = os.stat(f"./TEMP/scan{file_extension}")
        os.chmod(f"./TEMP/scan{file_extension}", st.st_mode | stat.S_IEXEC)


def download_kr():
    headers = {'User-Agent': 'User Agent', 'From': 'mail@mail.com'}
    response = requests.get("http://edgilbert.org/InternationalDraughts/downloads/kr_hub_163.zip",
                            headers=headers, allow_redirects=True)
    with open("./TEMP/kr_zip.zip", "wb") as file:
        file.write(response.content)
    with zipfile.ZipFile("./TEMP/kr_zip.zip", "r") as zip_ref:
        zip_ref.extractall("./TEMP/")
    shutil.copyfile("./TEMP/kr_hub.ini", "kr_hub.ini")
    shutil.copyfile("./TEMP/KingsRow.odb", "KingsRow.odb")
    shutil.copyfile("./TEMP/weights.bin", "weights.bin")


if os.path.exists("TEMP"):
    shutil.rmtree("TEMP")
os.mkdir("TEMP")
if platform == "win32":
    download_scan()
    download_kr()
logging_level = lidraughts_bot.logging.INFO
lidraughts_bot.logging_configurer(logging_level, None)
lidraughts_bot.logger.info("Downloaded engines")


def run_bot(CONFIG, logging_level):
    lidraughts_bot.logger.info(lidraughts_bot.intro())
    li = lidraughts_bot.lidraughts.Lidraughts(CONFIG["token"], CONFIG["url"], lidraughts_bot.__version__)

    user_profile = li.get_profile()
    username = user_profile["username"]
    is_bot = user_profile.get("title") == "BOT"
    lidraughts_bot.logger.info(f"Welcome {username}!")

    if not is_bot:
        is_bot = lidraughts_bot.upgrade_account(li)

    if is_bot:
        def run_test():

            def thread_for_test():
                open("./logs/events.txt", "w").close()
                open("./logs/states.txt", "w").close()
                open("./logs/result.txt", "w").close()

                start_time = 10
                increment = 0.1

                board = draughts.Game()
                wtime = start_time
                btime = start_time

                with open("./logs/states.txt", "w") as file:
                    file.write(f"\n{wtime},{btime}")

                engine = draughts.engine.HubEngine(hub_engine_path)
                engine.init()

                while True:
                    if board.is_over():
                        with open("./logs/events.txt", "w") as file:
                            file.write("end")
                        break

                    if len(board.move_stack) % 2 == 0:
                        if not board.move_stack:
                            move = engine.play(board, draughts.engine.Limit(time=1), ponder=False)
                        else:
                            start_time = time.perf_counter_ns()
                            move = engine.play(board, draughts.engine.Limit(movetime=0.0001), ponder=False)
                            end_time = time.perf_counter_ns()
                            wtime -= (end_time - start_time) / 1e9
                            wtime += increment
                        for move_part in move.move.li_api_move:
                            board.push_str_move(move_part)

                        with open("./logs/states.txt") as states:
                            state = states.read().split("\n")
                        for move_part in move.move.li_api_move:
                            state[0] += f" {move_part}"
                        state = "\n".join(state)
                        with open("./logs/states.txt", "w") as file:
                            file.write(state)

                    else:  # lidraughts-bot move
                        start_time = time.perf_counter_ns()
                        while True:
                            with open("./logs/states.txt") as states:
                                state2 = states.read()
                            time.sleep(0.001)
                            moves = state2.split("\n")[0]
                            temp_board = draughts.Game()
                            moves_are_correct = True
                            for move in moves.split():
                                try:
                                    temp_board.push_str_move(move)
                                except ValueError:
                                    moves_are_correct = False
                            if state != state2 and moves_are_correct:
                                break
                        with open("./logs/states.txt") as states:
                            state2 = states.read()
                        end_time = time.perf_counter_ns()
                        if len(board.move_stack) > 1:
                            btime -= (end_time - start_time) / 1e9
                            btime += increment
                        moves = state2.split("\n")[0]
                        old_moves = state.split("\n")[0]
                        move = moves[len(old_moves):]
                        for move_part in move.split():
                            board.push_str_move(move_part)

                    time.sleep(0.001)
                    with open("./logs/states.txt") as states:
                        state = states.read().split("\n")
                    state[1] = f"{wtime},{btime}"
                    state = "\n".join(state)
                    with open("./logs/states.txt", "w") as file:
                        file.write(state)

                engine.quit()
                engine.kill_process()
                win = board.has_player_won(draughts.BLACK) and board.whose_turn() == draughts.WHITE
                with open("./logs/result.txt", "w") as file:
                    file.write("1" if win else "0")

            thr = threading.Thread(target=thread_for_test)
            thr.start()
            lidraughts_bot.start(li, user_profile, CONFIG, logging_level, None, one_game=True)
            thr.join()

        run_test()

        with open("./logs/result.txt") as file:
            data = file.read()
        return data

    else:
        lidraughts_bot.logger.error(f'{user_profile["username"]} is not a bot account. Please upgrade it to a bot account!')


@pytest.mark.timeout(150, method="thread")
def test_scan():
    if platform != "win32":
        assert True
        return
    if os.path.exists("logs"):
        shutil.rmtree("logs")
    os.mkdir("logs")
    with open("./config.yml.default") as file:
        CONFIG = yaml.safe_load(file)
    CONFIG["token"] = ""
    CONFIG["engine"]["dir"] = "./TEMP/"
    CONFIG["engine"]["name"] = f"scan{file_extension}"
    CONFIG["engine"]["working_dir"] = ""
    CONFIG["engine"]["ponder"] = False
    CONFIG["pgn_directory"] = "TEMP/scan_game_record"
    win = run_bot(CONFIG, logging_level)
    shutil.rmtree("logs")
    lidraughts_bot.logger.info("Finished Testing Scan")
    assert win == "1"
    assert os.path.isfile(os.path.join(CONFIG["pgn_directory"], "bo vs b - zzzzzzzz.pgn"))


@pytest.mark.timeout(150, method="thread")
def test_homemade():
    if platform != "win32":
        assert True
        return
    with open("strategies.py") as file:
        original_strategies = file.read()
    with open("strategies.py", "a") as file:
        file.write(f"""
class Scan(ExampleEngine):
    def __init__(self, commands, options, stderr, draw_or_resign, **popen_args):
        super().__init__(commands, options, stderr, draw_or_resign, **popen_args)
        self.engine = draughts.engine.HubEngine(['./TEMP/scan{file_extension}', 'hub'])
        self.engine.init()
    def search(self, board, time_limit, *args):
        return self.engine.play(board, time_limit, False)""")
    if os.path.exists("logs"):
        shutil.rmtree("logs")
    os.mkdir("logs")
    with open("./config.yml.default") as file:
        CONFIG = yaml.safe_load(file)
    CONFIG["token"] = ""
    CONFIG["engine"]["name"] = "Scan"
    CONFIG["engine"]["protocol"] = "homemade"
    CONFIG["pgn_directory"] = "TEMP/homemade_game_record"
    win = run_bot(CONFIG, logging_level)
    shutil.rmtree("logs")
    with open("strategies.py", "w") as file:
        file.write(original_strategies)
    lidraughts_bot.logger.info("Finished Testing Homemade")
    assert win == "1"
    assert os.path.isfile(os.path.join(CONFIG["pgn_directory"], "bo vs b - zzzzzzzz.pgn"))
