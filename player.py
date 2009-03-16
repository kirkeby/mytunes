class Player(object):
    def __init__(self, library):
        self.library = library
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
            i = self.library.index(self.playing['path'])
            print self.library.songs[i-2:i+2]
            return self.library.get_at((i + 1) % len(self.library))
        else:
            return self.library.get_at(0)

