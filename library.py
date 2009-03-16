import os
import pickle
import whoosh.index
from operator import itemgetter
from whoosh.qparser import MultifieldParser
from whoosh.searching import Searcher

default_search_fiels = 'artist', 'album', 'title'
default_sort_fields = 'artist', 'year', 'album', 'tracknumber'

class MusicLibrary(object):
    def open(self, library_path):
        self.ix = whoosh.index.open_dir(library_path)
        self.searcher = Searcher(self.ix)
        self.qparser = MultifieldParser(fieldnames=default_search_fiels)

        songs_path = os.path.join(library_path, 'songs')
        self.songs = self.all_songs = pickle.load(open(songs_path))
        self.sort()

    # view manipulation
    def limit(self, q):
        if q is None:
            self.songs = self.all_songs
        else:
            self.songs = list(self.find(q))
        self.sort()
        
    def sort(self, fields=default_sort_fields):
        def key(song):
            return tuple(song.get(key) for key in fields)
        self.songs.sort(key=key)
        self._reindex()
    def _reindex(self):
        self._path_index = dict((song['path'], i)
                                for i, song in enumerate(self.songs))

    # by-index accessors
    def __len__(self):
        return len(self.songs)
    def get_at(self, index):
        return self.songs[index]
    def index(self, path):
        return self._path_index[path]

    # by-index accessors
    def find(self, q):
        for doc in self.searcher.search(self.qparser.parse(q)):
            yield self.songs[self._path_index[doc['path']]]
