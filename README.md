# lidraughts-bot

[![Python Build](https://github.com/AttackingOrDefending/lidraughts-bot/actions/workflows/python-build.yml/badge.svg)](https://github.com/AttackingOrDefending/lidraughts-bot/actions/workflows/python-build.yml) [![CodeQL](https://github.com/AttackingOrDefending/lidraughts-bot/actions/workflows/codeql-analysis.yml/badge.svg)](https://github.com/AttackingOrDefending/lidraughts-bot/actions/workflows/codeql-analysis.yml)

A bridge between [Lidraughts API](https://lidraughts.org/api#tag/Bot) and bots.


## How to Install

### Mac/Linux:
- NOTE: Only Python 3.7 or later is supported!
- Download the repo into lidraughts-bot directory
- Navigate to the directory in cmd/Terminal: `cd lidraughts-bot`
- Install pip: `apt install python3-pip`
- Install virtualenv: `pip install virtualenv`
- Setup virtualenv: `apt install python3-venv`
```
python3 -m venv venv #if this fails you probably need to add Python3 to your PATH
virtualenv venv -p python3 #if this fails you probably need to add Python3 to your PATH
source ./venv/bin/activate
python3 -m pip install -r requirements.txt
```
- Copy `config.yml.default` to `config.yml`
- Edit the variants: `supported_variants` and time controls: `supported_tc` from the config.yml as necessary

### Windows:
- NOTE: Only Python 3.7 or later is supported!
- If you don't have Python, you may download it [here](https://www.python.org/downloads/). When installing it, enable `add Python to PATH`, then go to custom installation (this may be not necessary, but on some computers it won't work otherwise) and enable all options (especially "install for all users"), except the last . It's better to install Python in a path without spaces, like `C:\Python\`.
- To type commands it's better to use PowerShell. Go to Start menu and type `PowerShell`(you may use cmd too, but sometimes it may not work).
- Then you may need to upgrade pip. Execute `python -m pip install --upgrade pip` in PowerShell.
- Download the repo into lidraughts-bot directory.
- Navigate to the directory in PowerShell: `cd [folder's adress]` (like `cd C:\draughts\lidraughts-bot`).
- Install virtualenv: `pip install virtualenv`.
- Setup virtualenv:
```
python -m venv .venv (if this fails you probably need to add Python to your PATH)
./.venv/Scripts/Activate.ps1 (.\.venv\Scripts\activate.bat should work in cmd in administator mode) (This may not work on Windows, and in this case you need to execute "Set-ExecutionPolicy RemoteSigned" first and choose "Y" there [you may need to run Powershell as administrator]. After you executed the script, change execution policy back with "Set-ExecutionPolicy Restricted" and pressing "Y")
pip install -r requirements.txt
```
- Copy `config.yml.default` to `config.yml`
- Edit the variants: `supported_variants` and time controls: `supported_tc` from the config.yml as necessary (use # to disable certain ones)

## Heroku:
- See [here](heroku/README.md)


## Lidraughts OAuth
- Create an account for your bot on [Lidraughts.org](https://lidraughts.org/signup)
- NOTE: If you have previously played games on an existing account, you will not be able to use it as a bot account
- Once your account has been created and you are logged in, [create a personal OAuth2 token](https://lidraughts.org/account/oauth/token/create?scopes[]=bot:play&description=lidraughts-bot) with the "Play as a bot" selected and add a description
- A `token` e.g. `Xb0ddNrLabc0lGK2` will be displayed. Store this in `config.yml` as the `token` field. You can also set the token in the environment variable `$LIDRAUGHTS_BOT_TOKEN`.
- NOTE: You won't see this token again on Lidraughts.


## Setup Engine
- Place your engine(s) in the `engine.dir` directory
- In `config.yml`, enter the binary name as the `engine.name` field (In Windows you may need to type a name with ".exe", like "lczero.exe")


## Lidraughts Upgrade to Bot Account
**WARNING** This is irreversible. [Read more about upgrading to bot account](https://lidraughts.org/api#operation/botAccountUpgrade).
- run `python lidraughts-bot.py -u`

## To Quit
- Press CTRL+C
- It may take some time to quit

## Creating a homemade bot

As an alternative to creating an entire draughts engine and implementing one of the communiciation protocols (e.g. Hub), a bot can also be created by writing a single class with a single method. The `search()` method in this new class takes the current board and the game clock as arguments and should return a move based on whatever criteria the coder desires.

Steps to create a homemade bot:

1. Do all the steps in the [How to Install](#how-to-install)
2. In the `config.yml`, change the engine protocol to `homemade`
3. Create a class in some file that extends `MinimalEngine` (in `strategies.py`).
    - Look at the `strategies.py` file to see some examples.
    - If you don't know what to implement, look at the `EngineWrapper` or `HubEngine` class.
        - You don't have to create your own engine, even though it's an "EngineWrapper" class.<br>
          The examples just implement `search`.
4. In the `config.yml`, change the name from engine_name to the name of your class
    - In this case, you could change it to:

      `name: "RandomMove"`

### Engine Configuration
Besides the above, there are many possible options within `config.yml` for configuring the engine for use with lishogi-bot.
- `protocol`: Specify which protocol your engine uses. `"usi" "hub", "dxp", "cb" (checkerboard) or "strategy"` are supported protocols.
- `ponder`: Specify whether your bot will ponder, i.e., think while the bot's opponent is choosing a move.
- `engine_options`: Command line options to pass to the engine on startup. For example, the `config.yml.default` has the configuration
```yml
  engine_options:
    cpuct: 3.1
```
This would create the command-line option `--cpuct=3.1` to be used when starting the engine. Any number of options can be listed here, each getting their own command-line option.
- `hub_options`: A list of options to pass to a HUB engine after startup. Different engines have different options, so treat the options in `config.yml.default` as templates and not suggestions. When USI engines start, they print a list of configurations that can modify their behavior. For example, Scan 3.1 prints the hub options when run at the command line (`./scan`):

Any of the names following `option name` can be listed in `hub_options` in order to configure the Scan engine.
```yml
  hub_options:
    Move Overhead: 100
    threads: 10
```
One last option is `go_commands`. Beneath this option, arguments to the hub `go` command can be passed. For example,
```yml
  go_commands:
    nodes: 1
    depth: 5
    movetime: 1000
```
will append `nodes 1 depth 5 movetime 1000` to the command to start thinking of a move: `go startpos e2e4 e7e5 ...`.

- `abort_time`: How many seconds to wait before aborting a game due to opponent inaction. This only applies during the first six moves of the game.
- `fake_think_time`: Artificially slow down the engine to simulate a person thinking about a move. The amount of thinking time decreases as the game goes on.
- `rate_limiting_delay`: For extremely fast games, the [lidraughts.org](https://lidraughts.org) servers may respond with an error if too many moves are played to quickly. This option avoids this problem by pausing for a specified number of milliseconds after submitting a move before making the next move.
- `move_overhead`: To prevent losing on time due to network lag, subtract this many milliseconds from the time to think on each move.

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

- `variants`: An indented list of chess variants that the bot can handle.
```yml
  variants:
    - standard
    - fromPosition
    - breakthrough
    - antidraughts
    - frisian
    - frysk
#   - brazilian
#   - russian
```

- `time_controls`: An indented list of acceptable time control types from `ultraBullet` to `correspondence`.
```yml
  time_controls:
    - ultraBullet
    - bullet
    - blitz
    - rapid
    - classical
    - correpondence
```
- `modes`: An indented list of acceptable game modes (`rated` and/or `casual`).
```yml
  modes:
    -rated
    -casual
```


## Tips & Tricks
- You can specify a different config file with the `--config` argument.
- Here's an example systemd service definition:
```
[Unit]
Description=lidraughts-bot
After=network-online.target
Wants=network-online.target

[Service]
Environment="PYTHONUNBUFFERED=1"
ExecStart=/usr/bin/python3 /home/AttackingOrDefending/lidraughts-bot/lidraughts-bot.py
WorkingDirectory=/home/AttackingOrDefending/lidraughts-bot/
User=AttackingOrDefending
Group=AttackingOrDefending
Restart=always

[Install]
WantedBy=multi-user.target
```

# Acknowledgements
Thanks to the Lichess Team for creating a [repository](https://github.com/ShailChoksi/lichess-bot) that could be easily modified to a format that supports Lidraughts. Thanks to [RoepStoep](https://github.com/RoepStoep) for running an [API](https://lidraughts.org/api) to communicate with the BOTs.

# License
lidraughts-bot is licensed under the AGPLv3 (or any later version at your option). Some files are licensed under a different license (the different license will be stated at the top of the file if that's the case). Check out LICENSE.txt for the full text.
