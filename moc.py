'''Python client for accessing a Music On Console (MOC) server.'''
# -*- encoding: utf-8 -*-

# Note: _moc_protocol.py was auto-generated from protocol.h in
# moc-2.5.0-alpha3 with:
#     grep -F '#define' ../moc-2.5.0-alpha3/protocol.h | tr '\t' ' ' \
#     | sed 's/#define *\([^ ]*\) *\(0x[^ ]*\).*/\1 = \2/' > _moc_protocol.py

import socket
import asyncore
import struct
import traceback
import logging

import _moc_protocol
from _moc_protocol import *

log = logging.getLogger(__name__)

event_names = dict((getattr(_moc_protocol, name), name)
                   for name in dir(_moc_protocol)
                   if name.startswith('EV_'))
# This list was lifted from make_event_packet in moc-2.5.0-alpha3/protocol.c
data_full_events = [EV_PLIST_DEL, EV_STATUS_MSG, EV_PLIST_ADD,
                    EV_FILE_TAGS, EV_PLIST_MOVE]
data_less_events = [event
                    for event in event_names.keys()
                    if event not in data_full_events ]

state_names = dict((getattr(_moc_protocol, name), name)
                   for name in dir(_moc_protocol)
                   if name.startswith('STATE_'))

int_format = 'i'
int_length = struct.calcsize(int_format)
long_format = 'l'
long_length = struct.calcsize(long_format)
max_recv = 1024 * 1024

tags_keys = 'title', 'artist', 'album', 'track', 'time', 'filled'
tags_message_format = ('string', 'string', 'string', 'int', 'int', 'int')
item_keys = ('path', 'tags',) + tags_keys + ('mtime',)
item_message_format = ('string', 'string') + tags_message_format + ('time',)
message_formats = {
    EV_STATUS_MSG: ('string',),
    EV_PLIST_ADD: item_message_format,
    EV_PLIST_DEL: ('string',),
    EV_PLIST_MOVE: ('string', 'string'),
    EV_FILE_TAGS: ('string',) + tags_message_format,
}
empty_values = {'int': 0, 'time': 0, 'string': ''}

# FIXME - The taking and having methods should be merged, so we have
# take_complete_message which either takes a complete message, or leaves the
# buffered data alone.

class AsyncoreMocProtocol(asyncore.dispatcher):
    '''Low-level asyncore client for the MOC protocol.'''
    
    def __init__(self):
        asyncore.dispatcher.__init__(self)
        self.received = ''
        self.unsent = ''
        self.expected_ev_datas = []
        self.client = None

    def handle_connect(self):
        self.client.on_connect()
        self.send_int(CMD_SEND_EVENTS)
        self.get_state(self.client.on_state_changed)

    def writable(self):
        return bool(self.unsent)

    def handle_write(self):
        sent = self.send(self.unsent)
        self.unsent = self.unsent[sent:]

    def handle_read(self):
        self.received += self.recv(max_recv)
        while len(self.received) >= int_length:
            event_id = self.peek_int()
            if not self.have_complete_message(event_id, offset=int_length):
                break
            self.handle_event()

    def handle_event(self):
        event_id = self.take_int()
        event = event_names.get(event_id, hex(event_id))
        handler = getattr(self, 'handle_' + event.lower(),
                          lambda: event_id in data_less_events)
        if not handler():
            log.warn('Unhandled event %s', event)
            if self.received:
                log.error('Lusering received data: %r', self.received)
                log.error('Dazed and confused, trying to continue')
                self.received = ''

    def have_complete_message(self, event_id, offset):
        if event_id == EV_DATA:
            message_format = self.expected_ev_datas[0][0]
        elif event_id in data_full_events:
            message_format = message_formats[event_id]
        else:
            return True

        have = len(self.received)
        for piece in message_format:
            need = self.need(piece, offset)
            if have < offset + need:
                return False
            offset += need
        return True

    def need(self, piece, offset=0):
        if piece == 'int':
            return int_length
        elif piece == 'time':
            return long_length
        elif piece == 'state':
            return int_length
        elif piece == 'string':
            if len(self.received) - offset >= int_length:
                strlen = self.peek_int(offset)
                return int_length + strlen
            else:
                return int_length
        else:
            raise ValueError('unknown message-piece: %r' % piece)

    def peek_int(self, offset=0):
        packed = self.received[offset:offset + int_length]
        return struct.unpack(int_format, packed)[0]

    def take(self, count):
        if len(self.received) < count:
            raise ValueError('Cannot take %d bytes when %d are available'
                             % (count, len(self.received)))
        data, self.received = self.received[:count], self.received[count:]
        return data
    def take_string(self):
        return self.take(self.take_int())
    def take_int(self):
        return struct.unpack(int_format, self.take(int_length))[0]
    def take_state(self):
        return state_names[self.take_int()]
    def take_time(self):
        return struct.unpack(long_format, self.take(long_length))[0]
    def take_tags(self):
        return dict(zip(tags_keys, self.take_message(tags_message_format)))
    def take_item(self):
        return dict(zip(item_keys, self.take_message(item_message_format)))
    def take_message(self, message_format):
        return [ getattr(self, 'take_' + piece_format)()
                 for piece_format in message_format ]

    def handle_ev_state(self):
        self.get_state(self.client.on_state_changed)
        return True
    def handle_ev_data(self):
        if not self.expected_ev_datas:
            return False
        message_format, callback = self.expected_ev_datas.pop(0)
        message = self.take_message(message_format)
        callback(*message)
        return True
    def handle_ev_status_msg(self):
        self.client.on_status_msg(self.take_string())
        return True
    def handle_ev_plist_add(self):
        self.client.on_playlist_add(self.take_item())
        return True
    def handle_ev_plist_del(self):
        self.client.on_playlist_delete(self.take_string())
        return True
    def handle_ev_plist_move(self):
        self.client.on_playlist_move(self.take_string(), self.take_string())
        return True
    def handle_ev_file_tags(self):
        self.client.on_file_tags(self.take_string(), self.take_tags())
        return True

    def send_int(self, i):
        self.unsent += struct.pack(int_format, i)
    def send_time(self, t):
        self.unsent += struct.pack(long_format, t)
    def send_string(self, s):
        self.send_int(len(s))
        self.unsent += s
    def send_item(self, item):
        for key, type in zip(item_keys, item_message_format):
            getattr(self, 'send_' + type)(item.get(key, empty_values[type]))
    def send_command(self, command, callback, message_format):
        self.expected_ev_datas.append((message_format, callback))
        self.send_int(command)

    def set_option(self, name, value):
        self.send_int(CMD_SET_OPTION)
        self.send_string(name)
        self.send_int(value)
    
    def play(self, path):
        self.send_int(CMD_STOP)
        self.send_int(CMD_LIST_CLEAR)
        self.send_int(CMD_LIST_ADD)
        self.send_string(path)
        self.send_int(CMD_PLAY)
        self.send_string('')

    def get_option(self, name, callback):
        self.send_command(CMD_GET_OPTION, callback, ('int',))
        self.send_string(name)
    def get_state(self, callback):
        self.send_command(CMD_GET_STATE, callback, ('state',))
    def get_song_name(self, callback):
        self.send_command(CMD_GET_SNAME, callback, ('string',))

    def handle_error(self):
        log.error('Rome is burning!', exc_info=True)

class MusicLibrary(object):
    def __init__(self, songs):
        self.songs = []
        self._path_index = {}

        for song in songs:
            self.add(song)

    def add(self, song):
        self._path_index[song['path']] = len(self.songs)
        self.songs.append(song)

    # by-index accessors
    def __len__(self):
        return len(self.songs)
    def get_at(self, index):
        return self.songs[index]
    def index(self, path):
        return self._path_index[path]

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
            return self.library.get_at((i + 1) % len(self.library))
        else:
            return self.library.get_at(0)

class MocClient(object):
    def __init__(self, protocol, player):
        self.protocol = protocol
        self.state = 'STATE_NONE'
        self.status = None
        self.player = player

    def on_connect(self):
        log.debug('on_connect')
        log.debug('disabling AutoNext')
        self.protocol.set_option('AutoNext', 0)

    def on_state_changed(self, state):
        transition = (self.state + '->' + state).replace('STATE_', '').lower()
        log.debug('on_state_changed: ' + transition)
        self.state = state
        if transition == 'stop->play' or transition == 'none->play':
            self.protocol.get_song_name(self.on_playing)
        elif transition == 'none->stop':
            # Connected to a stopped moc server, start it!
            self.play_next_song()
        elif transition == 'play->stop' and self.status <> 'Opening...':
            # This is magically fucked up. The moc-server is multi-threaded,
            # and wether we get play->play or play->stop->play state
            # transitions, when some other player sends a CMD_PLAY, depends on
            # timing, luck and the phase of the moon. But, 9 times out of 10 we
            # get an 'Opening...' status-message from the server, before a
            # play->stop->play transition. So, this will work as expected in
            # most cases, but it is not fool-proof. Blame the morons who
            # "designed" the brain damage that is the moc protocol.
            self.play_next_song()

    def on_playing(self, path):
        log.debug('on_playing: ' + repr(path))
        if path:
            self.player.on_playing(path)
    def on_status_msg(self, msg):
        log.debug('on_status_msg: %r', msg)
        self.status = msg
    def on_playlist_add(self, item):
        log.debug('on_playlist_add: %r', item)
    def on_playlist_del(self, path):
        log.debug('on_playlist_del: %r', path)
    def on_playlist_move(self, old_path, new_path):
        log.debug('on_playlist_move: %r -> %r', old_path, new_path)
    def on_file_tags(self, path, tags):
        log.debug('on_file_tags: %r: %r', path, tags)

    def play_next_song(self):
        log.debug('playing next song')
        self.protocol.play(self.player.next()['path'])

playable_extensions = '.mp3', '.flac', '.aac', '.wav', '.ogg'

if __name__ == '__main__':
    logging.basicConfig(level=0)
    logging.getLogger().setLevel(0)

    import os
    import sys
    from commands import getoutput
    song_dirs = sys.argv[1:]
    songs = [ dict(path=os.path.join(song_dir, filename))
              for song_dir in song_dirs
              for filename in os.listdir(song_dir) 
              if os.path.splitext(filename)[1] in playable_extensions ]
    library = MusicLibrary(songs)
    player = Player(library)

    protocol = AsyncoreMocProtocol()
    client = MocClient(protocol, player)
    protocol.client = client

    if not getoutput('pgrep mocp').strip():
        os.system('mocp -S')

    protocol.create_socket(socket.AF_UNIX, socket.SOCK_STREAM)
    protocol.connect('/home/sune/.moc/socket2')

    asyncore.loop()
