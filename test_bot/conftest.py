import shutil
import os


def pytest_sessionfinish(session, exitstatus):
    shutil.copyfile("correct_lidraughts.py", "lidraughts.py")
    os.remove("correct_lidraughts.py")
    if os.path.exists("TEMP"):
        shutil.rmtree("TEMP")
    if os.path.exists("logs"):
        shutil.rmtree("logs")

    # Engine files
    if os.path.exists("data"):
        shutil.rmtree("data")
    if os.path.exists("scan.ini"):
        os.remove("scan.ini")

    if os.path.exists("kr_hub.ini"):
        os.remove("kr_hub.ini")
    if os.path.exists("KingsRow.odb"):
        os.remove("KingsRow.odb")
    if os.path.exists("weights.bin"):
        os.remove("weights.bin")
