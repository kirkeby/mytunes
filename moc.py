'''Python client for accessing a Music On Console (MOC) server.'''

# Note: _moc_protocol.py was auto-generated from protocol.h in
# moc-2.5.0-alpha3 with:
#     grep -F '#define' ../moc-2.5.0-alpha3/protocol.h | tr '\t' ' ' \
#     | sed 's/#define *\([^ ]*\) *\(0x[^ ]*\).*/\1 = \2/' > _moc_protocol.py

import socket
import asyncore
import struct

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

int_format = 'i'
int_length = struct.calcsize(int_format)
long_format = 'l'
long_length = struct.calcsize(int_format)
max_recv = 1024 * 1024

class AsyncoreMocProtocol(asyncore.dispatcher):
    '''Low-level asyncore client for the MOC protocol.'''
    
    def __init__(self):
        asyncore.dispatcher.__init__(self)
        self.received = ''
        self.unsent = ''
        self.ev_data_callbacks = []

    def handle_connect(self):
        def cb(sname):
            print 'Playing:', sname
        self.get_song_name(cb)
        self.unsent += struct.pack(int_format, CMD_SEND_EVENTS)

    def writable(self):
        return bool(self.unsent)

    def handle_write(self):
        sent = self.send(self.unsent)
        self.unsent = self.unsent[sent:]

    def handle_read(self):
        self.received += self.recv(max_recv)
        while len(self.received) >= int_length:
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

    def take(self, count):
        if len(self.received) < count:
            raise ValueError('Cannot take %d bytes when %d is available'
                             % (count, len(self.received)))
        data, self.received = self.received[:count], self.received[count:]
        return data
    def take_string(self):
        return self.take(self.take_int())
    def take_int(self):
        return struct.unpack(int_format, self.take(int_length))[0]
    def take_time(self):
        return struct.unpack(long_format, self.take(long_length))[0]
    def take_tags(self):
        return {
            'title': self.take_string(),
            'artist': self.take_string(),
            'album': self.take_string(),
            'track': self.take_int(),
            'time': self.take_int(),
            'filled': self.take_int(),
        }
    def take_item(self):
        item = {
            'path': self.take_string(),
            'tags': self.take_string(),
        }
        item.update(self.take_tags())
        item['mtime'] = self.take_time()
        return item

    def handle_ev_data(self):
        if not self.ev_data_callbacks:
            return False
        return self.ev_data_callbacks.pop(0)()
    def handle_ev_status_msg(self):
        print 'status', self.take_string()
        return True
    def handle_ev_plist_add(self):
        return 'plist_add', repr(self.take_item())
        return True
    def handle_ev_plist_del(self):
        print 'plist_del', self.take_string()
        return True
    def handle_ev_plist_move(self):
        print 'plist_move', self.take_string(), '->', self.take_string()
        return True
    def handle_ev_file_tags(self):
        return 'file_tags', self.take_string(), ':', self.take_tags()
        return True

    def send_command(self, ev_data_callback, command):
        self.ev_data_callbacks.append(ev_data_callback)
        self.unsent += struct.pack(int_format, command)

    def get_song_name(self, callback):
        def ev_data_callback():
            callback(self.take_string())
            return True
        self.send_command(ev_data_callback, CMD_GET_SNAME)

if __name__ == '__main__':
    client = AsyncoreMocProtocol()
    client.create_socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.connect('/home/sune/.moc/socket2')
    asyncore.loop()
