# Welcome to FTUI

Freqtrade Textual User Interface (FTUI) is a text-based interface for the 
[Freqtrade](https://github.com/freqtrade/freqtrade) bot.

- Version: 0.1.0
- Original concept and development: [@froggleston](https://github.com/froggleston)
- Github : [https://github.com/freqtrade/freqtrade-ftui](https://github.com/freqtrade/freqtrade-ftui)

## Getting Started

Stuff

## Known Issues

### General

- When the bot is been running and you put your PC to sleep, the async worker will bug out
  and intermittently crash the UI.

### Charting

- Sometimes charts will experience a `IndexError: list index out of range` - the source of
  this bug hasn't been found yet.