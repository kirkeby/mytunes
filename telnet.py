import asyncore
import asynchat

import logging
log = logging.getLogger(__name__)

class AsyncoreServer(asyncore.dispatcher):
    def __init__(self, factory):
        asyncore.dispatcher.__init__(self)
        self.factory = factory

    def handle_error(self):
        log.error('Rome is burning!', exc_info=True)

    def handle_accept(self):
        self.factory(*self.accept())

command_prefix = 'cmd_'
class TelnetProtocol(asynchat.async_chat):
    def __init__(self, sprockert):
        asynchat.async_chat.__init__(self, sprockert)
        self.set_terminator('\n')
        self.buffer = []

        self.commands = [
            (name.replace(command_prefix, ''), getattr(self, name))
            for name in dir(self)
            if name.startswith(command_prefix)
        ]

        self.push('myTunes/0.1 here\n')

    def collect_incoming_data(self, data):
        self.buffer.append(data)

    def found_terminator(self):
        line = ''.join(self.buffer).strip()
        self.buffer = []

        if not line:
            return

        pieces = line.split(None, 1)
        cmd = pieces[0]
        
        matching = [handler for name, handler in self.commands
                            if name.startswith(cmd)]
        if not matching:
            reply = 'Unknown command'
        elif len(matching) > 1:
            reply = 'More than one command found'
        else:
            try:
                reply = matching[0](*pieces)
            except Exception, ex:
                self.handle_error()
                self.push('Error: %r\n' % ex)

    def handle_error(self):
        log.error('Rome is burning!', exc_info=True)

    def cmd_quit(self, cmd):
        self.close()
        return 'Bye.'

    def cmd_next(self, cmd):
        self.player.play_next()

    def cmd_limit(self, cmd, *filters):
        self.library.limit(None)
        self.cmd_Limit(cmd, *filters)

    def cmd_Limit(self, cmd, *filters):
        if filters:
            self.library.limit(' '.join(filters))
        self.push('%d song(s)\n' % len(self.library))

    def cmd_status(self, cmd):
        if self.player.playing:
            self.push('Playing: %s\n' % self.player.playing)
        else:
            self.push('Not playing')

        self.push('%d/%d songs visible\n' % (len(self.library),
                                             len(self.library.all_songs)))

    def cmd_find(self, cmd, *filters):
        self.last_search = list(self.library.find(' '.join(filters)))
        for i, song in enumerate(self.last_search):
            self.push('% 3d. %s\n' % (i, song))

    def cmd_play(self, cmd, n):
        self.player.play(self.last_search[int(n)])