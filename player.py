from random import randrange
import logging
log = logging.getLogger(__name__)

class Player(object):
    def __init__(self, library):
        self.library = library
        self.client = None
        self.playing = None
        self.random = True
        self.listeners = []

    def on_playing(self, path):
        try:
            i = self.library.index(path)
            self.playing = self.library.get_at(i)
            for l in self.listeners:
                l('Playing', '%(title)s by %(artist)s' % self.playing)
        except KeyError:
            # FIXME - need a value to represent unknown?
            log.info('playing unknown song: %r', path)
            self.playing = None

    def next(self):
        if self.random:
            i = randrange(0, len(self.library))
        elif self.playing:
            try:
               i = self.library.index(self.playing['path'])
            except KeyError:
                # Someone may have removed the song from the library,
                # or maybe this is a limited-view without this song.
                # FIXME - should we use bisection to find the next song
                # after the one we're missing?
                i = -1
            i = (i + 1) % len(self.library)
        return self.library.get_at(i)

    def play(self, song):
        self.client.play(song['path'].encode('utf-8'))

    def play_next(self):
        self.play(self.next())
