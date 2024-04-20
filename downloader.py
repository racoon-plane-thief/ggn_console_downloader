import os

from lib.ggn_client import GGNClient, GGNClientException
import argparse

print("Starting GGN Console Downloader")

parser = argparse.ArgumentParser("downloader")
parser.add_argument("--token",
                    help="GGN token to use for downloading torrents. Overrides the environment variable `GGN_TOKEN` "
                         "which may also be used to set the to",
                    default=None, required=False)
parser.add_argument("--dry",
                    help="When dry is true, torrents will not be downloaded. Instead, their links will be printed.",
                    default=True, required=False)
parser.add_argument("--write_location", help="Location to write the torrent files to.", default="./", required=False)
args = parser.parse_args()

token = args.token if args.token is not None else os.getenv("GGN_TOKEN")

print(f"building client.")

client = GGNClient(token)

torrent_data = {}

# add consoles you wish to obtain here
console_list = ['Atari 2600']

print(f"searching for torrents in {console_list}")

for console in console_list:
    print(f"Searching for torrents for {console} starting at page 1.")
    page_number = 1
    while True:
        result = client.search_torrents(
            artist_name=console,
            order_by="groupname",
            order_way="asc",
            page=page_number,
            empty_groups="filled",
        )
        # if no torrents are found on the page, we must be at the end
        if len(result) == 0:
            break
        for (_, torrent) in result.items():
            if "Torrents" not in torrent:
                continue

            # if there are no torrents in the group, skip it
            if len(torrent["Torrents"]) == 0:
                continue

            for (torrent_id, data) in torrent["Torrents"].items():
                # Filter out non-torrents
                if data["TorrentType"] != "Torrent":
                    continue
                # Filter out GameDOX torrents
                if data["GameDOXType"] != "":
                    continue
                # Skip already snatched torrents
                if data["IsSnatched"]:
                    print(f"group already snatched ({data['ReleaseTitle']}), skipping.")
                    if data["GroupID"] in torrent_data:
                        torrent_data.pop(data["GroupID"], None)
                    break

                # only add torrent if it has more seeds than the current torrent in the group
                if data["GroupID"] in torrent_data:
                    if torrent_data[data["GroupID"]]["seeders"] > data["Seeders"]:
                        continue

                torrent_data[data["GroupID"]] = {
                    "torrent_id": torrent_id,
                    "release_title": data["ReleaseTitle"],
                    "seeders": data["Seeders"],
                }

        page_number += 1
        print("Found {} torrents so far next page is {}.".format(len(torrent_data), page_number))

print(f"Found {len(torrent_data)} torrents.")
file_translator = str.maketrans({"[": "_", "\\": "_", "/": "-", "\"": "_", "*": "_", "?": "_",
                                 "<": "_", ">": "_", "|": "_", "]": "_", ":": "_"})

for (group_id, torrent) in torrent_data.items():
    try:
        filename = torrent['release_title'].translate(file_translator)
        client.download_torrent(torrent["torrent_id"], dry=args.dry,
                                write_location=f"{args.write_location}{filename}.torrent")
    except GGNClientException as e:
        print(f"Error downloading torrent {torrent['torrent_id']}: {e}")

print("Download complete.")
