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

import _moc_protocol
from _moc_protocol import *

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
long_length = struct.calcsize(int_format)
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
        self.unsent += struct.pack(int_format, CMD_SEND_EVENTS)

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
            print 'unhandled', event
            if self.received:
                print 'dazed and confused, trying to continue'
                print 'lusering received data:', repr(self.received)
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
        return dict(zip(tags_keys, self.take_message(tags_format)))
    def take_item(self):
        return dict(zip(item_keys, self.take_message(item_format)))
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

    def send_command(self, command, callback, message_format):
        self.expected_ev_datas.append((message_format, callback))
        self.unsent += struct.pack(int_format, command)

    def get_state(self, callback):
        self.send_command(CMD_GET_STATE, callback, ('state',))
    def get_song_name(self, callback):
        self.send_command(CMD_GET_SNAME, callback, ('string',))

    def handle_error(self):
        traceback.print_exc()

class MocClient(object):
    def __init__(self, protocol):
        self.protocol = protocol
        self.status = None

    def on_connect(self):
        self.protocol.get_song_name(self.on_playing)

    def on_state_changed(self, state):
        if state == 'STATE_PLAY':
            self.protocol.get_song_name(self.on_playing)
        else:
            print 'state', state
    def on_playing(self, path):
        print 'playing', path
    def on_status_msg(self, msg):
        self.status = msg
    def on_plist_add(self, item):
        print 'plist_add', repr(item)
    def on_plist_del(self, path):
        print 'plist_del', path
    def on_plist_move(self, old_path, new_path):
        print 'plist_move', old_path, '->', new_path
    def on_file_tags(self, path, tags):
        print 'file_tags', path, ':', repr(self.tags)

if __name__ == '__main__':
    protocol = AsyncoreMocProtocol()
    client = MocClient(protocol)
    protocol.client = client

    protocol.create_socket(socket.AF_UNIX, socket.SOCK_STREAM)
    protocol.connect('/home/sune/.moc/socket2')

    asyncore.loop()
