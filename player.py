class Player(object):
    def __init__(self, library):
        self.library = library
        self.client = None
        self.playing = None

    def on_playing(self, path):
        try:
            i = self.library.index(path)
            self.playing = self.library.get_at(i)
        except KeyError:
            # FIXME - need a value to represent unknown?
            log.info('playing unknown song: %r', path)
            self.playing = None

    def next(self):
        if self.playing:
            try:
               i = self.library.index(self.playing['path'])
            except KeyError:
                # Someone may have removed the song from the library,
                # or maybe this is a limited-view without this song.
                i = -1
            return self.library.get_at((i + 1) % len(self.library))
        else:
            return self.library.get_at(0)

    def play(self, song):
        self.client.play(song['path'].encode('utf-8'))

    def play_next(self):
        self.play(self.next())
