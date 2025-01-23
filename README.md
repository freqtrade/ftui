# Welcome to FTUI

Freqtrade Textual User Interface (FTUI) is a text-based interface for the 
[Freqtrade](https://github.com/freqtrade/freqtrade) bot.

FTUI is developed using the awesome [Textual](https://textual.textualize.io/) and
[Rich](https://rich.readthedocs.io/en/stable/introduction.html) frameworks.

- Original concept and development: [@froggleston](https://github.com/froggleston)
- Github : [https://github.com/freqtrade/ftui](https://github.com/freqtrade/ftui)

### FTUI is in an alpha state so there will be bugs and missing features

![image](https://github.com/freqtrade/ftui/assets/1872302/60deca56-421b-436d-85e3-eea4befe4c37)

## Getting Started

FTUI is designed to mimic the [FreqUI](https://github.com/freqtrade/frequi) interface as
much as possible, but the main difference is that FTUI does not currenty support
controlling a running bot. Rather FTUI acts as a lightweight passive monitoring system
for running Freqtrade bots.

### Installation

Currently, FTUI is only supported on Linux systems. We hope to provide a Docker container
in future.

The easiest way to install FTUI is via pip: `pip install ftui`

__Linux__

FTUI can be installed into an existing venv (e.g. a existing freqtrade venv) or in a 
new directory, e.g. `~/ftui`, and venv as follows:

```bash
$ mkdir ~/ftui
$ cd ftui
$ python3 -m venv .venv
$ source .venv/bin/activate
$ pip3 install -r requirements.txt
$ pip3 install -e .
```

Once installed, a `config.yaml` needs to be provided to FTUI, so create it in your new
`ftui/` directory and edit it with a cli text editor like `nano`:

```bash
$ touch config.yaml
$ nano config.yaml
```

### Configuration

FTUI is configured using a `config.yaml` file, where a list of running Freqtrade bots needs
to be provided. An example has been provided to get you started as below:

```yaml
---
servers:
    - name        : "botA"
      username    : "you"
      password    : "your_password"
      ip          : 1.2.3.4
      port        : 8080
    - name        : "botB"
      username    : "you"
      password    : "your_password"
      ip          : 1.2.3.4
      port        : 8081

    - name        : "botC"
      username    : "you"
      password    : "your_password"
      ip          : 5.6.7.8
      port        : 8080

colours:
    pair_col: "purple"
    bot_col: "yellow"
    bot_start_col: "white"
    trade_id_col: "white"
    open_rate_col: "white"
    current_rate_col: "white"
    open_date_col: "cyan"
    winrate_col: "cyan"
    open_trade_num_col: "cyan"
    closed_trade_num_col: "purple"
    profit_chart_col: "orange"
    link_col: "yellow"
    candlestick_trade_text_col: "orange"
    candlestick_trade_open_col: "blue"
    candlestick_trade_close_col: "purple"

debug: False
show_fear: True
```

Add a corresponding `servers` block into your own `config.yaml`, making note of the
indentation.

You can monitor bots across multiple servers easily in one FTUI interface. FTUI uses
the [freqtrade-client](https://pypi.org/project/freqtrade-client/) REST API client, so
you do not need to wrestle with any CORS setup as you have to do in FreqUI to access
multiple bots.

You can also set custom colours for some of the UI elements as per the example above. 
The supported list of colour names can be found 
[here](https://textual.textualize.io/api/color/#textual.color--named-colors). You can
leave the `colours` option out of the configuration and defaults will be used.

In future, the Settings screen will allow configuration of the `config.yaml` from inside the
FTUI interface.

### Running FTUI

Once you have saved your `config.yaml` file, make sure you are in your ftui directory with your 
venv activated, and run FTUI as below. FTUI will load each bot client, and preload trade data
into memory:

```bash
$ ftui -y config.yaml

███████╗████████╗██╗   ██╗██╗
██╔════╝╚══██╔══╝██║   ██║██║
█████╗     ██║   ██║   ██║██║
██╔══╝     ██║   ██║   ██║██║
██║        ██║   ╚██████╔╝██║
╚═╝        ╚═╝    ╚═════╝ ╚═╝

Freqtrade Textual User Interface (FTUI)

Run with:

    ftui -y config.yaml

Setting up botA version 2024.1-dev-1b70e9b07 at http://1.2.3.4:8080: SampleStrategy running dry_run 5m
Setting up botB version 2024.1-dev-1b70e9b07 at http://1.2.3.4:8081: SampleStrategy running dry_run 5m
Setting up botC version 2024.1-dev-1b70e9b07 at http://5.6.7.8:8080: SampleStrategy running dry_run 5m

Starting FTUI - preloading all dataframes.......
```

### Screens

__Dashboard__

The main dashboard shows summary statistics from all bots. You can access the dashboard by
clicking the Dashboard button in the bottom left, or hitting the `D` key.

![image](https://github.com/freqtrade/ftui/assets/1872302/53d9e2ca-1afd-4d0d-ace6-a7a5419a0397)

__View Bots__

The bot view allows selection of a running bot from the dropdown at the top of the screen.
Once selected, various information about the bot will be shown in the tabs in the bottom half
of the screen. You can access the View Bots screen by clicking the button in the bottom left,
or hitting the `B` key.

Open trades:
![image](https://github.com/freqtrade/ftui/assets/1872302/ac12cf57-2235-4215-9463-8072ef9d9f02)

Closed trades:
![image](https://github.com/freqtrade/ftui/assets/1872302/abdd62ef-f9dc-4eb3-b33e-05e4611141c5)

Tag summary:
![image](https://github.com/freqtrade/ftui/assets/1872302/906f644b-f203-45a3-b821-c7b0d25a01e7)

Performance:
![image](https://github.com/freqtrade/ftui/assets/1872302/16cce9a9-61f0-4caa-98f2-823b57a82ef8)

General bot information:
![image](https://github.com/freqtrade/ftui/assets/1872302/6e597102-59f2-4456-b321-f5ce787ab89d)

Logs:
![image](https://github.com/freqtrade/ftui/assets/1872302/1dcc8b43-7bd4-43ae-907f-0dc749a717ea)

Sysinfo:
![image](https://github.com/freqtrade/ftui/assets/1872302/b1377e21-03f8-47a1-92eb-11b523753ad7)


__Settings__

The Settings screen shows the list of configured bots on the left hand side of the screen.
Other configuration options are shown on the right. You can access the Settings
screen by clicking the button in the bottom left, or hitting the `S` key.

In future, you will be able to show and hide bots in FTUI by selecting/deselecting them 
in the bot list, as well as changing other configuration options. Currently this feature
is disabled in this alpha release.

__Help__

This README! 

## Known Issues

### General

- When the bot is been running and you put your PC to sleep, the async worker will bug out
  and intermittently crash the UI.
- The Settings screen save functionality is currently disabled.

### urllib pool connection errors

When running a larger number of bots within one FTUI instance, you may see urllib/requests 
warnings about the pool connections being exhausted:

`connection pool is full, discarding connection: 127.0.0.1.  Connection pools size: 10`

Raising the pool size limits can help avoid these warnings.

There are two command line/yaml config options that can be adjusted:

#### CLI

`ftui -c config.json --pool_connections 20 --pool_maxsize 15`

#### YAML config

```yaml
pool_connections: 20
pool_maxsize: 15
```
