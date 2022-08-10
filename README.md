# lidraughts-bot
[![Python Build](https://github.com/AttackingOrDefending/lidraughts-bot/actions/workflows/python-build.yml/badge.svg)](https://github.com/AttackingOrDefending/lidraughts-bot/actions/workflows/python-build.yml)
[![Python Test](https://github.com/AttackingOrDefending/lidraughts-bot/actions/workflows/python-test.yml/badge.svg)](https://github.com/AttackingOrDefending/lidraughts-bot/actions/workflows/python-test.yml)
[![CodeQL](https://github.com/AttackingOrDefending/lidraughts-bot/actions/workflows/codeql-analysis.yml/badge.svg)](https://github.com/AttackingOrDefending/lidraughts-bot/actions/workflows/codeql-analysis.yml)

A bridge between [Lidraughts Bot API](https://lidraughts.org/api#tag/Bot) and bots.

## How to Install
### Mac/Linux:
- **NOTE: Only Python 3.8 or later is supported!**
- Download the repo into lidraughts-bot directory.
- Navigate to the directory in cmd/Terminal: `cd lidraughts-bot`.
- Install pip: `apt install python3-pip`.
- Install virtualenv: `pip install virtualenv`.
- Setup virtualenv: `apt install python3-venv`.
```python
python3 -m venv venv # If this fails you probably need to add Python3 to your PATH.
virtualenv venv -p python3 # If this fails you probably need to add Python3 to your PATH.
source ./venv/bin/activate
python3 -m pip install -r requirements.txt
```
- Copy `config.yml.default` to `config.yml`.
- Edit the variants: `supported_variants` and time controls: `supported_tc` from the `config.yml` file as necessary.

### Windows:
- [Here is a video on how to install the bot](https://youtu.be/w-aJFk00POQ) (it is for lichess-bot but most steps are the same). Or you may proceed to the following steps.
- **NOTE: Only Python 3.8 or later is supported!**
- If you don't have Python, you may [download it here](https://www.python.org/downloads/). When installing it, enable "add Python to PATH", then go to custom installation (this may be not necessary, but on some computers it won't work otherwise) and enable all options (especially "install for all users"), except the last. It's better to install Python in a path without spaces, like "C:\Python\".
- To type commands it's better to use PowerShell. Go to the Start menu and type "PowerShell" (you may use "cmd" too, but sometimes it may not work).
- Then you may need to upgrade pip. Execute `python3 -m pip install --upgrade pip` in PowerShell.
- Download the repo into lidraughts-bot directory.
- Navigate to the directory in PowerShell: `cd [folder's address]` (example, `cd C:\draughts\lidraughts-bot`).
- Install virtualenv: `pip install virtualenv`.
- Setup virtualenv:
```python
python3 -m venv .venv # If this fails you probably need to add Python3 to your PATH.
./.venv/Scripts/Activate.ps1 # `.\.venv\Scripts\activate.bat` should work in cmd in administrator mode. This may not work on Windows, and in this case you need to execute "Set-ExecutionPolicy RemoteSigned" first and choose "Y" there (you may need to run Powershell as administrator). After you execute the script, change execution policy back with "Set-ExecutionPolicy Restricted" and pressing "Y".
pip install -r requirements.txt
```
- Copy `config.yml.default` to `config.yml`.
- Edit the variants: `supported_variants` and time controls: `supported_tc` from the `config.yml` file as necessary (use "#" to disable certain ones).

### Heroku:
- See [here](heroku/README.md)

## Lidraughts OAuth
- Create an account for your bot on [Lidraughts.org](https://lidraughts.org/signup).
- **NOTE: If you have previously played games on an existing account, you will not be able to use it as a bot account.**
- Once your account has been created and you are logged in, [create a personal OAuth2 token with the "Play games with the bot API" ('bot:play') scope](https://lidraughts.org/account/oauth/token/create) selected and a description added.
- A `token` (e.g. `xxxxxxxxxxxxxxxx`) will be displayed. Store this in the `config.yml` file as the `token` field. You can also set the token in the environment variable `$LIDRAUGHTS_BOT_TOKEN`.
- **NOTE: You won't see this token again on Lidraughts, so do save it.**

## Setup Engine
Within the file `config.yml`:
- Enter the directory containing the engine executable in the `engine: dir` field.
- Enter the executable name in the `engine: name` field (In Windows you may need to type a name with ".exe", like "lczero.exe")
- If you want the engine to run in a different directory (e.g., if the engine needs to read or write files at a certain location), enter that directory in the `engine: working_dir` field.
  - If this field is blank or missing, the current directory will be used.

As an optional convenience, there is a folder named `engines` within the lidraughts-bot folder where you can copy your engine and all the files it needs. This is the default executable location in the `config.yml.default` file.

### Engine Configuration
Besides the above, there are many possible options within `config.yml` for configuring the engine for use with lidraughts-bot.

- `protocol`: Specify which protocol your engine uses. Choices are
    1. `"hub"` for the [Hub](https://github.com/rhalbersma/scan/blob/master/protocol.txt)
    2. `"dxp"` for the [DXP](http://www.mesander.nl/damexchange/edxpmain.htm)
    3. `"cb"` for the [CheckerBoard](https://github.com/eygilbert/CheckerBoard/blob/master/cb_api_reference.htm)
    4. `"homemade"` if you want to write your own engine in Python within lidraughts-bot. See [**Creating a homemade bot**](#creating-a-homemade-bot) below.
- `ponder`: Specify whether your bot will ponder--i.e., think while the bot's opponent is choosing a move.
- `draw_or_resign`: This section allows your bot to resign or offer/accept draw based on the evaluation by the engine.
    - `resign_enabled`: Whether the bot is allowed to resign based on the evaluation.
    - `resign_score`: The engine evaluation has to be less than or equal to `resign_score` for the bot to resign.
    - `resign_moves`: The evaluation has to be less than or equal to `resign_score` for `resign_moves` amount of moves for the bot to resign.
    - `offer_draw_enabled`: Whether the bot is allowed to offer/accept draw based on the evaluation.
    - `offer_draw_score`: The absolute value of the engine evaluation has to be less than or equal to `offer_draw_score` for the bot to offer/accept draw.
    - `offer_draw_moves`: The absolute value of the evaluation has to be less than or equal to `offer_draw_score` for `offer_draw_moves` amount of moves for the bot to offer/accept draw.
    - `offer_draw_pieces`: The bot only offers/accepts draws if the position has less than or equal to `offer_draw_pieces` pieces.
- `engine_options`: Command line options to pass to the engine on startup. For example, the `config.yml.default` has the configuration
```yml
  engine_options:
    cpuct: 3.1
```
This would create the command-line option `--cpuct=3.1` to be used when starting the engine, like this for the engine lc0: `lc0 --cpuct=3.1`. Any number of options can be listed here, each getting their own command-line option.
- `hub_options`: A list of options to pass to a Hub engine after startup. Different engines have different options, so treat the options in `config.yml.default` as templates and not suggestions. When Hub engines start, they print a list of configurations that can modify their behavior after receiving the string "hub". For example, to find out what options Scan 3.1 supports, run the executable in a terminal, type `hub`, and press Enter. The engine will print the following when run at the command line:
```
id name=Scan version=3.1 author="Fabien Letouzey" country=France
param name=variant value=normal type=enum values="normal killer bt frisian losing"
param name=book value=true type=bool
param name=book-ply value=4 type=int min=0 max=20
param name=book-margin value=4 type=int min=0 max=100
param name=ponder value=false type=bool
param name=threads value=1 type=int min=1 max=16
param name=tt-size value=24 type=int min=16 max=30
param name=bb-size value=0 type=int min=0 max=7
wait
```
Any of the names following `param name=` can be listed in `hub_options` in order to configure the Scan engine.
```yml
  hub_options:
    book-ply: 15
    book-margin: 10
```
The exception to this is the option `variant`. These will be handled by lidraughts-bot after a game starts and should not be listed in `config.yml`. Also, if an option is listed under `hub_options` that is not in the list printed by the engine, it will cause an error when the engine starts because the engine won't understand the option. The word after `type` indicates the expected type of the options: `string` for a text string, `int` for a numeric value, `bool` for a boolean True/False value.

One last option is `go_commands`. Beneath this option, arguments to the Hub `level` command can be passed. For example,
```yml
  go_commands:
    movetime: 1000
```
will send `level move-time=1000` to inform the engine on the time it should use.

- `dxp_options`: A list of options to send to pydraughts about the engine. These are:
```
engine-opened
ip
port
wait-to-open-time
max-moves
initial-time
```
The exceptions to this are the options `max-moves`, and `initial-time`. These will be handled by lidraughts-bot after a game starts and should not be listed in `config.yml`. Also, if an option is listed under `dxp_options` that is not in the list printed by the engine, it will cause an error when the engine starts because the engine won't know how to handle the option.

- `cb_options`: A list of options to pass to a CheckerBoard engine after startup. Different engines have different options, so treat the options in `config.yml.default` as templates and not suggestions. There are no standard options for the engine parameters. Some possible options are:
```
hashsize
book
dbmbytes
```
See [here](https://github.com/eygilbert/CheckerBoard/blob/master/cb_api_reference.htm) for many possible options for the engine. There is also `divide-time-by` which is sent to pydraughts.

- `abort_time`: How many seconds to wait before aborting a game due to opponent inaction. This only applies during the first six moves of the game.
- `fake_think_time`: Artificially slow down the engine to simulate a person thinking about a move. The amount of thinking time decreases as the game goes on.
- `rate_limiting_delay`: For extremely fast games, the lidraughts.org servers may respond with an error if too many moves are played too quickly. This option avoids this problem by pausing for a specified number of milliseconds after submitting a move before making the next move.
- `move_overhead`: To prevent losing on time due to network lag, subtract this many milliseconds from the time to think on each move.
- `move_overhead_inc`: To prevent losing on time due to network lag, subtract this many milliseconds from the time to think on each move.


- `correspondence` These options control how the engine behaves during correspondence games.
  - `move_time`: How many seconds to think for each move.
  - `checkin_period`: How often (in seconds) to reconnect to games to check for new moves after disconnecting.
  - `disconnect_time`: How many seconds to wait after the bot makes a move for an opponent to make a move. If no move is made during the wait, disconnect from the game.
  - `ponder`: Whether the bot should ponder during the above waiting period.

- `challenge`: Control what kind of games for which the bot should accept challenges. All of the following options must be satisfied by a challenge to be accepted.
  - `concurrency`: The maximum number of games to play simultaneously.
  - `sort_by`: Whether to start games by the best rated/titled opponent `"best"` or by first-come-first-serve `"first"`.
  - `accept_bot`: Whether to accept challenges from other bots.
  - `only_bot`: Whether to only accept challenges from other bots.
  - `max_increment`: The maximum value of time increment.
  - `min_increment`: The minimum value of time increment.
  - `max_base`: The maximum base time for a game.
  - `min_base`: The minimum base time for a game.
  - `variants`: An indented list of draughts variants that the bot can handle.
```yml
  variants:
    - standard
    - frisian
    - frysk!
    # etc.
```
  - `time_controls`: An indented list of acceptable time control types from `bullet` to `correspondence`.
```yml
  time_controls:
    - bullet
    - blitz
    - rapid
    - classical
    - correspondence
```
  - `modes`: An indented list of acceptable game modes (`rated` and/or `casual`).
```yml
  modes:
    -rated
    -casual
```
  - `greeting`: Send messages via chat to the bot's opponent. The string `{me}` will be replaced by the bot's lidraughts account name. The string `{opponent}` will be replaced by the opponent's lidraughts account name. Any other word between curly brackets will be removed. If you want to put a curly bracket in the message, use two: `{{` or `}}`.
    - `hello`: Message to send to the opponent when the bot makes its first move.
    - `goodbye`: Message to send to the opponent once the game is over.
    - `hello_spectators`: Message to send to the spectators when the bot makes its first move.
    - `goodbye_spectators`: Message to send to the spectators once the game is over.
```yml
  greeting:
    hello: Hi, {opponent}! I'm {me}. Good luck!
    goodbye: Good game!
    hello_spectators: "Hi! I'm {me}. Type !help for a list of commands I can respond to." # Message to send to spectator chat at the start of a game
    goodbye_spectators: "Thanks for watching!" # Message to send to spectator chat at the end of a game
```
  - `pgn_directory`: Write a record of every game played in PGN format to files in this directory. Each bot move will be annotated with the bot's calculated score and principal variation. The score is written with a tag of the form `[%eval s,d]`, where `s` is the score in pawns (positive means white has the advantage), and `d` is the depth of the search. Each game will be written to a uniquely named file.
```yml
  pgn_directory: "game_records"
```

## Lidraughts Upgrade to Bot Account
**WARNING: This is irreversible. [Read more about upgrading to bot account](https://lidraughts.org/api#operation/botAccountUpgrade).**
- run `python3 lidraughts-bot.py -u`.

## To Run
After activating the virtual environment created in the installation steps (the `source` line for Linux and Macs or the `activate` script for Windows), run
```
python3 lidraughts-bot.py
```
The working directory for the engine execution will be the lidraughts-bot directory. If your engine requires files located elsewhere, make sure they are specified by absolute path or copy the files to an appropriate location inside the lidraughts-bot directory.

To output more information (including your engine's thinking output and debugging information), the `-v` option can be passed to lidraughts-bot:
```
python3 lidraughts-bot.py -v
```

If you want to record the output to a log file, add the `-l` or `--logfile` along with a file name:
```
python3 lidraughts-bot.py --logfile log.txt
```

## To Quit
- Press `CTRL+C`.
- It may take some time to quit.

## <a name="creating-a-homemade-bot"></a> Creating a homemade bot
As an alternative to creating an entire draughts engine and implementing one of the communication protocols (`Hub` or `DXP`), a bot can also be created by writing a single class with a single method. The `search()` method in this new class takes the current board and the game clock as arguments and should return a move based on whatever criteria the coder desires.

Steps to create a homemade bot:

1. Do all the steps in the [How to Install](#how-to-install)
2. In the `config.yml`, change the engine protocol to `homemade`
3. Create a class in some file that extends `MinimalEngine` (in `strategies.py`).
    - Look at the `strategies.py` file to see some examples.
    - If you don't know what to implement, look at the `EngineWrapper` or `HubEngine` class.
        - You don't have to create your own engine, even though it's an "EngineWrapper" class.<br>
The examples just implement `search`.
4. In the `config.yml`, change the name from `engine_name` to the name of your class
    - In this case, you could change it to:

        `name: "RandomMove"`

## Tips & Tricks
- You can specify a different config file with the `--config` argument.
- Here's an example systemd service definition:
```ini
[Unit]
Description=lidraughts-bot
After=network-online.target
Wants=network-online.target

[Service]
Environment="PYTHONUNBUFFERED=1"
ExecStart=/usr/bin/python3 /home/attackingordefending/lidraughts-bot/lidraughts-bot.py
WorkingDirectory=/home/attackingordefending/lidraughts-bot/
User=attackingordefending
Group=attackingordefending
Restart=always

[Install]
WantedBy=multi-user.target
```

# Acknowledgements
Thanks to the Lichess Team for creating a [repository](https://github.com/ShailChoksi/lichess-bot) that could be easily modified to a format that supports Lidraughts. Thanks to [RoepStoep](https://github.com/RoepStoep) for running an [API](https://lidraughts.org/api) to communicate with the BOTs. Thanks to [AttackingOrDefending](https://github.com/AttackingOrDefending) and his [pydraughts](https://github.com/AttackingOrDefending/pydraughts) code which allows engine communication seamlessly.

# License
lidraughts-bot is licensed under the AGPLv3 (or any later version at your option). Check out the [LICENSE file](/LICENSE) for the full text.
