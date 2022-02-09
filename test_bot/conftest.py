import pytest
import shutil
import os


def pytest_sessionfinish(session, exitstatus):
    shutil.copyfile('correct_lidraughts.py', 'lidraughts.py')
    os.remove('correct_lidraughts.py')
    if os.path.exists('TEMP'):
        shutil.rmtree('TEMP')
    if os.path.exists('logs'):
        shutil.rmtree('logs')

    # Engine files
    if os.path.exists('data'):
        shutil.rmtree('data')
    os.remove('scan.ini')

    os.remove('kr_hub.ini')
    os.remove('KingsRow.odb')
    os.remove('weights.bin')
