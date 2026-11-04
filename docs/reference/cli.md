# `ytb-playlist`

Download YouTube playlists as MP3 or MP4, named by date and tagged for Apple Music.

**Usage**:

```console
$ ytb-playlist [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--config <path>`: Config file to use.
* `--version`: Show the version.
* `--install-completion`: Install completion for the current shell.
* `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
* `--help`: Show this message and exit.

**Commands**:

* `doctor`: Check yt-dlp, ffmpeg, deno and the output...
* `info`: Show a playlist&#x27;s title, ID and number of...
* `fetch`: Download playlists into one folder each,...
* `tag`: Write tags and the cover from the saved...
* `cover`: Embed the saved thumbnail again, keeping...
* `rename`: Apply the naming rules.
* `sync`: Download what&#x27;s new in saved playlists.
* `playlist`: Manage saved playlists.
* `config`: Inspect the configuration.

## `ytb-playlist doctor`

Check yt-dlp, ffmpeg, deno and the output folder.

**Usage**:

```console
$ ytb-playlist doctor [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.

## `ytb-playlist info`

Show a playlist&#x27;s title, ID and number of items.

**Usage**:

```console
$ ytb-playlist info [OPTIONS] {url}
```

**Arguments**:

* `url`: Playlist URL.  [required]

**Options**:

* `--help`: Show this message and exit.

## `ytb-playlist fetch`

Download playlists into one folder each, skipping what&#x27;s already there.

**Usage**:

```console
$ ytb-playlist fetch [OPTIONS] {urls}...
```

**Arguments**:

* `urls...`: Playlist URLs.  [required]

**Options**:

* `--format <mp3|mp4>`: One format per playlist.  [required]
* `--out <path>`: Folder that holds the playlists.
* `--items <str>`: Positions, such as 1:10 or 1,3:4.
* `--dry-run / --no-dry-run`: Report what&#x27;s new; write nothing.  [default: no-dry-run]
* `--cover <episode|playlist>`: Cover for each track.
* `--max-height <int range>`: Video height cap.  [x&gt;=1]
* `--quality <max>`: max also allows formats Apple apps may refuse.
* `--help`: Show this message and exit.

## `ytb-playlist tag`

Write tags and the cover from the saved metadata. Nothing is downloaded.

**Usage**:

```console
$ ytb-playlist tag [OPTIONS] {paths}...
```

**Arguments**:

* `paths...`: Files or playlist folders.  [required]

**Options**:

* `--cover <square|wide>`: Cover shape.
* `--help`: Show this message and exit.

## `ytb-playlist cover`

Embed the saved thumbnail again, keeping every other tag.

**Usage**:

```console
$ ytb-playlist cover [OPTIONS] {paths}...
```

**Arguments**:

* `paths...`: Files or playlist folders.  [required]

**Options**:

* `--cover <square|wide>`: Cover shape.
* `--help`: Show this message and exit.

## `ytb-playlist rename`

Apply the naming rules. Old names are kept in a log beside the state file.

**Usage**:

```console
$ ytb-playlist rename [OPTIONS] {paths}...
```

**Arguments**:

* `paths...`: Files or playlist folders.  [required]

**Options**:

* `--dry-run / --no-dry-run`: Show the new names; change nothing.  [default: no-dry-run]
* `--help`: Show this message and exit.

## `ytb-playlist sync`

Download what&#x27;s new in saved playlists.

**Usage**:

```console
$ ytb-playlist sync [OPTIONS] [name]
```

**Arguments**:

* `name`: Saved name.

**Options**:

* `--all`: Every saved playlist.
* `--retry-failed / --no-retry-failed`: Try permanent failures again.  [default: no-retry-failed]
* `--dry-run / --no-dry-run`: Report what&#x27;s new; write nothing.  [default: no-dry-run]
* `--help`: Show this message and exit.

## `ytb-playlist playlist`

Manage saved playlists.

**Usage**:

```console
$ ytb-playlist playlist [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `add`: Save a playlist so `sync` can keep it up...
* `list`: Show saved playlists.
* `remove`: Forget a saved playlist.

### `ytb-playlist playlist add`

Save a playlist so `sync` can keep it up to date.

**Usage**:

```console
$ ytb-playlist playlist add [OPTIONS] {url}
```

**Arguments**:

* `url`: Playlist URL.  [required]

**Options**:

* `--format <mp3|mp4>`: Fixed once saved.  [required]
* `--name <str>`: Defaults to the playlist title.
* `--album <str>`: Album tag.
* `--genre <str>`: Genre tag.
* `--cover <episode|playlist>`: Cover for each track.
* `--max-height <int range>`: Video height cap.  [x&gt;=1]
* `--help`: Show this message and exit.

### `ytb-playlist playlist list`

Show saved playlists.

**Usage**:

```console
$ ytb-playlist playlist list [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.

### `ytb-playlist playlist remove`

Forget a saved playlist. Its folder and files are left alone.

**Usage**:

```console
$ ytb-playlist playlist remove [OPTIONS] {name}
```

**Arguments**:

* `name`: Saved name.  [required]

**Options**:

* `--help`: Show this message and exit.

## `ytb-playlist config`

Inspect the configuration.

**Usage**:

```console
$ ytb-playlist config [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `path`: Show which config file is used.
* `show`: Show the settings after merging the file...

### `ytb-playlist config path`

Show which config file is used.

**Usage**:

```console
$ ytb-playlist config path [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.

### `ytb-playlist config show`

Show the settings after merging the file and the environment.

**Usage**:

```console
$ ytb-playlist config show [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.
