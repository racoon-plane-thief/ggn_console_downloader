from datetime import timedelta
from ratelimit import limits, sleep_and_retry
import requests
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class Headers:
    token: str
    extra_headers: Dict[str, str] = field(default_factory=dict)

    def to_dict(self):
        default_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-API-Key": self.token,
        }
        return {**default_headers, **self.extra_headers}

    def add_header(self, key: str, value: str) -> None:
        """Adds a header to the extra headers."""
        self.extra_headers[key] = value

    def remove_header(self, key: str) -> None:
        """Removes a header from the extra headers."""
        self.extra_headers.pop(key, None)


class GGNClientException(Exception):
    pass


class GGNClient:

    def __init__(
            self,
            token=None,
            base_url: str = "https://gazellegames.net/api.php",
    ) -> None:
        self._token = token
        self._base_url = base_url
        self._user = None # user info cache, needed for downloading torrents.

    def __base_url(self):
        return f"{self._base_url}?"

    def _action_url(self, action: str = None, args: Dict[str, str] = None, override_url: str = None, ) -> str:
        base = self.__base_url() if not override_url else override_url

        if not action:
            return base

        extra_args = "&{}".format(
            '&'.join([f"{key}={value}" for key, value in args.items() if value is not None]),
        ) if args is not None and len(args) > 0 else ""
        return f"{base}&request={action}&{extra_args}"

    @sleep_and_retry
    @limits(calls=5, period=timedelta(seconds=10).total_seconds())
    def _do_request(self, action: str, args: Dict[str, str] = None, override_url: str = None, dry: bool = False):
        endpoint = self._action_url(
            action=action,
            args=args,
            override_url=override_url,
        )

        if dry:
            return endpoint

        response = requests.get(
            url=endpoint,
            headers=Headers(token=self._token).to_dict(),
            timeout=10,
        )

        if not response.ok:
            raise GGNClientException(
                f"Failed to call {action}: {response.status_code} - {response.text}"
            )
        if response.headers.get("Content-Type") != "application/json":
            return response

        json = response.json()
        if json["status"] != "success":
            raise GGNClientException(
                f"Failed to call {action}: {json}"
            )
        return json["response"]

    def index(self):
        """returns the ggn api version

           Required Permissions: None
        """
        response = self._do_request()

        return response

    def quick_user(self):
        """returns the user's quick info, including identifiers, notifications, and userstats

           Required Permissions: User
        """
        response = self._do_request(action="quick_user")

        return response

    def user_ratio_stats(self):
        """returns the user's ratio stats

           Required Permissions: User
        """
        response = self._do_request(action="user_ratio_stats")

        return response

    def user_profile(self, user_id: int = None, name: str = None):
        """returns a user's profile
          `user_id` - the id of the user to display
          `name` - the name of the user to display

          Required Permissions: None* (see note below)

          Note that the user data will be limited by paranoia so not all data will always be filled
          Please refrain from pulling from this api too often. All of the data is live and it causes a lot of stress to
          the database to pull this constantly.
        """
        if not user_id and not name:
            raise GGNClientException("id or name must be provided")
        if user_id and name:
            raise GGNClientException("only one of id or name can be provided")

        response = self._do_request(action="user", args={
            "id": user_id if user_id else None,
            "username": name if name else None,
        })

        return response

    def userlog(self, search=None, page: int = 1, limit: int = 50):
        """returns the user log
          `page` - the page number to display (default 1)
          `limit` - the amount of results to show per page (default 50)
          `search` - search for logs containing a string (case-insensitive)

           Required Permissions: User
        """
        response = self._do_request(action="userlog", args={
            "search": search,
            "page": page,
            "limit": limit,
        })

        return response

    def user_community_stats(self, user_id: int):
        """returns the user's community stats
          `user_id` - the id of the user to display

           Required Permissions: None(?)
        """
        response = self._do_request(action="user_community_stats", args={
            "userid": user_id,
        })

        return response

    def inbox(
            self,
            sort: str = None,
            search: str = None,
            search_type: str = None,
            message_type: str = "inbox",
            page: int = 1
    ):
        """returns a page from the user's inbox or sentbox
          `message_type` - the type of messages to display (`inbox` or `sentbox`)
          `page` - the page number to display (default 1)
          `sort` - if set to `unread` then unread messages will be displayed first
          `search` - search for messages containing a string (case-insensitive)
          `searchtype` - the field which search applies to (`subject`, `message`, or `user)

           Required Permissions: User
        """
        if message_type not in ["inbox", "sentbox", None]:
            raise GGNClientException("type must be 'inbox' or 'sentbox', or None")
        if sort not in ["unread", None]:
            raise GGNClientException("sort must be 'unread' or None")
        if search_type not in ["subject", "message", "user", None]:
            raise GGNClientException("searchtype must be 'subject', 'message', or 'user', or None")

        response = self._do_request(action="inbox", args={
            "type": message_type,
            "page": page,
            "sort": sort,
            "search": search,
            "searchtype": search_type,
        })

        return response

    def conversations(self, conv_id: int = None):
        """returns a conversation from within the user's inbox
          `conv_id` - the id of the conversation to display

           Required Permissions: User
        """
        response = self._do_request(action="inbox", args={
            "type": "viewconv",
            "id": conv_id
        })

        return response

    def send_pm(self, to: str = None, subject: str = None, body: str = None, conv_id: str = None):
        """sends a private message
          `to` - the user id of who you want to PM
          `subject` - the subject of the new PM
          `body` - the body of the message
          `conv_id` - the ID of an existing conversation

           Required Permissions: User
        """
        response = self._do_request(action="inbox", args={
            "type": "send",
            "to": to,
            "subject": subject,
            "body": body,
            "convid": conv_id,
        })

        return response

    def mark_read(self, messages: [int]):
        """marks messages as read
          `messages` - a list of conversation ids to mark as read

           Required Permissions: User
        """
        response = self._do_request(action="inbox", args={
            "type": "markread",
            "messages": messages,
        })

        return response

    def search_torrents(
            self,
            search_str: str = None,
            group_name: str = None,
            artist_name: str = None,
            artist_check: str = None,
            year: int = None,
            remaster_title: str = None,
            remaster_year: int = None,
            release_title: str = None,
            release_group: str = None,
            file_list: str = None,
            size_small: int = None,
            size_large: int = None,
            user_rating: int = None,
            meta_rating: int = None,
            ign_rating: int = None,
            gs_rating: int = None,
            encoding: str = None,
            audio_format: str = None,  # format
            region: str = None,
            language: str = None,
            rating: str = None,
            rating_strict: bool = None,
            miscellaneous: str = None,
            game_dox: str = None,
            scene: bool = None,
            dupable: int = None,
            free_torrent: int = None,
            checked: bool = None,
            tag_list: [str] = None,
            tags_type: bool = None,
            hide_dead: bool = None,
            empty_groups: str = None,
            filter_cat_1: bool = None,
            filter_cat_2: bool = None,
            filter_cat_3: bool = None,
            filter_cat_4: bool = None,
            order_by: str = None,
            order_way: str = None,
            page: int = 1,
    ):
        """searches for torrents

            All arguments are optional.
            `search_str` - Word(s) to search torrents for
            `group_name` - Title of the game/application/etc.
            `artist_name` - Single platform to restrict to. Empty for no restriction. `My Platforms` is a valid value. Cannot be used wityh `artistcheck`.
            `artist_check` - Single platform to restrict to. Empty for no restriction. `My Platforms` is a valid value. Cannot be used with `artistname`.
            `year` - Group's year or range, eg. 2000 or 1999- or -2008 or 1990-1995
            `remaster_title` - Special edition title, eg. "GOG Edition"
            `remaster_year` -  Special edition year or year range, same format as year
            `release_title` - Release title
            `release_group` - Release group name
            `file_list` - Search the torrent's file names
            `size_small` - Minimum size in MBs
            `size_large` - Maximum size in MBs
            `user_rating` - Number of positive user ratings (thumbs up - thumbs down) or higher
            `meta_rating` - Metacritic rating 0-100 or higher
            `ign_rating` - IGN rating 0-10 or higher
            `gs_rating` - Gamespot rating 0-10 or higher
            `encoding` - OST SPECIFIC: Audio bitrate. The possible values are `192`, `V2 (VBR)`, `V1 (VBR)`, `256`, `V0 (VBR)`, `320`, `Lossless`, `24bit Lossless`
            `audio_format` - OST SPECIFIC: Audio format. The possible values are `MP3`, `FLAC`, `Other`
            `region` - GAME SPECIFIC: Game Region. The possible values are `USA`, `Europe`, `Japan`, `Asia`, `Australia`, `France`, `Germany`, `Spain`, `Italy`, `UK`, `Netherlands`, `Sweden`, `Russia`, `China`, `Korea`, `Hong Kong`, `Taiwan`, `Brazil`, `Canada`, `Japan`, `USA`, `Japan`, `Europe`, `USA`, `Europe`, `Europe`, `Australia`, `Japan`, `Asia`, `UK`, `Australia`, `World`, `Region-Free`, `Other`
            `language` - GAME SPECIFIC: Game Language. `Multi-Language`, `English`, `German`, `French`, `Czech`, `Chinese`, `Italian`, `Japanese`, `Korean`, `Polish`, `Portuguese`, `Russian`, `Spanish`, `Other`
            `rating` - GAME SPECIFIC: Game Rating text.  The possible values are: `3+`, `7+`, `12+`, `16+`, `18+`, `N/A`
            `rating_strict` - GAME SPECIFIC: 1 to search only the selected rating, rather than the rating or higher
            `miscellaneous` - Release type. The possible values are: `Full ISO`, `GameDOX`, `GGn Internal`,`P2P`, `Rip`, `Scrubbed`, `Home Rip`, `DRM Free`, `ROM`, `E-Book`, `Other`
            `game_dox` - GameDOX type. If miscellaneous is not set or is set to GameDOX. The possible values are: `Fix/Keygen`, `Update`, `DLC`, `GOG-Goodies`, `Trainer`, `Tool`, `Guide`, `Artwork`, `Audio`
            `game_dox_version` - GameDOX version number, format x.x.x.x, if gamedox is set to Update or unset
            `scene` - Restrict search to scene or non-scene. The posible values are: 1 - scene releases, 0 - non-scene releases
            `dupable` - Trump status. The possible values are: 0 - Not Trumpable, 999 - All Trumpable, 1 - Bad directory / file names, 2 - Altered scene release, 3 - Wrong archive format, 4 - No version info, 5 - Approved lossy master, 6 - Bundle to split, 7 - To be bundled
            `freetorrent` - Leech type. The possible values are: 1 - Freeleech, 2 - Neutral Leech, 3 - Either, 0 - Normal
            `checked` - Torrent verified: 1 - Yes, 0 - No
            `taglist` - List of tags, comma separated
            `tags_type` - How to search specified tags: 0 - Torrents must have any of taglist, 1 - Torrents must have all of taglist
            `hide_dead` - 1 to hide groups with no seeds
            `empty_groups` - Empty groups filter. The possible values are: `both` - Both Filled & Empty, `filled` - Filled-Only, `empty` - Empty-Only
            `filter_cat[1]` - 1 to include Games (default when none are specified includes all categories)
            `filter_cat[2]` - 1 to include Applications
            `filter_cat[3]` - 1 to include E-Books
            `filter_cat[4]` - 1 to include OST
            `order_by` - What method to use to order the results. The possible values are: `relevance` - Relevance, `time` - Time added, `userrating` - User Rating, `groupname` - Title, `year` - Year, `size` - Size, `snatched` - Snatched, `seeders` - Seeders, `leechers` - Leechers, `metarating` - MetaCritic Score, `ignrating` - IGN Score, `gsrating` - GameSpot Score (default relevance)
            `order_way` - Sort order direction: asc or desc. (default desc)

        Required Permissions: None"""

        response = self._do_request(action="search", args={
            "search_type": "torrents",
            "searchstr": search_str,
            "groupname": group_name,
            "artistname": artist_name,
            "artistcheck": artist_check,
            "year": year,
            "remastertitle": remaster_title,
            "releasegroup": release_group,
            "remasteryear": remaster_year,
            "releasetitle": release_title,
            "filelist": file_list,
            "sizesmall": size_small,
            "sizelarge": size_large,
            "userrating": user_rating,
            "metarating": meta_rating,
            "ignrating": ign_rating,
            "gsrating": gs_rating,
            "encoding": encoding,
            "audioformat": audio_format,
            "region": region,
            "language": language,
            "rating": rating,
            "rating_strict": rating_strict,
            "miscellaneous": miscellaneous,
            "gamedox": game_dox,
            "scene": scene,
            "dupable": dupable,
            "freetorrent": free_torrent,
            "checked": int(checked is True) if checked is not None else None,
            "taglist": tag_list,
            "tags_type": int(tags_type is True) if tags_type is not None else None,
            "hide_dead": int(hide_dead is True) if hide_dead is not None else None,
            "emptygroups": empty_groups,
            "filtercat[1]": int(filter_cat_1 is True) if filter_cat_1 is not None else None,
            "filtercat[2]": int(filter_cat_2 is True) if filter_cat_2 is not None else None,
            "filtercat[3]": int(filter_cat_3 is True) if filter_cat_3 is not None else None,
            "filtercat[4]": int(filter_cat_4 is True) if filter_cat_4 is not None else None,
            "order_by": order_by,
            "order_way": order_way,
            "page": page,
        })
        return response

    def search_requests(
            self,
            search_str: str = None,
            group_name: str = None,
            artist_name: str = None,
            artist_check: str = None,
            year: int = None,
            remaster_title: str = None,
            remaster_year: int = None,
            release_title: str = None,
            release_group: str = None,
            file_list: str = None,
            size_small: int = None,
            size_large: int = None,
            user_rating: int = None,
            meta_rating: int = None,
            ign_rating: int = None,
            gs_rating: int = None,
            encoding: str = None,
            audio_format: str = None,  # format
            region: str = None,
            language: str = None,
            rating: str = None,
            rating_strict: bool = None,
            miscellaneous: str = None,
            game_dox: str = None,
            scene: bool = None,
            dupable: int = None,
            free_torrent: int = None,
            checked: bool = None,
            tag_list: [str] = None,
            tags_type: bool = None,
            hide_dead: bool = None,
            empty_groups: str = None,
            filter_cat_1: bool = None,
            filter_cat_2: bool = None,
            filter_cat_3: bool = None,
            filter_cat_4: bool = None,
            order_by: str = None,
            order_way: str = None,
            page: int = 1,
    ):
        """searches for requests

           All arguments are optional.
            `search_str` - Word(s) to search requests for
            `group_name` - Title of the game/application/etc.
            `artist_name` - Single platform to restrict to. Empty for no restriction. `My Platforms` is a valid value. Cannot be used with `artistcheck`.
            `artist_check` - Single platform to restrict to. Empty for no restriction. `My Platforms` is a valid value. Cannot be used with `artistname`.
            `year` - Group's year or range, eg. 2000 or 1999- or -2008 or 1990-1995
            `remaster_title` - Special edition title, eg. "GOG Edition"
            `remaster_year` -  Special edition year or year range, same format as year
            `release_title` - Release title
            `release_group` - Release group name
            `file_list` - Search the request's file names
            `size_small` - Minimum size in MBs
            `size_large` - Maximum size in MBs
            `user_rating` - Number of positive user ratings (thumbs up - thumbs down) or higher
            `meta_rating` - Metacritic rating 0-100 or higher
            `ign_rating` - IGN rating 0-10 or higher
            `gs_rating` - Gamespot rating 0-10 or higher
            `encoding` - OST SPECIFIC: Audio bitrate. The possible values are `192`, `V2 (VBR)`, `V1 (VBR)`, `256`, `V0 (VBR)`, `320`, `Lossless`, `24bit Lossless`
            `audio_format` - OST SPECIFIC: Audio format. The possible values are `MP3`, `FLAC`, `Other`
            `region` - GAME SPECIFIC: Game Region. The possible values are `USA`, `Europe`, `Japan`, `Asia`, `Australia`, `France`, `Germany`, `Spain`, `Italy`, `UK`, `Netherlands`, `Sweden`, `Russia`, `China`, `Korea`, `Hong Kong`, `Taiwan`, `Brazil`, `Canada`, `Japan`, `USA`, `Japan`, `Europe`, `USA`, `Europe`, `Europe`, `Australia`, `Japan`, `Asia`, `UK`, `Australia`, `World`, `Region-Free`, `Other`
            `language` - GAME SPECIFIC: Game Language. `Multi-Language`, `English`, `German`, `French`, `Czech`, `Chinese`, `Italian`, `Japanese`, `Korean`, `Polish`, `Portuguese`, `Russian`, `Spanish`, `Other`
            `rating` - GAME SPECIFIC: Game Rating text.  The possible values are: `3+`, `7+`, `12+`, `16+`, `18+`, `N/A`
            `rating_strict` - GAME SPECIFIC: 1 to search only the selected rating, rather than the rating or higher
            `miscellaneous` - Release type. The possible values are: `Full ISO`, `GameDOX`, `GGn Internal`,`P2P`, `Rip`, `Scrubbed`, `Home Rip`, `DRM Free`, `ROM`, `E-Book`, `Other`
            `game_dox` - GameDOX type. If miscellaneous is not set or is set to GameDOX. The possible values are: `Fix/Keygen`, `Update`, `DLC`, `GOG-Goodies`, `Trainer`, `Tool`, `Guide`, `Artwork`, `Audio`
            `game_dox_version` - GameDOX version number, format x.x.x.x, if gamedox is set to Update or unset
            `scene` - Restrict search to scene or non-scene. The posible values are: 1 - scene releases, 0 - non-scene releases
            `dupable` - Trump status. The possible values are: 0 - Not Trumpable, 999 - All Trumpable, 1 - Bad directory / file names, 2 - Altered scene release, 3 - Wrong archive format, 4 - No version info, 5 - Approved lossy master, 6 - Bundle to split, 7 - To be bundled
            `freetorrent` - Leech type. The possible values are: 1 - Freeleech, 2 - Neutral Leech, 3 - Either, 0 - Normal
            `checked` - Torrent verified: 1 - Yes, 0 - No
            `taglist` - List of tags, comma separated
            `tags_type` - How to search specified tags: 0 - Torrents must have any of taglist, 1 - Torrents must have all of taglist
            `hide_dead` - 1 to hide groups with no seeds
            `empty_groups` - Empty groups filter. The possible values are: both - Both Filled & Empty, filled - Filled-Only, empty - Empty-Only
            `filter_cat[1]` - 1 to include Games (default when none are specified includes all categories)
            `filter_cat[2]` - 1 to include Applications
            `filter_cat[3]` - 1 to include E-Books
            `filter_cat[4]` - 1 to include OST
            `order_by` - What method to use to order the results. The possible values are: `relevance` - Relevance, `time` - Time added, `userrating` - User Rating, `groupname` - Title, `year` - Year, `size` - Size, `snatched` - Snatched, `seeders` - Seeders, `leechers` - Leechers, `metarating` - MetaCritic Score, `ignrating` - IGN Score, `gsrating` - GameSpot Score (default relevance)
            `order_way` - Sort order direction: asc or desc. (default desc)

        Required Permissions: None
        """
        response = self._do_request(action="search", args={
            "search_type": "requests",
            "searchstr": search_str,
            "groupname": group_name,
            "artistname": artist_name,
            "artistcheck": artist_check,
            "year": year,
            "remastertitle": remaster_title,
            "releasegroup": release_group,
            "remasteryear": remaster_year,
            "releasetitle": release_title,
            "filelist": file_list,
            "sizesmall": size_small,
            "sizelarge": size_large,
            "userrating": user_rating,
            "metarating": meta_rating,
            "ignrating": ign_rating,
            "gsrating": gs_rating,
            "encoding": encoding,
            "audioformat": audio_format,
            "region": region,
            "language": language,
            "rating": rating,
            "rating_strict": rating_strict,
            "miscellaneous": miscellaneous,
            "gamedox": game_dox,
            "scene": scene,
            "dupable": dupable,
            "freetorrent": free_torrent,
            "checked": int(checked is True) if checked is not None else None,
            "taglist": tag_list,
            "tags_type": int(tags_type is True) if tags_type is not None else None,
            "hide_dead": int(hide_dead is True) if hide_dead is not None else None,
            "emptygroups": empty_groups,
            "filtercat[1]": int(filter_cat_1 is True) if filter_cat_1 is not None else None,
            "filtercat[2]": int(filter_cat_2 is True) if filter_cat_2 is not None else None,
            "filtercat[3]": int(filter_cat_3 is True) if filter_cat_3 is not None else None,
            "filtercat[4]": int(filter_cat_4 is True) if filter_cat_4 is not None else None,
            "order_by": order_by,
            "order_way": order_way,
            "page": page,
        })
        return response

    def search_collections(
            self,
            search: str = None,
            search_type: str = None,
            order: str = None,
            way: str = None,
            cats_1: bool = None,
            cats_2: bool = None,
            cats_3: bool = None,
            cats_4: bool = None,
            cats_5: bool = None,
            cats_6: bool = None,
            cats_7: bool = None,
            cats_8: bool = None,
            cats_9: bool = None,
            cats_10: bool = None,
            cats_11: bool = None,
            cats_12: bool = None,
            cats_15: bool = None,
    ):
        """search for collections
            All arguments are optional.
            `search` - Word(s) to search collections for
            `type` - What part of the collection to search in: `c.name` - Names, `description` - Descriptions, `tags.Tag` - Tags.
            `order` - How to order the results: `Time` - Collection creation time, `Name` - Name of collection, `Torrents` - Count of torrents in collection, `Updated` - Last update time
            `way` - Sort direction: `Ascending` or `Descending`
            `cats[1]` - 1 to include Theme collections. Exclude all cats arguments to include all types.
            `cats[2]` - 1 to include Series collections.
            `cats[3]` - 1 to include Developer collections.
            `cats[4]` - 1 to include Publisher collections.
            `cats[5]` - 1 to include Designer collections.
            `cats[6]` - 1 to include Composer collections.
            `cats[7]` - 1 to include Engine collections.
            `cats[8]` - 1 to include Feature collections.
            `cats[9]` - 1 to include Franchise collections.
            `cats[10]` - 1 to include Pack collections.
            `cats[11]` - 1 to include Best Of collections.
            `cats[12]` - 1 to include Author collections.
            `cats[15]` - 1 to include Arranger collections.

           Required Permissions: None
        """
        response = self._do_request(action="search", args={
            "search": search,
            "search_type": search_type,
            "order": order,
            "way": way,
            "cats[1]": int(cats_1 is True) if cats_1 is not None else None,
            "cats[2]": int(cats_2 is True) if cats_2 is not None else None,
            "cats[3]": int(cats_3 is True) if cats_3 is not None else None,
            "cats[4]": int(cats_4 is True) if cats_4 is not None else None,
            "cats[5]": int(cats_5 is True) if cats_5 is not None else None,
            "cats[6]": int(cats_6 is True) if cats_6 is not None else None,
            "cats[7]": int(cats_7 is True) if cats_7 is not None else None,
            "cats[8]": int(cats_8 is True) if cats_8 is not None else None,
            "cats[9]": int(cats_9 is True) if cats_9 is not None else None,
            "cats[10]": int(cats_10 is True) if cats_10 is not None else None,
            "cats[11]": int(cats_11 is True) if cats_11 is not None else None,
            "cats[12]": int(cats_12 is True) if cats_12 is not None else None,
            "cats[15]": int(cats_15 is True) if cats_15 is not None else None,
        })
        return response

    def get_master_group(self, id: int, group_id: int):
        """Gets a master group by id
            `id` - the id of the master group
            `group_id` - a group in a master group

           Required Permissions: None
        """
        response = self._do_request(action="master_group", args={
            "id": id,
            "groupid": group_id,
        })
        return response

    def get_torrent_group(self, group_id: int, torrent_hash: str, name: str):
        """Get a torrent group
            `group_id` - the id of the torrent group
            `torrent_hash` - the hash of a torrent in the torrent group
            `name` - the exact torrent group's name

           Required Permissions: None
        """
        response = self._do_request(action="torrent_group", args={
            "id": group_id,
            "hash": torrent_hash.upper() if torrent_hash else None,
            "name": name,
        })
        return response

    def get_torrent(self, torrent_id: int, torrent_hash: str = None):
        """gets a torrent's info
            `torrent_id` - the id of the torrent
            `info_hash` - the hash of the torrent

           Required Permissions: None
        """
        response = self._do_request(action="torrent", args={
            "id": torrent_id,
            "hash": torrent_hash.upper() if torrent_hash else None,
        })

        return response

    def get_deleted_torrent_notifications(
            self,
            limit: int,
            page: int = 1,
            clear: str = None,
            mark_unread: bool = False
    ):
        """gets a list of deleted torrent notifications
            `limit` - the maximum number of notifications to list
            `page` - the page number to display (default 1)
            `clear` - either `all` or a comma-separated list of torrent IDs to clear notifications for
            `mark_unread` - mark all notifications as unread

           Required Permissions: Torrents
        """
        response = self._do_request(action="delete_notifs", args={
            "limit": limit,
            "page": page,
            "clear": clear,
            "mark_unread": int(mark_unread is True),
        })

        return response

    def get_collection(self, collection_id: int):
        """gets a collection by id
            `collection_id` - the id of the collection

            Required Permissions: None
        """
        response = self._do_request(action="collection", args={"id": "{}".format(collection_id)})
        return response

    def get_wiki_article(self, article_id: int):
        """gets a wiki article by id
            `article_id` - the id of the article

            Required Permissions: Wiki
        """
        response = self._do_request(action="wiki", args={"id": "{}".format(article_id)})
        return response

    def get_site_log(self, page: int = 1, limit: int = 25, search: str = None):
        """gets the site log
            `page` - the page number to display (default 1)
            `limit` - the amount of results to show per page (default 25)
            `search` - search for logs containing a string (case-insensitive)

            Required Permissions: Site Info
        """
        response = self._do_request(action="sitelog", args={
            "page": page,
            "limit": limit,
            "search": search,
        })
        return response

    def get_item_info(self, item_id: int = None, item_ids: [int] = None):
        """gets an item's info
            `item_id` - the id of the item (cannot be used with `item_ids`)
            `item_ids` - a list of item ids (cannot be used with `item_id`)

            Required Permissions: Store
        """

        response = self._do_request(action="store", args={
            "itemid": item_id,
            "itemids": '[{}]'.format(','.join(map(str, item_ids))) if item_ids else None,
        })
        return response

    def search_items(
            self,
            search: str = None,
            search_more: bool = None,
            category: str = None,
            item_type: int = None,
            cost_type: int = None,
            cost_amount: int = None,
            in_stock: bool = None,
            no_featured: bool = None,
            order_by: str = None,
            order_way: str = None,
            page: int = 1,
            limit: int = 30,
    ):
        """searches for items
            All arguments are optional.
            `search` - a query to search (case-insensitive). By default searches just the items name.
            `search_more` - when true, makes the search additionally query item descriptions and book excerpts.
            `category` - used to filter by a category. This should be the name of a category (e.g. "New Site Features"). Alternatively this can be set to 'Featured Only' or 'All'.
            `item_type` - used to filter by item type. This should be a number. The possible types are: `100` - Standard, `2` - Equippable, `3` - Book, `4` - Card, `5` - Pack, `6` - Adventure Club Item.
            `cost_type` - used to filter by cost type. This should be a number. The possible types are: `100` - Gold, `2` - Upload, `3` - Download, `4` - Donor Points.
            `cost_amount` - set the max cost of items you want returned.
            `in_stock` - when true, only returns items that are in stock.
            `no_featured` - by default the search returns featured results first. When this is set to true it won't prioritize featured items.
            `order_by` - options include: `category`, `dateadded`, `name`, `cost`, and `itemtype`.
            `order_way` - `asc` or `desc`.
            `page` - page number to display (default: 1)
            `limit` - the amount of results to show per page (default: 30)

            Requires Permissions: None?
        """
        response = self._do_request(action="store", args={
            "type": "search",
            "search": search,
            "search_more": int(search_more is True) if search_more is not None else None,
            "category": category,
            "item_type": item_type,
            "cost_type": cost_type,
            "cost_amount": cost_amount,
            "in_stock": int(in_stock is True) if in_stock is not None else None,
            "no_featured": int(no_featured is True) if no_featured is not None else None,
            "order_by": order_by,
            "order_way": order_way,
            "page": page,
            "limit": limit,
        })
        return response

    def get_user_items(self, user_id: int = None, include_info: bool = False):
        """gets a user's items
            `user_id` - id of the user to display. default: self
            `include_info` - if false or not set, this endpoint only returns item ids. If true, it will return item info for each item under the 'item' key.

            Required Permissions: Items
        """
        response = self._do_request(action="items", args={
            "type": "inventory",
            "userid": user_id,
            "include_info": include_info,
        })
        return response

    def get_user_equipment(self, user_id: int = None, include_info: bool = False):
        """gets a user's equipment
            `user_id` - id of the user to display. default: self
            `include_info` - if false or not set, this endpoint only returns item ids. If true, it will return item info for each item under the 'item' key.

            Required Permissions: Items
        """
        response = self._do_request(action="items", args={
            "type": "users_equippable",
            "userid": user_id,
            "include_info": include_info,
        })
        return response

    def get_users_equipped(self, include_info: bool = False):
        """gets your own equipped items
            `include_info` - if false or not set, this endpoint only returns item ids. If true, it will return item info for each item under the 'item' key.

            Required Permissions: Items
        """
        response = self._do_request(action="items", args={
            "type": "users_equipped",
            "include_info": include_info,
        })
        return response

    def get_user_buffs(self):
        """gets your own buffs
            Required Permissions: Items
        """
        response = self._do_request(action="items", args={"type": "users_buffs"})
        return response

    def get_user_crafted_recipes(self):
        """gets your own crafted recipes
            Required Permissions: Items
        """
        response = self._do_request(action="items", args={"type": "crafted_recipes"})
        return response

    def get_crafting_recipe(self, recipe_id: int = None, recipe_ids: [int] = None):
        """gets a crafting recipe by id
            `recipe_id` - the recipe id to query (get this from the Users Crafted Recipes endpoint) (cannot be used with `recipe_ids`)
            `recipe_ids` - a list of recipe ids to query (get this from the Users Crafted Recipes endpoint) (cannot be used with `recipe_id`)

            Required Permissions: Items
        """
        response = self._do_request(action="items", args={
            "type": "get_crafting_recipe",
            "recipeid": recipe_id,
            "recipeids": recipe_ids,
        })
        return response

    def get_crafting_result(self, action: str = "find", recipe_id: int = None, recipe: str = None):
        """gets the result of a crafting recipe
            `action` - `find` (default) or `take`. find will return the result if one exists, take will take the resulting crafting item if possible.
            `recipe_id` - the recipe id to use (get this from the Users Crafted Recipes endpoint) (will only work if you have crafted the recipe at least once before) (cannot be used with `recipe`)
            `recipe` - a recipe string (get this from the Get Crafting Recipe endpoint) (will work whether you have crafted the recipe before or not) (cannot be used with `recipe_id`)

            Required Permissions: Items
        """
        response = self._do_request(action="items", args={
            "type": "crafting_result",
            "action": action,
            "recipeid": recipe_id,
            "recipe": recipe,
        })
        return response

    def purchase_item(self, item_id: int, amount: int):
        """purchases an item
            `item_id` - The item to purchase. You can obtain an itemid using the Item Search endpoint or from the site.

            Required Permissions: Items
        """
        response = self._do_request(action="items", args={
            "type": "purchase",
            "itemid": item_id,
            "amount": amount,
        })
        return response

    def use_item(self, item_id: int, amount: int):
        """uses an item
            `item_id` - The item to use. You can obtain an itemid using the Item Search endpoint or from the site.
            `amount` - The amount of the item to use.

            Required Permissions: Items
        """
        response = self._do_request(action="items", args={
            "type": "use",
            "itemid": item_id,
            "amount": amount,
        })
        return response

    def unpack_item(self, item_id: int, amount: int):
        """unpacks an item
            `item_id` - The item to unpack. You can obtain an itemid using the Item Search endpoint or from the site.
            `amount` - The amount of the item to unpack.

            Required Permissions: Items
        """
        response = self._do_request(action="items", args={
            "type": "unpack",
            "itemid": item_id,
            "amount": amount,
        })
        return response

    def equip_item(self, equip_id: int):
        """equips an item
            `equip_id` - The equipid of the specific piece of equipment you want to equip. You can obtain this from the Users Equipment endpoint.

            Required Permissions: Items
        """
        response = self._do_request(action="items", args={
            "type": "equip",
            "equipid": equip_id,
        })
        return response

    def unequip_item(self, equip_id: int, slot_id: int):
        """unequips an item
            `equip_id` - The equip_id of the specific piece of equipment you want to unequip. You can obtain this from the Users Equipment endpoint. (cannot be used with `slot_id`)
            `slot_id` - The slot_id of the specific slot you want to unequip. You can obtain this from the Users Equipment endpoint. (cannot be used with `equip_id`)

            Required Permissions: Items
        """
        response = self._do_request(action="items", args={
            "type": "unequip",
            "equipid": equip_id,
            "slotid": slot_id,
        })
        return response

    def get_thread_info(self, thread_id: int):
        """gets a forum thread's info
            `thread_id` - the id of the thread

            Required Permissions: Forums
        """
        response = self._do_request(action="forums", args={
            "type": "thread_info",
            "id": thread_id,
        })
        return response

    def get_site_stats(self):
        """gets the site stats

            Required Permissions: None
        """
        response = self._do_request(action="site_stats")
        return response

    def get_torrent_stats(self):
        """gets site's torrent stats

            Required Permissions: Site Info
            Requires Legendary Gamer+
        """
        response = self._do_request(action="torrent_stats")
        return response

    def get_economic_stats(self):
        """gets site's economic stats

            Required Permissions: Site Info
            Requires Legendary Gamer+
        """
        response = self._do_request(action="economic_stats")
        return response

    def get_item_stats(self, item_id: int):
        """gets an item's stats
            `item_id` - the id of the item

            Required Permissions: Items
        """
        response = self._do_request(action="item_stats", args={
            "itemid": "{}".format(item_id),
        })
        return response

    def download_torrent(self, torrent_id: int, write_location: str = None, dry: bool = True):
        """downloads a torrent. This is not a standard part of the API, but is a useful function to have
            `torrent_id` - the id of the torrent
            `dry` - whether to simulate the download by just printing out the download link (default True)
            `write_location` - the location to save the torrent to

            Requires Permissions: User
        """
        if (dry is None or dry is False) and write_location is None:
            raise Exception("write_location must be set if dry is False")

        # cache user info so that we don't have to keep calling the API for every torrent download.
        if self._user is None:
            self._user = self.quick_user()

        response = self._do_request(
            action="download",
            override_url="https://gazellegames.net/torrents.php?",
            dry=dry,
            args={
                "id": torrent_id,
                "authkey": self._user["authkey"],
                "torrent_pass": self._user["passkey"],
            },
        )
        if dry:
            print(response)
            return

        torrent_file = open(write_location, "wb")
        torrent_file.write(response.content)
        torrent_file.close()
        print("Torrent downloaded to {}".format(write_location))

