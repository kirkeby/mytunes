from __future__ import with_statement

import os
import re
import sys
import pickle
from datetime import datetime

import whoosh.index

import mutagen
import mutagen.mp3
import mutagen.easyid3

# music-library walker
def song_walker(top):
    for directory, dirnames, filenames in os.walk(top):
        for filename in filenames:
            path = os.path.join(directory, filename)
            try:
                song = { 'path': path.decode('utf8') }
            except UnicodeDecodeError:
                print >>sys.stderr, '%s: Not valid UTF-8, bugger off!' % path
            file = mutagen.File(path)
            if not file:
                continue
            kind = file.__class__
            
            # FIXME - What to do, what to do? Multiple values per key...
            if kind in kind_keys:
                song.update((k, unicode(file[n][0]))
                            for k, n in kind_keys[kind].items()
                            if file.has_key(n))
            else:
                song.update((k, unicode(file[k][0]))
                            for k in interesting_keys
                            if file.has_key(k))


            yield song

date_formats = ['%Y', '%Y-%m-%d']
def parse_date(s):
    for fmt in date_formats:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    print >>sys.stderr, '%s: Not a date format I know. Furrfu.' % s
    return None

tracknumber = re.compile('(\d+)')
def parse_tracknumber(s):
    m = tracknumber.match(s)
    if not m:
        return None
    return int(m.group(1))

# Mapping from different meta-data formats to ours
kind_keys = {
    mutagen.mp3.MP3: mutagen.easyid3.EasyID3.valid_keys,
}
interesting_keys = mutagen.easyid3.EasyID3.valid_keys.keys()
key_parsers = {
    'date': parse_date,
    'tracknumber': parse_tracknumber,
}

# Whoosh indexing schema
from whoosh.fields import Schema, ID, TEXT
song_schema = Schema(path=ID(stored=True, unique=True),
                     artist=TEXT, album=TEXT, title=TEXT, composer=TEXT,
                     genre=TEXT, date=TEXT, lyricist=TEXT, version=TEXT,
                     tracknumber=TEXT)

def main(library_path, music_path):
    if os.path.exists(library_path):
        index = whoosh.index.open_dir(library_path)
    else:
        os.makedirs(library_path)
        index = whoosh.index.create_in(library_path, song_schema)

    songs = []
    with index.writer() as writer:
        for song in song_walker(os.path.expanduser(music_path)):
            # We index by the original text, but store parsed values in
            # our own index.
            writer.update_document(**song)

            for key, parser in key_parsers.items():
                if key in song:
                    song[key] = parser(song[key])
                    if song[key] is None:
                        del song[key]
            songs.append(song)

    pickle.dump(songs, open(os.path.join(library_path, 'songs'), 'w'))

if __name__ == '__main__':
    main(os.path.expanduser('~/.mytunes'), os.path.expanduser('~/Music'))
