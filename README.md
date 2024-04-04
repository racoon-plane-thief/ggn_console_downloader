GGN Console Downloader

This is a simple script which downloads all torrents from a list of console groups which meet the following criteria:

* Is not GameDOX
* Is the best seed from the torrent group
* Has not been snatched already
---

## SETUP INSTRUCTIONS

From this directory within your console, run 

```bash
pip install -r requirements.txt
```

## USAGE

```bash
python downloader.py <options>

Options:
    --token <token>               GGN token to use for downloading torrents. Overrides the environment variable `GGN_TOKEN` which may also be used to set the to
    --write_location <location>   The output directory to save the files. (default: ./)
    --dry <true|false>            When dry is true, torrents will not be downloaded. Instead, their links will be printed. (default: true)
```