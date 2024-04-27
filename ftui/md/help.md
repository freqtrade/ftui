# Welcome to FTUI

Freqtrade Textual User Interface (FTUI) is a text-based interface for the 
[Freqtrade](https://github.com/freqtrade/freqtrade) bot.

FTUI is developed using the awesome [Textual](https://textual.textualize.io/) and
[Rich](https://rich.readthedocs.io/en/stable/introduction.html) frameworks.

- Version: 0.1.0
- Original concept and development: [@froggleston](https://github.com/froggleston)
- Github : [https://github.com/freqtrade/ftui](https://github.com/freqtrade/ftui)

## Getting Started

FTUI is designed to mimic the [FreqUI](https://github.com/freqtrade/frequi) interface as
much as possible, but the main difference is that FTUI does not currenty support
controlling a running bot. Rather FTUI acts as a lightweight passive monitoring system
for running Freqtrade bots.

### Installation

Currently, FTUI is only supported on Linux systems. We hope to provide a Docker container
in future.

__Linux__

FTUI can be installed into an existing venv (e.g. a existing freqtrade venv) or in a 
new directory, e.g. `~/ftui`, and venv as follows:

```bash
$ mkdir ~/ftui
$ cd ftui
$ python3 -m venv .venv
$ source .venv/bin/activate
$ pip3 install -r requirements.txt
$ pip3 install freqtrade-ftui
```

Once installed, a `config.yaml` needs to be provided to FTUI, so create it in your new
`ftui/` directory and edit it with a cli text editor like `nano`:

```bash
$ pwd
/home/froggleston/ftui
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

debug: False
```

Add a corresponding `servers` block into your own `config.yaml`, making note of the
indentation.

You can monitor bots across multiple servers easily in one FTUI interface. FTUI uses
the [freqtrade-client](https://pypi.org/project/freqtrade-client/) REST API client, so
you do not need to wrestle with any CORS setup as you have to do in FreqUI to access
multiple bots.

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

__View Bots__

The bot view allows selection of a running bot from the dropdown at the top of the screen.
Once selected, various information about the bot will be shown in the tabs in the bottom half
of the screen. You can access the View Bots screen by clicking the button in the bottom left,
or hitting the `B` key.

__Settings__

The Settings screen shows the list of configured bots on the left hand side of the screen.
Other configuration options are shown on the right. You can access the Settings
screen by clicking the button in the bottom left, or hitting the `S` key.

In future, you will be able to show and hide bots in FTUI by selecting/deselecting them 
in the bot list, as well as changing other configuration options. Currently this feature
is disabled in this alpha release.

__Help__

This help! 

## Known Issues

### General

- When the bot is been running and you put your PC to sleep, the async worker will bug out
  and intermittently crash the UI.
- The Settings screen save functionality is currently disabled.
