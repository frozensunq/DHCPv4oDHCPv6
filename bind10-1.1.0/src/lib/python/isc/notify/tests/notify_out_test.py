# Copyright (C) 2010-2012  Internet Systems Consortium.
#
# Permission to use, copy, modify, and distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND INTERNET SYSTEMS CONSORTIUM
# DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL
# INTERNET SYSTEMS CONSORTIUM BE LIABLE FOR ANY SPECIAL, DIRECT,
# INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING
# FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT,
# NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION
# WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

import unittest
import sys
import os
import tempfile
import time
import socket
from isc.notify import notify_out, SOCK_DATA
import isc.log
from isc.dns import *

TESTDATA_SRCDIR = os.getenv("TESTDATASRCDIR")

def get_notify_msgdata(zone_name, qid=0):
    """A helper function to generate a notify response in wire format.

    Parameters:
    zone_name(isc.dns.Name()) The zone name for the notify.  Used as the
    question name.
    qid (int): The QID of the response.  In most test cases a value of 0 is
    expected.

    """
    m = Message(Message.RENDER)
    m.set_opcode(Opcode.NOTIFY)
    m.set_rcode(Rcode.NOERROR)
    m.set_qid(qid)
    m.set_header_flag(Message.HEADERFLAG_QR)
    m.add_question(Question(zone_name, RRClass.IN, RRType.SOA))

    renderer = MessageRenderer()
    m.to_wire(renderer)
    return renderer.get_data()

# our fake socket, where we can read and insert messages
class MockSocket():
    def __init__(self):
        self._local_sock, self._remote_sock = socket.socketpair()
        self.__raise_on_recv = False # see set_raise_on_recv()

    def connect(self, to):
        pass

    def fileno(self):
        return self._local_sock.fileno()

    def close(self):
        self._local_sock.close()
        self._remote_sock.close()

    def sendto(self, data, flag, dst):
        return self._local_sock.send(data)

    def recvfrom(self, length):
        if self.__raise_on_recv:
            raise socket.error('fake error')
        data = self._local_sock.recv(length)
        return (data, None)

    # provide a remote end which can write data to MockSocket for testing.
    def remote_end(self):
        return self._remote_sock

    def set_raise_on_recv(self, on):
        """A helper to force recvfrom() to raise an exception or cancel it.

        The next call to recvfrom() will result in an exception iff parameter
        'on' (bool) is set to True.
        """
        self.__raise_on_recv = on

# We subclass the ZoneNotifyInfo class we're testing here, only
# to override the create_socket() method.
class MockZoneNotifyInfo(notify_out.ZoneNotifyInfo):
    def create_socket(self, addrinfo):
        super().create_socket(addrinfo)
        # before replacing the underlying socket, remember the address family
        # of the original socket so that tests can check that.
        self.sock_family = self._sock.family
        self._sock.close()
        self._sock = MockSocket()
        self._sock.family = self.sock_family
        return self._sock

class TestZoneNotifyInfo(unittest.TestCase):
    def setUp(self):
        self.info = notify_out.ZoneNotifyInfo('example.net.', 'IN')

    def test_prepare_finish_notify_out(self):
        self.info.prepare_notify_out()
        self.assertNotEqual(self.info.notify_timeout, None)
        self.assertIsNone(self.info._notify_current)

        self.info.finish_notify_out()
        self.assertEqual(self.info._sock, None)
        self.assertEqual(self.info.notify_timeout, None)

    def test_set_next_notify_target(self):
        self.info.notify_slaves.append(('127.0.0.1', 53))
        self.info.notify_slaves.append(('192.0.2.1', 5353))
        self.info.prepare_notify_out()
        self.assertEqual(self.info.get_current_notify_target(), ('127.0.0.1', 53))

        self.info.set_next_notify_target()
        self.assertEqual(self.info.get_current_notify_target(), ('192.0.2.1', 5353))
        self.info.set_next_notify_target()
        self.assertIsNone(self.info.get_current_notify_target())

        temp_info = notify_out.ZoneNotifyInfo('example.com.', 'IN')
        temp_info.prepare_notify_out()
        self.assertIsNone(temp_info.get_current_notify_target())


class TestNotifyOut(unittest.TestCase):
    def setUp(self):
        self._db_file = TESTDATA_SRCDIR + '/test.sqlite3'
        self._notify = notify_out.NotifyOut(self._db_file)
        self._notify._notify_infos[('example.com.', 'IN')] = MockZoneNotifyInfo('example.com.', 'IN')
        self._notify._notify_infos[('example.com.', 'CH')] = MockZoneNotifyInfo('example.com.', 'CH')
        self._notify._notify_infos[('example.net.', 'IN')] = MockZoneNotifyInfo('example.net.', 'IN')
        self._notify._notify_infos[('example.org.', 'IN')] = MockZoneNotifyInfo('example.org.', 'IN')
        self._notify._notify_infos[('example.org.', 'CH')] = MockZoneNotifyInfo('example.org.', 'CH')

        net_info = self._notify._notify_infos[('example.net.', 'IN')]
        net_info.notify_slaves.append(('127.0.0.1', 53))
        net_info.notify_slaves.append(('192.0.2.1', 5353))
        com_info = self._notify._notify_infos[('example.com.', 'IN')]
        com_info.notify_slaves.append(('192.0.2.1', 5353))
        com_ch_info = self._notify._notify_infos[('example.com.', 'CH')]
        com_ch_info.notify_slaves.append(('192.0.2.1', 5353))
        # Keep the original library version in case a test case replaces it
        self.__time_time_orig = notify_out.time.time

    def tearDown(self):
        self._notify._counters.clear_all()
        # restore the original time.time() in case it was replaced.
        notify_out.time.time = self.__time_time_orig

    def test_send_notify(self):
        notify_out._MAX_NOTIFY_NUM = 2

        self._notify._nonblock_event.clear()
        self.assertTrue(self._notify.send_notify('example.net'))
        self.assertTrue(self._notify._nonblock_event.isSet())
        self.assertEqual(self._notify.notify_num, 1)
        self.assertEqual(self._notify._notifying_zones[0], ('example.net.', 'IN'))

        self.assertTrue(self._notify.send_notify('example.com'))
        self.assertEqual(self._notify.notify_num, 2)
        self.assertEqual(self._notify._notifying_zones[1], ('example.com.', 'IN'))

        # notify_num is equal to MAX_NOTIFY_NUM, append it to waiting_zones list.
        self._notify._nonblock_event.clear()
        self.assertTrue(self._notify.send_notify('example.com', 'CH'))
        # add waiting zones won't set nonblock_event.
        self.assertFalse(self._notify._nonblock_event.isSet())
        self.assertEqual(self._notify.notify_num, 2)
        self.assertEqual(1, len(self._notify._waiting_zones))

        # zone_id is already in notifying_zones list, append it to waiting_zones list.
        self.assertTrue(self._notify.send_notify('example.net'))
        self.assertEqual(2, len(self._notify._waiting_zones))
        self.assertEqual(self._notify._waiting_zones[1], ('example.net.', 'IN'))

        # zone_id is already in waiting_zones list, skip it.
        self.assertTrue(self._notify.send_notify('example.net'))
        self.assertEqual(2, len(self._notify._waiting_zones))

        # has no slave masters, skip it.
        self.assertTrue(self._notify.send_notify('example.org.', 'CH'))
        self.assertEqual(self._notify.notify_num, 2)
        self.assertEqual(2, len(self._notify._waiting_zones))

        self.assertTrue(self._notify.send_notify('example.org.'))
        self.assertEqual(self._notify.notify_num, 2)
        self.assertEqual(2, len(self._notify._waiting_zones))

        # zone does not exist, should return False, and no change in other
        # values
        self.assertFalse(self._notify.send_notify('does.not.exist.'))
        self.assertEqual(self._notify.notify_num, 2)
        self.assertEqual(2, len(self._notify._waiting_zones))

        self.assertFalse(self._notify.send_notify('example.net.', 'CH'))
        self.assertEqual(self._notify.notify_num, 2)
        self.assertEqual(2, len(self._notify._waiting_zones))

    def test_wait_for_notify_reply(self):
        self._notify.send_notify('example.net.')
        self._notify.send_notify('example.com.')

        notify_out._MAX_NOTIFY_NUM = 2
        self._notify.send_notify('example.org.')
        replied_zones, timeout_zones = self._notify._wait_for_notify_reply()
        self.assertEqual(len(replied_zones), 0)
        self.assertEqual(len(timeout_zones), 2)

        # Trigger timeout events to "send" notifies via a mock socket
        for zone in timeout_zones:
            self._notify._zone_notify_handler(timeout_zones[zone],
                                              notify_out._EVENT_TIMEOUT)

        # Now make one socket be readable
        self._notify._notify_infos[('example.net.', 'IN')].notify_timeout = time.time() + 10
        self._notify._notify_infos[('example.com.', 'IN')].notify_timeout = time.time() + 10

        #Send some data to socket 12340, to make the target socket be readable
        self._notify._notify_infos[('example.net.', 'IN')]._sock.remote_end().send(b'data')
        replied_zones, timeout_zones = self._notify._wait_for_notify_reply()
        self.assertEqual(len(replied_zones), 1)
        self.assertEqual(len(timeout_zones), 1)
        self.assertTrue(('example.net.', 'IN') in replied_zones.keys())
        self.assertTrue(('example.com.', 'IN') in timeout_zones.keys())
        self.assertLess(time.time(), self._notify._notify_infos[('example.com.', 'IN')].notify_timeout)

    def test_wait_for_notify_reply_2(self):
        # Test the returned value when the read_side socket is readable.
        self._notify.send_notify('example.net.')
        self._notify.send_notify('example.com.')

        # Now make one socket be readable
        self._notify._notify_infos[('example.net.', 'IN')].notify_timeout = time.time() + 10
        self._notify._notify_infos[('example.com.', 'IN')].notify_timeout = time.time() + 10

        if self._notify._read_sock is not None:
            self._notify._read_sock.close()
        if self._notify._write_sock is not None:
            self._notify._write_sock.close()
        self._notify._read_sock, self._notify._write_sock = socket.socketpair()
        self._notify._write_sock.send(SOCK_DATA)
        replied_zones, timeout_zones = self._notify._wait_for_notify_reply()
        self.assertEqual(0, len(replied_zones))
        self.assertEqual(0, len(timeout_zones))

    def test_notify_next_target(self):
        self._notify.send_notify('example.net.')
        self._notify.send_notify('example.com.')
        notify_out._MAX_NOTIFY_NUM = 2
        # zone example.org. has no slave servers.
        self._notify.send_notify('example.org.')
        self._notify.send_notify('example.com.', 'CH')

        info = self._notify._notify_infos[('example.net.', 'IN')]
        self._notify._notify_next_target(info)
        self.assertEqual(0, info.notify_try_num)
        self.assertEqual(info.get_current_notify_target(), ('192.0.2.1', 5353))
        self.assertEqual(2, self._notify.notify_num)
        self.assertEqual(1, len(self._notify._waiting_zones))

        self._notify._notify_next_target(info)
        self.assertEqual(0, info.notify_try_num)
        self.assertIsNone(info.get_current_notify_target())
        self.assertEqual(2, self._notify.notify_num)
        self.assertEqual(0, len(self._notify._waiting_zones))

        example_com_info = self._notify._notify_infos[('example.com.', 'IN')]
        self._notify._notify_next_target(example_com_info)
        self.assertEqual(1, self._notify.notify_num)
        self.assertEqual(1, len(self._notify._notifying_zones))
        self.assertEqual(0, len(self._notify._waiting_zones))

    def test_handle_notify_reply(self):
        fake_address = ('192.0.2.1', 53)
        self.assertEqual(notify_out._BAD_REPLY_PACKET, self._notify._handle_notify_reply(None, b'badmsg', fake_address))
        example_com_info = self._notify._notify_infos[('example.com.', 'IN')]
        example_com_info.notify_msg_id = 0X2f18

        # test with right notify reply message
        data = b'\x2f\x18\xa0\x00\x00\x01\x00\x00\x00\x00\x00\x00\x07example\03com\x00\x00\x06\x00\x01'
        self.assertEqual(notify_out._REPLY_OK, self._notify._handle_notify_reply(example_com_info, data, fake_address))

        # test with unright query id
        data = b'\x2e\x18\xa0\x00\x00\x01\x00\x00\x00\x00\x00\x00\x07example\03com\x00\x00\x06\x00\x01'
        self.assertEqual(notify_out._BAD_QUERY_ID, self._notify._handle_notify_reply(example_com_info, data, fake_address))

        # test with unright query name
        data = b'\x2f\x18\xa0\x00\x00\x01\x00\x00\x00\x00\x00\x00\x07example\03net\x00\x00\x06\x00\x01'
        self.assertEqual(notify_out._BAD_QUERY_NAME, self._notify._handle_notify_reply(example_com_info, data, fake_address))

        # test with unright opcode
        data = b'\x2f\x18\x80\x00\x00\x01\x00\x00\x00\x00\x00\x00\x07example\03com\x00\x00\x06\x00\x01'
        self.assertEqual(notify_out._BAD_OPCODE, self._notify._handle_notify_reply(example_com_info, data, fake_address))

        # test with unright qr
        data = b'\x2f\x18\x10\x10\x00\x01\x00\x00\x00\x00\x00\x00\x07example\03com\x00\x00\x06\x00\x01'
        self.assertEqual(notify_out._BAD_QR, self._notify._handle_notify_reply(example_com_info, data, fake_address))

    def test_send_notify_message_udp_ipv4(self):
        example_com_info = self._notify._notify_infos[('example.net.', 'IN')]

        self.assertRaises(isc.cc.data.DataNotFoundError,
                          self._notify._counters.get,
                          'zones', 'example.net.', 'notifyoutv4')
        self.assertRaises(isc.cc.data.DataNotFoundError,
                          self._notify._counters.get,
                          'zones', 'example.net.', 'notifyoutv6')

        example_com_info.prepare_notify_out()
        ret = self._notify._send_notify_message_udp(example_com_info,
                                                    ('192.0.2.1', 53))
        self.assertTrue(ret)
        self.assertEqual(socket.AF_INET, example_com_info.sock_family)
        self.assertEqual(self._notify._counters.get(
                'zones', 'example.net.', 'notifyoutv4'), 1)
        self.assertEqual(self._notify._counters.get(
                'zones', 'example.net.', 'notifyoutv6'), 0)

    def test_send_notify_message_udp_ipv6(self):
        example_com_info = self._notify._notify_infos[('example.net.', 'IN')]

        self.assertRaises(isc.cc.data.DataNotFoundError,
                          self._notify._counters.get,
                          'zones', 'example.net.', 'notifyoutv4')
        self.assertRaises(isc.cc.data.DataNotFoundError,
                          self._notify._counters.get,
                          'zones', 'example.net.', 'notifyoutv6')

        ret = self._notify._send_notify_message_udp(example_com_info,
                                                    ('2001:db8::53', 53))
        self.assertTrue(ret)
        self.assertEqual(socket.AF_INET6, example_com_info.sock_family)
        self.assertEqual(self._notify._counters.get(
                'zones', 'example.net.', 'notifyoutv4'), 0)
        self.assertEqual(self._notify._counters.get(
                'zones', 'example.net.', 'notifyoutv6'), 1)

    def test_send_notify_message_with_bogus_address(self):
        example_com_info = self._notify._notify_infos[('example.net.', 'IN')]

        self.assertRaises(isc.cc.data.DataNotFoundError,
                          self._notify._counters.get,
                          'zones', 'example.net.', 'notifyoutv4')
        self.assertRaises(isc.cc.data.DataNotFoundError,
                          self._notify._counters.get,
                          'zones', 'example.net.', 'notifyoutv6')

        # As long as the underlying data source validates RDATA this shouldn't
        # happen, but right now it's not actually the case.  Even if the
        # data source does its job, it's prudent to confirm the behavior for
        # an unexpected case.
        ret = self._notify._send_notify_message_udp(example_com_info,
                                                    ('invalid', 53))
        self.assertFalse(ret)

        self.assertRaises(isc.cc.data.DataNotFoundError,
                          self._notify._counters.get,
                          'zones', 'example.net.', 'notifyoutv4')
        self.assertRaises(isc.cc.data.DataNotFoundError,
                          self._notify._counters.get,
                          'zones', 'example.net.', 'notifyoutv4')

    def test_zone_notify_handler(self):
        sent_addrs = []
        def _fake_send_notify_message_udp(notify_info, addrinfo):
            sent_addrs.append(addrinfo)
            pass
        notify_out.time.time = lambda: 42
        self._notify._send_notify_message_udp = _fake_send_notify_message_udp
        self._notify.send_notify('example.net.')

        example_net_info = self._notify._notify_infos[('example.net.', 'IN')]

        # On timeout, the request will be resent until try_num reaches the max
        self.assertEqual([], sent_addrs)
        example_net_info.notify_try_num = 2
        self._notify._zone_notify_handler(example_net_info,
                                          notify_out._EVENT_TIMEOUT)
        self.assertEqual(3, example_net_info.notify_try_num)
        self.assertEqual([('127.0.0.1', 53)], sent_addrs)
        # the timeout time will be set to "current time(=42)"+2**(new try_num)
        self.assertEqual(42 + 2**3, example_net_info.notify_timeout)

        # If try num exceeds max, the next slave will be tried (and then
        # next zone, but for this test it sufficies to check the former case)
        example_net_info.notify_try_num = 5
        self._notify._zone_notify_handler(example_net_info,
                                          notify_out._EVENT_TIMEOUT)
        self.assertEqual(0, example_net_info.notify_try_num) # should be reset
        self.assertEqual(('192.0.2.1', 5353), example_net_info._notify_current)

        # Possible event is "read" or "timeout".
        cur_tgt = example_net_info._notify_current
        example_net_info.notify_try_num = notify_out._MAX_NOTIFY_TRY_NUM
        self.assertRaises(AssertionError, self._notify._zone_notify_handler,
                          example_net_info, notify_out._EVENT_TIMEOUT + 1)

    def test_zone_notify_read_handler(self):
        """Similar to the previous test, but focus on the READ events.

        """
        sent_addrs = []
        def _fake_send_notify_message_udp(notify_info, addrinfo):
            sent_addrs.append(addrinfo)
            pass
        self._notify._send_notify_message_udp = _fake_send_notify_message_udp
        self._notify.send_notify('example.net.')

        example_net_info = self._notify._notify_infos[('example.net.', 'IN')]
        example_net_info.create_socket('127.0.0.1')

        # A successful case: an expected notify response is received, and
        # another notify will be sent to the next slave immediately.
        example_net_info._sock.remote_end().send(
            get_notify_msgdata(Name('example.net')))
        self._notify._zone_notify_handler(example_net_info,
                                          notify_out._EVENT_READ)
        self.assertEqual(1, example_net_info.notify_try_num)
        expected_sent_addrs = [('192.0.2.1', 5353)]
        self.assertEqual(expected_sent_addrs, sent_addrs)
        self.assertEqual(('192.0.2.1', 5353), example_net_info._notify_current)

        # response's QID doesn't match.  the request will be resent.
        example_net_info._sock.remote_end().send(
            get_notify_msgdata(Name('example.net'), qid=1))
        self._notify._zone_notify_handler(example_net_info,
                                          notify_out._EVENT_READ)
        self.assertEqual(2, example_net_info.notify_try_num)
        expected_sent_addrs.append(('192.0.2.1', 5353))
        self.assertEqual(expected_sent_addrs, sent_addrs)
        self.assertEqual(('192.0.2.1', 5353), example_net_info._notify_current)

        # emulate exception from socket.recvfrom().  It will have the same
        # effect as a bad response.
        example_net_info._sock.set_raise_on_recv(True)
        example_net_info._sock.remote_end().send(
            get_notify_msgdata(Name('example.net')))
        self._notify._zone_notify_handler(example_net_info,
                                          notify_out._EVENT_READ)
        self.assertEqual(3, example_net_info.notify_try_num)
        expected_sent_addrs.append(('192.0.2.1', 5353))
        self.assertEqual(expected_sent_addrs, sent_addrs)
        self.assertEqual(('192.0.2.1', 5353), example_net_info._notify_current)

    def test_get_notify_slaves_from_ns(self):
        records = self._notify._get_notify_slaves_from_ns(Name('example.net.'),
                                                          RRClass.IN)
        self.assertEqual(6, len(records))
        self.assertEqual('8:8::8:8', records[5])
        self.assertEqual('7.7.7.7', records[4])
        self.assertEqual('6.6.6.6', records[3])
        self.assertEqual('5:5::5:5', records[2])
        self.assertEqual('4:4::4:4', records[1])
        self.assertEqual('3.3.3.3', records[0])

        records = self._notify._get_notify_slaves_from_ns(Name('example.com.'),
                                                          RRClass.IN)
        self.assertEqual(3, len(records))
        self.assertEqual('5:5::5:5', records[2])
        self.assertEqual('4:4::4:4', records[1])
        self.assertEqual('3.3.3.3', records[0])

    def test_get_notify_slaves_from_ns_unusual(self):
        self._notify._db_file = TESTDATA_SRCDIR + '/brokentest.sqlite3'
        self.assertEqual([], self._notify._get_notify_slaves_from_ns(
                Name('nons.example'), RRClass.IN))
        self.assertEqual([], self._notify._get_notify_slaves_from_ns(
                Name('nosoa.example'), RRClass.IN))
        self.assertEqual([], self._notify._get_notify_slaves_from_ns(
                Name('multisoa.example'), RRClass.IN))

        self.assertEqual([], self._notify._get_notify_slaves_from_ns(
                Name('nosuchzone.example'), RRClass.IN))

        # This will cause failure in getting access to the data source.
        self._notify._db_file = TESTDATA_SRCDIR + '/nodir/error.sqlite3'
        self.assertEqual([], self._notify._get_notify_slaves_from_ns(
                Name('example.com'), RRClass.IN))

    def test_init_notify_out(self):
        self._notify._init_notify_out(self._db_file)
        self.assertListEqual([('3.3.3.3', 53), ('4:4::4:4', 53), ('5:5::5:5', 53)],
                             self._notify._notify_infos[('example.com.', 'IN')].notify_slaves)

    def test_prepare_select_info(self):
        timeout, valid_fds, notifying_zones = self._notify._prepare_select_info()
        self.assertEqual(None, timeout)
        self.assertListEqual([], valid_fds)

        self._notify._notify_infos[('example.net.', 'IN')]._sock = 1
        self._notify._notify_infos[('example.net.', 'IN')].notify_timeout = time.time() + 5
        timeout, valid_fds, notifying_zones = self._notify._prepare_select_info()
        self.assertGreater(timeout, 0)
        self.assertListEqual([1], valid_fds)

        self._notify._notify_infos[('example.net.', 'IN')]._sock = 1
        self._notify._notify_infos[('example.net.', 'IN')].notify_timeout = time.time() - 5
        timeout, valid_fds, notifying_zones = self._notify._prepare_select_info()
        self.assertEqual(timeout, 0)
        self.assertListEqual([1], valid_fds)

        self._notify._notify_infos[('example.com.', 'IN')]._sock = 2
        self._notify._notify_infos[('example.com.', 'IN')].notify_timeout = time.time() + 5
        timeout, valid_fds, notifying_zones = self._notify._prepare_select_info()
        self.assertEqual(timeout, 0)
        self.assertEqual(len(valid_fds), 2)
        self.assertIn(1, valid_fds)
        self.assertIn(2, valid_fds)

    def test_shutdown(self):
        thread = self._notify.dispatcher()
        self.assertTrue(thread.is_alive())
        # nonblock_event won't be setted since there are no notifying zones.
        self.assertFalse(self._notify._nonblock_event.isSet())

        # set nonblock_event manually
        self._notify._nonblock_event.set()
        # nonblock_event will be cleared soon since there are no notifying zones.
        while (self._notify._nonblock_event.isSet()):
            pass

        # send notify
        example_net_info = self._notify._notify_infos[('example.net.', 'IN')]
        example_net_info.notify_slaves = [('127.0.0.1', 53)]
        example_net_info.create_socket('127.0.0.1')
        self._notify.send_notify('example.net')
        self.assertTrue(self._notify._nonblock_event.isSet())
        # set notify_try_num to _MAX_NOTIFY_TRY_NUM, zone 'example.net' will be removed
        # from notifying zones soon and nonblock_event will be cleared since there is no 
        # notifying zone left.
        example_net_info.notify_try_num = notify_out._MAX_NOTIFY_TRY_NUM
        while (self._notify._nonblock_event.isSet()):
            pass

        self.assertFalse(self._notify._nonblock_event.isSet())
        self._notify.shutdown()
        # nonblock_event should have been setted to stop waiting.
        self.assertTrue(self._notify._nonblock_event.isSet())
        self.assertFalse(thread.is_alive())

if __name__== "__main__":
    isc.log.init("bind10")
    isc.log.resetUnitTestRootLogger()
    unittest.main()
