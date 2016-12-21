#!/usr/bin/env python
#
# Copyright 2012 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################

from SimpleXMLRPCServer import SimpleXMLRPCDispatcher
import array
import fcntl
import os
import pty
import signal
import select
import struct
import sys
import SocketServer
import termios
import threading
import time
import middlewared.logger

from setproctitle import setproctitle
import daemon

HERE = os.path.abspath(os.path.dirname(__file__))
sys.path.append(os.path.join(HERE, ".."))
sys.path.append(os.path.join(HERE, "../.."))
sys.path.append('/usr/local/www')
sys.path.append('/usr/local/www/freenasUI')

os.environ['DJANGO_SETTINGS_MODULE'] = 'freenasUI.settings'

log = middlewared.logger.Logger('tools.webshell')


class XMLRPCHandler(SocketServer.BaseRequestHandler):

    def handle(self):
        buff = ''
        while True:
            data = self.request.recv(1024)
            if not data:
                break
            buff += data

            fds = select.select([self.request], [], [], 0)
            if not fds[0]:
                break

        self.request.send(self.server.dispatcher._marshaled_dispatch(
            buff
        ))


def main_loop():
    setproctitle('webshelld')

    dispatcher = SimpleXMLRPCDispatcher()
    SOCKFILE = '/var/run/webshell.sock'
    if os.path.exists(SOCKFILE):
        os.unlink(SOCKFILE)
    server = SocketServer.UnixStreamServer(SOCKFILE, XMLRPCHandler)
    os.chmod(SOCKFILE, 0o700)
    dispatcher.register_instance(
        Multiplex("/usr/local/bin/bash", "xterm-color"))
    server.dispatcher = dispatcher
    server.serve_forever()


class PidFile(object):
    """
    Context manager that locks a pid file.
    Implemented as class not generator because daemon.py is calling __exit__
    with no parameters instead of the None, None, None specified by PEP-343.

    Based on:
    http://code.activestate.com/recipes/
    577911-context-manager-for-a-daemon-pid-file/
    """

    def __init__(self, path):
        self.path = path
        self.pidfile = None

    def __enter__(self):
        self.pidfile = open(self.path, "a+")
        self.pidfile.seek(0)
        try:
            pid = int(self.pidfile.read())
            os.kill(pid, 0)
            raise SystemExit("Already running according to " + self.path)
        except (OSError, ValueError):
            pass

        self.pidfile.seek(0)
        self.pidfile.truncate()
        self.pidfile.write(str(os.getpid()))
        self.pidfile.flush()
        self.pidfile.seek(0)
        return self.pidfile

    def __exit__(self, *args, **kwargs):
        try:
            if os.path.exists(self.path):
                os.unlink(self.path)
            self.pidfile.close()
        except IOError:
            pass


def main(argv):
    """Our friendly neighborhood main function."""
    pidfile = PidFile('/var/run/webshell.pid')

    context = daemon.DaemonContext(
        working_directory='/root',
        umask=0o002,
        pidfile=pidfile,
        stdout=sys.stdout,
        stdin=sys.stdin,
        stderr=sys.stderr,
    )

    with context:
        main_loop()


class Terminal:

    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.vt100_charset_graph = [
            0x25ca, 0x2026, 0x2022, 0x3f,
            0xb6, 0x3f, 0xb0, 0xb1,
            0x3f, 0x3f, 0x2b, 0x2b,
            0x2b, 0x2b, 0x2b, 0xaf,
            0x2014, 0x2014, 0x2014, 0x5f,
            0x2b, 0x2b, 0x2b, 0x2b,
            0x7c, 0x2264, 0x2265, 0xb6,
            0x2260, 0xa3, 0xb7, 0x7f
        ]
        self.vt100_esc = {
            '#8': self.esc_DECALN,
            '(A': self.esc_G0_0,
            '(B': self.esc_G0_1,
            '(0': self.esc_G0_2,
            '(1': self.esc_G0_3,
            '(2': self.esc_G0_4,
            ')A': self.esc_G1_0,
            ')B': self.esc_G1_1,
            ')0': self.esc_G1_2,
            ')1': self.esc_G1_3,
            ')2': self.esc_G1_4,
            '7': self.esc_DECSC,
            '8': self.esc_DECRC,
            '=': self.esc_DECKPAM,
            '>': self.esc_DECKPNM,
            'D': self.esc_IND,
            'E': self.esc_NEL,
            'H': self.esc_HTS,
            'M': self.esc_RI,
            'N': self.esc_SS2,
            'O': self.esc_SS3,
            'P': self.esc_DCS,
            'X': self.esc_SOS,
            'Z': self.esc_DECID,
            '[': self.esc_CSI,
            '\\': self.esc_ST,
            ']': self.esc_OSC,
            '^': self.esc_PM,
            '_': self.esc_APC,
            'c': self.reset_hard,
        }
        self.vt100_csi = {
            '@': self.csi_ICH,
            'A': self.csi_CUU,
            'B': self.csi_CUD,
            'C': self.csi_CUF,
            'D': self.csi_CUB,
            'E': self.csi_CNL,
            'F': self.csi_CPL,
            'G': self.csi_CHA,
            'H': self.csi_CUP,
            'I': self.csi_CHT,
            'J': self.csi_ED,
            'K': self.csi_EL,
            'L': self.csi_IL,
            'M': self.csi_DL,
            'P': self.csi_DCH,
            'S': self.csi_SU,
            'T': self.csi_SD,
            'W': self.csi_CTC,
            'X': self.csi_ECH,
            'Z': self.csi_CBT,
            '`': self.csi_HPA,
            'a': self.csi_HPR,
            'b': self.csi_REP,
            'c': self.csi_DA,
            'd': self.csi_VPA,
            'e': self.csi_VPR,
            'f': self.csi_HVP,
            'g': self.csi_TBC,
            'h': self.csi_SM,
            'l': self.csi_RM,
            'm': self.csi_SGR,
            'n': self.csi_DSR,
            'r': self.csi_DECSTBM,
            's': self.csi_SCP,
            'u': self.csi_RCP,
            'x': self.csi_DECREQTPARM,
            '!p': self.csi_DECSTR,
        }
        self.vt100_keyfilter_ansikeys = {
            '~': '~',
            'A': '\x1b[A',
            'B': '\x1b[B',
            'C': '\x1b[C',
            'D': '\x1b[D',
            'F': '\x1b[F',
            'H': '\x1b[H',
            '1': '\x1b[5~',
            '2': '\x1b[6~',
            '3': '\x1b[2~',
            '4': '\x1b[3~',
            'a': '\x1bOP',
            'b': '\x1bOQ',
            'c': '\x1bOR',
            'd': '\x1bOS',
            'e': '\x1b[15~',
            'f': '\x1b[17~',
            'g': '\x1b[18~',
            'h': '\x1b[19~',
            'i': '\x1b[20~',
            'j': '\x1b[21~',
            'k': '\x1b[23~',
            'l': '\x1b[24~',
        }
        self.vt100_keyfilter_appkeys = {
            '~': '~',
            'A': '\x1bOA',
            'B': '\x1bOB',
            'C': '\x1bOC',
            'D': '\x1bOD',
            'F': '\x1bOF',
            'H': '\x1bOH',
            '1': '\x1b[5~',
            '2': '\x1b[6~',
            '3': '\x1b[2~',
            '4': '\x1b[3~',
            'a': '\x1bOP',
            'b': '\x1bOQ',
            'c': '\x1bOR',
            'd': '\x1bOS',
            'e': '\x1b[15~',
            'f': '\x1b[17~',
            'g': '\x1b[18~',
            'h': '\x1b[19~',
            'i': '\x1b[20~',
            'j': '\x1b[21~',
            'k': '\x1b[23~',
            'l': '\x1b[24~',
        }
        self.reset_hard()

    # Reset functions
    def reset_hard(self):
        # Attribute mask: 0x0XFB0000
        #   X:  Bit 0 - Underlined
        #       Bit 1 - Negative
        #       Bit 2 - Concealed
        #   F:  Foreground
        #   B:  Background
        self.attr = 0x00fe0000
        # UTF-8 decoder
        self.utf8_units_count = 0
        self.utf8_units_received = 0
        self.utf8_char = 0
        # Key filter
        self.vt100_keyfilter_escape = False
        # Last char
        self.vt100_lastchar = 0
        # Control sequences
        self.vt100_parse_len = 0
        self.vt100_parse_state = ""
        self.vt100_parse_func = ""
        self.vt100_parse_param = ""
        # Buffers
        self.vt100_out = ""
        # Caches
        self.dump_cache = ""
        # Invoke other resets
        self.reset_screen()
        self.reset_soft()

    def reset_soft(self):
        """
        Attribute mask: 0x0XFB0000
          X:  Bit 0 - Underlined
              Bit 1 - Negative
              Bit 2 - Concealed
          F:  Foreground
          B:  Background
        """
        self.attr = 0x00fe0000
        # Scroll parameters
        self.scroll_area_y0 = 0
        self.scroll_area_y1 = self.h
        # Character sets
        self.vt100_charset_is_single_shift = False
        self.vt100_charset_is_graphical = False
        self.vt100_charset_g_sel = 0
        self.vt100_charset_g = [0, 0]
        # Modes
        self.vt100_mode_insert = False
        self.vt100_mode_lfnewline = False
        self.vt100_mode_cursorkey = False
        self.vt100_mode_column_switch = False
        self.vt100_mode_inverse = False
        self.vt100_mode_origin = False
        self.vt100_mode_autowrap = True
        self.vt100_mode_cursor = True
        self.vt100_mode_alt_screen = False
        self.vt100_mode_backspace = False
        # Init DECSC state
        self.esc_DECSC()
        self.vt100_saved2 = self.vt100_saved
        self.esc_DECSC()

    def reset_screen(self):
        # Screen
        self.screen = array.array('i', [self.attr | 0x20] * self.w * self.h)
        self.screen2 = array.array('i', [self.attr | 0x20] * self.w * self.h)
        # Scroll parameters
        self.scroll_area_y0 = 0
        self.scroll_area_y1 = self.h
        # Cursor position
        self.cx = 0
        self.cy = 0
        # Tab stops
        self.tab_stops = range(0, self.w, 8)

    # UTF-8 functions
    def utf8_decode(self, d):
        o = ''
        for c in d:
            char = ord(c)
            if self.utf8_units_count != self.utf8_units_received:
                self.utf8_units_received += 1
                if (char & 0xc0) == 0x80:
                    self.utf8_char = (self.utf8_char << 6) | (char & 0x3f)
                    if self.utf8_units_count == self.utf8_units_received:
                        if self.utf8_char < 0x10000:
                            o += unichr(self.utf8_char)
                        self.utf8_units_count = self.utf8_units_received = 0
                else:
                    o += '?'
                    while self.utf8_units_received:
                        o += '?'
                        self.utf8_units_received -= 1
                    self.utf8_units_count = 0
            else:
                if (char & 0x80) == 0x00:
                    o += c
                elif (char & 0xe0) == 0xc0:
                    self.utf8_units_count = 1
                    self.utf8_char = char & 0x1f
                elif (char & 0xf0) == 0xe0:
                    self.utf8_units_count = 2
                    self.utf8_char = char & 0x0f
                elif (char & 0xf8) == 0xf0:
                    self.utf8_units_count = 3
                    self.utf8_char = char & 0x07
                else:
                    o += '?'
        return o

    def utf8_charwidth(self, char):
        if char >= 0x2e80:
            return 2
        else:
            return 1

    # Low-level terminal functions
    def peek(self, y0, x0, y1, x1):
        return self.screen[self.w * y0 + x0:self.w * (y1 - 1) + x1]

    def poke(self, y, x, s):
        pos = self.w * y + x
        self.screen[pos:pos + len(s)] = s

    def fill(self, y0, x0, y1, x1, char):
        n = self.w * (y1 - y0 - 1) + (x1 - x0)
        self.poke(y0, x0, array.array('i', [char] * n))

    def clear(self, y0, x0, y1, x1):
        self.fill(y0, x0, y1, x1, self.attr | 0x20)

    # Scrolling functions
    def scroll_area_up(self, y0, y1, n=1):
        n = min(y1 - y0, n)
        self.poke(y0, 0, self.peek(y0 + n, 0, y1, self.w))
        self.clear(y1 - n, 0, y1, self.w)

    def scroll_area_down(self, y0, y1, n=1):
        n = min(y1 - y0, n)
        self.poke(y0 + n, 0, self.peek(y0, 0, y1 - n, self.w))
        self.clear(y0, 0, y0 + n, self.w)

    def scroll_area_set(self, y0, y1):
        y0 = max(0, min(self.h - 1, y0))
        y1 = max(1, min(self.h, y1))
        if y1 > y0:
            self.scroll_area_y0 = y0
            self.scroll_area_y1 = y1

    def scroll_line_right(self, y, x, n=1):
        if x < self.w:
            n = min(self.w - self.cx, n)
            self.poke(y, x + n, self.peek(y, x, y + 1, self.w - n))
            self.clear(y, x, y + 1, x + n)

    def scroll_line_left(self, y, x, n=1):
        if x < self.w:
            n = min(self.w - self.cx, n)
            self.poke(y, x, self.peek(y, x + n, y + 1, self.w))
            self.clear(y, self.w - n, y + 1, self.w)

    # Cursor functions
    def cursor_line_width(self, next_char):
        wx = self.utf8_charwidth(next_char)
        lx = 0
        for x in range(min(self.cx, self.w)):
            char = self.peek(self.cy, x, self.cy + 1, x + 1)[0] & 0xffff
            wx += self.utf8_charwidth(char)
            lx += 1
        return wx, lx

    def cursor_up(self, n=1):
        self.cy = max(self.scroll_area_y0, self.cy - n)

    def cursor_down(self, n=1):
        self.cy = min(self.scroll_area_y1 - 1, self.cy + n)

    def cursor_left(self, n=1):
        self.cx = max(0, self.cx - n)

    def cursor_right(self, n=1):
        self.cx = min(self.w - 1, self.cx + n)

    def cursor_set_x(self, x):
        self.cx = max(0, x)

    def cursor_set_y(self, y):
        self.cy = max(0, min(self.h - 1, y))

    def cursor_set(self, y, x):
        self.cursor_set_x(x)
        self.cursor_set_y(y)

    # Dumb terminal
    def ctrl_BS(self):
        delta_y, cx = divmod(self.cx - 1, self.w)
        cy = max(self.scroll_area_y0, self.cy + delta_y)
        self.cursor_set(cy, cx)

    def ctrl_HT(self, n=1):
        if n > 0 and self.cx >= self.w:
            return
        if n <= 0 and self.cx == 0:
            return
        ts = 0
        for i in range(len(self.tab_stops)):
            if self.cx >= self.tab_stops[i]:
                ts = i
        ts += n
        if ts < len(self.tab_stops) and ts >= 0:
            self.cursor_set_x(self.tab_stops[ts])
        else:
            self.cursor_set_x(self.w - 1)

    def ctrl_LF(self):
        if self.vt100_mode_lfnewline:
            self.ctrl_CR()
        if self.cy == self.scroll_area_y1 - 1:
            self.scroll_area_up(self.scroll_area_y0, self.scroll_area_y1)
        else:
            self.cursor_down()

    def ctrl_CR(self):
        self.cursor_set_x(0)

    def dumb_write(self, char):
        if char < 32:
            if char == 8:
                self.ctrl_BS()
            elif char == 9:
                self.ctrl_HT()
            elif char >= 10 and char <= 12:
                self.ctrl_LF()
            elif char == 13:
                self.ctrl_CR()
            return True
        return False

    def dumb_echo(self, char):
        # Check right bound
        wx, cx = self.cursor_line_width(char)
        # Newline
        if wx > self.w:
            if self.vt100_mode_autowrap:
                self.ctrl_CR()
                self.ctrl_LF()
            else:
                self.cx = cx - 1
        if self.vt100_mode_insert:
            self.scroll_line_right(self.cy, self.cx)
        if self.vt100_charset_is_single_shift:
            self.vt100_charset_is_single_shift = False
        elif self.vt100_charset_is_graphical and (char & 0xffe0) == 0x0060:
            char = self.vt100_charset_graph[char - 0x60]
        self.poke(self.cy, self.cx, array.array('i', [self.attr | char]))
        self.cursor_set_x(self.cx + 1)

    # VT100 CTRL, ESC, CSI handlers
    def vt100_charset_update(self):
        self.vt100_charset_is_graphical = (
            self.vt100_charset_g[self.vt100_charset_g_sel] == 2)

    def vt100_charset_set(self, g):
        # Invoke active character set
        self.vt100_charset_g_sel = g
        self.vt100_charset_update()

    def vt100_charset_select(self, g, charset):
        # Select charset
        self.vt100_charset_g[g] = charset
        self.vt100_charset_update()

    def vt100_setmode(self, p, state):
        # Set VT100 mode
        p = self.vt100_parse_params(p, [], False)
        for m in p:
            if m == '4':
                # Insertion replacement mode
                self.vt100_mode_insert = state
            elif m == '20':
                # Linefeed/new line mode
                self.vt100_mode_lfnewline = state
            elif m == '?1':
                # Cursor key mode
                self.vt100_mode_cursorkey = state
            elif m == '?3':
                # Column mode
                if self.vt100_mode_column_switch:
                    if state:
                        self.w = 132
                    else:
                        self.w = 80
                    self.reset_screen()
            elif m == '?5':
                # Screen mode
                self.vt100_mode_inverse = state
            elif m == '?6':
                # Region origin mode
                self.vt100_mode_origin = state
                if state:
                    self.cursor_set(self.scroll_area_y0, 0)
                else:
                    self.cursor_set(0, 0)
            elif m == '?7':
                # Autowrap mode
                self.vt100_mode_autowrap = state
            elif m == '?25':
                # Text cursor enable mode
                self.vt100_mode_cursor = state
            elif m == '?40':
                # Column switch control
                self.vt100_mode_column_switch = state
            elif m == '?47':
                # Alternate screen mode
                if ((state and not self.vt100_mode_alt_screen) or
                        (not state and self.vt100_mode_alt_screen)):
                    self.screen, self.screen2 = self.screen2, self.screen
                    self.vt100_saved, self.vt100_saved2 = self.vt100_saved2, \
                        self.vt100_saved
                self.vt100_mode_alt_screen = state
            elif m == '?67':
                # Backspace/delete
                self.vt100_mode_backspace = state

    def ctrl_SO(self):
        # Shift out
        self.vt100_charset_set(1)

    def ctrl_SI(self):
        # Shift in
        self.vt100_charset_set(0)

    def esc_CSI(self):
        # CSI start sequence
        self.vt100_parse_reset('csi')

    def esc_DECALN(self):
        # Screen alignment display
        self.fill(0, 0, self.h, self.w, 0x00fe0045)

    def esc_G0_0(self):
        self.vt100_charset_select(0, 0)

    def esc_G0_1(self):
        self.vt100_charset_select(0, 1)

    def esc_G0_2(self):
        self.vt100_charset_select(0, 2)

    def esc_G0_3(self):
        self.vt100_charset_select(0, 3)

    def esc_G0_4(self):
        self.vt100_charset_select(0, 4)

    def esc_G1_0(self):
        self.vt100_charset_select(1, 0)

    def esc_G1_1(self):
        self.vt100_charset_select(1, 1)

    def esc_G1_2(self):
        self.vt100_charset_select(1, 2)

    def esc_G1_3(self):
        self.vt100_charset_select(1, 3)

    def esc_G1_4(self):
        self.vt100_charset_select(1, 4)

    def esc_DECSC(self):
        # Store cursor
        self.vt100_saved = {}
        self.vt100_saved['cx'] = self.cx
        self.vt100_saved['cy'] = self.cy
        self.vt100_saved['attr'] = self.attr
        self.vt100_saved['charset_g_sel'] = self.vt100_charset_g_sel
        self.vt100_saved['charset_g'] = self.vt100_charset_g[:]
        self.vt100_saved['mode_autowrap'] = self.vt100_mode_autowrap
        self.vt100_saved['mode_origin'] = self.vt100_mode_origin

    def esc_DECRC(self):
        # Retore cursor
        self.cx = self.vt100_saved['cx']
        self.cy = self.vt100_saved['cy']
        self.attr = self.vt100_saved['attr']
        self.vt100_charset_g_sel = self.vt100_saved['charset_g_sel']
        self.vt100_charset_g = self.vt100_saved['charset_g'][:]
        self.vt100_charset_update()
        self.vt100_mode_autowrap = self.vt100_saved['mode_autowrap']
        self.vt100_mode_origin = self.vt100_saved['mode_origin']

    def esc_DECKPAM(self):
        # Application keypad mode
        pass

    def esc_DECKPNM(self):
        # Numeric keypad mode
        pass

    def esc_IND(self):
        # Index
        self.ctrl_LF()

    def esc_NEL(self):
        # Next line
        self.ctrl_CR()
        self.ctrl_LF()

    def esc_HTS(self):
        # Character tabulation set
        self.csi_CTC('0')

    def esc_RI(self):
        # Reverse line feed
        if self.cy == self.scroll_area_y0:
            self.scroll_area_down(self.scroll_area_y0, self.scroll_area_y1)
        else:
            self.cursor_up()

    def esc_SS2(self):
        # Single-shift two
        self.vt100_charset_is_single_shift = True

    def esc_SS3(self):
        # Single-shift three
        self.vt100_charset_is_single_shift = True

    def esc_DCS(self):
        # Device control string
        self.vt100_parse_reset('str')

    def esc_SOS(self):
        # Start of string
        self.vt100_parse_reset('str')

    def esc_DECID(self):
        # Identify terminal
        self.csi_DA('0')

    def esc_ST(self):
        # String terminator
        pass

    def esc_OSC(self):
        # Operating system command
        self.vt100_parse_reset('str')

    def esc_PM(self):
        # Privacy message
        self.vt100_parse_reset('str')

    def esc_APC(self):
        # Application program command
        self.vt100_parse_reset('str')

    def csi_ICH(self, p):
        # Insert character
        p = self.vt100_parse_params(p, [1])
        self.scroll_line_right(self.cy, self.cx, p[0])

    def csi_CUU(self, p):
        # Cursor up
        p = self.vt100_parse_params(p, [1])
        self.cursor_up(max(1, p[0]))

    def csi_CUD(self, p):
        # Cursor down
        p = self.vt100_parse_params(p, [1])
        self.cursor_down(max(1, p[0]))

    def csi_CUF(self, p):
        # Cursor right
        p = self.vt100_parse_params(p, [1])
        self.cursor_right(max(1, p[0]))

    def csi_CUB(self, p):
        # Cursor left
        p = self.vt100_parse_params(p, [1])
        self.cursor_left(max(1, p[0]))

    def csi_CNL(self, p):
        # Cursor next line
        self.csi_CUD(p)
        self.ctrl_CR()

    def csi_CPL(self, p):
        # Cursor preceding line
        self.csi_CUU(p)
        self.ctrl_CR()

    def csi_CHA(self, p):
        # Cursor character absolute
        p = self.vt100_parse_params(p, [1])
        self.cursor_set_x(p[0] - 1)

    def csi_CUP(self, p):
        # Set cursor position
        p = self.vt100_parse_params(p, [1, 1])
        if self.vt100_mode_origin:
            self.cursor_set(self.scroll_area_y0 + p[0] - 1, p[1] - 1)
        else:
            self.cursor_set(p[0] - 1, p[1] - 1)

    def csi_CHT(self, p):
        # Cursor forward tabulation
        p = self.vt100_parse_params(p, [1])
        self.ctrl_HT(max(1, p[0]))

    def csi_ED(self, p):
        # Erase in display
        p = self.vt100_parse_params(p, ['0'], False)
        if p[0] == '0':
            self.clear(self.cy, self.cx, self.h, self.w)
        elif p[0] == '1':
            self.clear(0, 0, self.cy + 1, self.cx + 1)
        elif p[0] == '2':
            self.clear(0, 0, self.h, self.w)

    def csi_EL(self, p):
        # Erase in line
        p = self.vt100_parse_params(p, ['0'], False)
        if p[0] == '0':
            self.clear(self.cy, self.cx, self.cy + 1, self.w)
        elif p[0] == '1':
            self.clear(self.cy, 0, self.cy + 1, self.cx + 1)
        elif p[0] == '2':
            self.clear(self.cy, 0, self.cy + 1, self.w)

    def csi_IL(self, p):
        # Insert line
        p = self.vt100_parse_params(p, [1])
        if (self.cy >= self.scroll_area_y0 and self.cy < self.scroll_area_y1):
            self.scroll_area_down(self.cy, self.scroll_area_y1, max(1, p[0]))

    def csi_DL(self, p):
        # Delete line
        p = self.vt100_parse_params(p, [1])
        if (self.cy >= self.scroll_area_y0 and self.cy < self.scroll_area_y1):
            self.scroll_area_up(self.cy, self.scroll_area_y1, max(1, p[0]))

    def csi_DCH(self, p):
        # Delete characters
        p = self.vt100_parse_params(p, [1])
        self.scroll_line_left(self.cy, self.cx, max(1, p[0]))

    def csi_SU(self, p):
        # Scroll up
        p = self.vt100_parse_params(p, [1])
        self.scroll_area_up(
            self.scroll_area_y0,
            self.scroll_area_y1,
            max(1, p[0]))

    def csi_SD(self, p):
        # Scroll down
        p = self.vt100_parse_params(p, [1])
        self.scroll_area_down(
            self.scroll_area_y0,
            self.scroll_area_y1,
            max(1, p[0]))

    def csi_CTC(self, p):
        # Cursor tabulation control
        p = self.vt100_parse_params(p, ['0'], False)
        for m in p:
            if m == '0':
                try:
                    self.tab_stops.index(self.cx)
                except ValueError:
                    tab_stops = self.tab_stops
                    tab_stops.append(self.cx)
                    tab_stops.sort()
                    self.tab_stops = tab_stops
            elif m == '2':
                try:
                    self.tab_stops.remove(self.cx)
                except ValueError:
                    pass
            elif m == '5':
                self.tab_stops = [0]

    def csi_ECH(self, p):
        # Erase character
        p = self.vt100_parse_params(p, [1])
        n = min(self.w - self.cx, max(1, p[0]))
        self.clear(self.cy, self.cx, self.cy + 1, self.cx + n)

    def csi_CBT(self, p):
        # Cursor backward tabulation
        p = self.vt100_parse_params(p, [1])
        self.ctrl_HT(1 - max(1, p[0]))

    def csi_HPA(self, p):
        # Character position absolute
        p = self.vt100_parse_params(p, [1])
        self.cursor_set_x(p[0] - 1)

    def csi_HPR(self, p):
        # Character position forward
        self.csi_CUF(p)

    def csi_REP(self, p):
        # Repeat
        p = self.vt100_parse_params(p, [1])
        if self.vt100_lastchar < 32:
            return
        n = min(2000, max(1, p[0]))
        while n:
            self.dumb_echo(self.vt100_lastchar)
            n -= 1
        self.vt100_lastchar = 0

    def csi_DA(self, p):
        # Device attributes
        p = self.vt100_parse_params(p, ['0'], False)
        if p[0] == '0':
            self.vt100_out = "\x1b[?1;2c"
        elif p[0] == '>0' or p[0] == '>':
            self.vt100_out = "\x1b[>0;184;0c"

    def csi_VPA(self, p):
        # Line position absolute
        p = self.vt100_parse_params(p, [1])
        self.cursor_set_y(p[0] - 1)

    def csi_VPR(self, p):
        # Line position forward
        self.csi_CUD(p)

    def csi_HVP(self, p):
        # Character and line position
        self.csi_CUP(p)

    def csi_TBC(self, p):
        # Tabulation clear
        p = self.vt100_parse_params(p, ['0'], False)
        if p[0] == '0':
            self.csi_CTC('2')
        elif p[0] == '3':
            self.csi_CTC('5')

    def csi_SM(self, p):
        # Set mode
        self.vt100_setmode(p, True)

    def csi_RM(self, p):
        # Reset mode
        self.vt100_setmode(p, False)

    def csi_SGR(self, p):
        # Select graphic rendition
        p = self.vt100_parse_params(p, [0])
        for m in p:
            if m == 0:
                # Reset
                self.attr = 0x00fe0000
            elif m == 4:
                # Underlined
                self.attr |= 0x01000000
            elif m == 7:
                # Negative
                self.attr |= 0x02000000
            elif m == 8:
                # Concealed
                self.attr |= 0x04000000
            elif m == 24:
                # Not underlined
                self.attr &= 0x7eff0000
            elif m == 27:
                # Positive
                self.attr &= 0x7dff0000
            elif m == 28:
                # Revealed
                self.attr &= 0x7bff0000
            elif m >= 30 and m <= 37:
                # Foreground
                self.attr = (self.attr & 0x7f0f0000) | ((m - 30) << 20)
            elif m == 39:
                # Default fg color
                self.attr = (self.attr & 0x7f0f0000) | 0x00f00000
            elif m >= 40 and m <= 47:
                # Background
                self.attr = (self.attr & 0x7ff00000) | ((m - 40) << 16)
            elif m == 49:
                # Default bg color
                self.attr = (self.attr & 0x7ff00000) | 0x000e0000

    def csi_DSR(self, p):
        # Device status report
        p = self.vt100_parse_params(p, ['0'], False)
        if p[0] == '5':
            self.vt100_out = "\x1b[0n"
        elif p[0] == '6':
            x = self.cx + 1
            y = self.cy + 1
            self.vt100_out = '\x1b[%d;%dR' % (y, x)
        elif p[0] == '7':
            self.vt100_out = 'WebShell'
        elif p[0] == '8':
            self.vt100_out = self.version
        elif p[0] == '?6':
            x = self.cx + 1
            y = self.cy + 1
            self.vt100_out = '\x1b[?%d;%dR' % (y, x)
        elif p[0] == '?15':
            self.vt100_out = '\x1b[?13n'
        elif p[0] == '?25':
            self.vt100_out = '\x1b[?20n'
        elif p[0] == '?26':
            self.vt100_out = '\x1b[?27;1n'
        elif p[0] == '?53':
            self.vt100_out = '\x1b[?53n'

    def csi_DECSTBM(self, p):
        # Set top and bottom margins
        p = self.vt100_parse_params(p, [1, self.h])
        self.scroll_area_set(p[0] - 1, p[1])
        if self.vt100_mode_origin:
            self.cursor_set(self.scroll_area_y0, 0)
        else:
            self.cursor_set(0, 0)

    def csi_SCP(self, p):
        # Save cursor position
        self.vt100_saved_cx = self.cx
        self.vt100_saved_cy = self.cy

    def csi_RCP(self, p):
        # Restore cursor position
        self.cx = self.vt100_saved_cx
        self.cy = self.vt100_saved_cy

    def csi_DECREQTPARM(self, p):
        # Request terminal parameters
        p = self.vt100_parse_params(p, [], False)
        if p[0] == '0':
            self.vt100_out = "\x1b[2;1;1;112;112;1;0x"
        elif p[0] == '1':
            self.vt100_out = "\x1b[3;1;1;112;112;1;0x"

    def csi_DECSTR(self, p):
        # Soft terminal reset
        self.reset_soft()

    # VT100 Parser
    def vt100_parse_params(self, p, d, to_int=True):
        # Process parameters (params p with defaults d)
        # Add prefix to all parameters
        prefix = ''
        if len(p) > 0:
            if p[0] >= '<' and p[0] <= '?':
                prefix = p[0]
                p = p[1:]
            p = p.split(';')
        else:
            p = ''
        # Process parameters
        n = max(len(p), len(d))
        o = []
        for i in range(n):
            value_def = False
            if i < len(p):
                value = prefix + p[i]
                value_def = True
                if to_int:
                    try:
                        value = int(value)
                    except ValueError:
                        value_def = False
            if (not value_def) and i < len(d):
                value = d[i]
            o.append(value)
        return o

    def vt100_parse_reset(self, vt100_parse_state=""):
        self.vt100_parse_state = vt100_parse_state
        self.vt100_parse_len = 0
        self.vt100_parse_func = ""
        self.vt100_parse_param = ""

    def vt100_parse_process(self):
        if self.vt100_parse_state == 'esc':
            # ESC mode
            f = self.vt100_parse_func
            try:
                self.vt100_esc[f]()
            except KeyError:
                pass
            if self.vt100_parse_state == 'esc':
                self.vt100_parse_reset()
        else:
            # CSI mode
            f = self.vt100_parse_func
            p = self.vt100_parse_param
            try:
                self.vt100_csi[f](p)
            except KeyError:
                pass
            if self.vt100_parse_state == 'csi':
                self.vt100_parse_reset()

    def vt100_write(self, char):
        if char < 32:
            if char == 27:
                self.vt100_parse_reset('esc')
                return True
            elif char == 14:
                self.ctrl_SO()
            elif char == 15:
                self.ctrl_SI()
        elif (char & 0xffe0) == 0x0080:
            self.vt100_parse_reset('esc')
            self.vt100_parse_func = chr(char - 0x40)
            self.vt100_parse_process()
            return True

        if self.vt100_parse_state:
            if self.vt100_parse_state == 'str':
                if char >= 32:
                    return True
                self.vt100_parse_reset()
            else:
                if char < 32:
                    if char == 24 or char == 26:
                        self.vt100_parse_reset()
                        return True
                else:
                    self.vt100_parse_len += 1
                    if self.vt100_parse_len > 32:
                        self.vt100_parse_reset()
                    else:
                        char_msb = char & 0xf0
                        if char_msb == 0x20:
                            # Intermediate bytes (added to function)
                            self.vt100_parse_func += unichr(char)
                        elif (char_msb == 0x30 and
                                self.vt100_parse_state == 'csi'):
                            # Parameter byte
                            self.vt100_parse_param += unichr(char)
                        else:
                            # Function byte
                            self.vt100_parse_func += unichr(char)
                            self.vt100_parse_process()
                        return True
        self.vt100_lastchar = char
        return False

    # External interface
    def set_size(self, w, h):
        if w < 2 or w > 256 or h < 2 or h > 256:
            return False
        self.w = w
        self.h = h
        self.vt100_parse_reset()
        self.reset_screen()
        return True

    def read(self):
        d = self.vt100_out
        self.vt100_out = ""
        return d

    def write(self, d):
        d = self.utf8_decode(d)
        for c in d:
            char = ord(c)
            if self.vt100_write(char):
                continue
            if self.dumb_write(char):
                continue
            if char <= 0xffff:
                self.dumb_echo(char)
        return True

    def pipe(self, d):
        o = ''
        for c in d:
            char = ord(c)
            if self.vt100_keyfilter_escape:
                self.vt100_keyfilter_escape = False
                try:
                    if self.vt100_mode_cursorkey:
                        o += self.vt100_keyfilter_appkeys[c]
                    else:
                        o += self.vt100_keyfilter_ansikeys[c]
                except KeyError:
                    pass
            elif c == '~':
                self.vt100_keyfilter_escape = True
            elif char == 127:
                if self.vt100_mode_backspace:
                    o += chr(8)
                else:
                    o += chr(127)
            else:
                o += c
                if self.vt100_mode_lfnewline and char == 13:
                    o += chr(10)
        return o

    def dump(self):
        dump = u""
        attr_ = -1
        cx, cy = min(self.cx, self.w - 1), self.cy
        for y in range(0, self.h):
            wx = 0
            for x in range(0, self.w):
                d = self.screen[y * self.w + x]
                char = d & 0xffff
                attr = d >> 16
                # Cursor
                if cy == y and cx == x and self.vt100_mode_cursor:
                    attr = attr & 0xfff0 | 0x000c
                # Attributes
                if attr != attr_:
                    if attr_ != -1:
                        dump += u'</span>'
                    bg = attr & 0x000f
                    fg = (attr & 0x00f0) >> 4
                    # Inverse
                    inv = attr & 0x0200
                    inv2 = self.vt100_mode_inverse
                    if (inv and not inv2) or (inv2 and not inv):
                        fg, bg = bg, fg
                    # Concealed
                    if attr & 0x0400:
                        fg = 0xc
                    # Underline
                    if attr & 0x0100:
                        ul = ' ul'
                    else:
                        ul = ''
                    dump += u'<span class="shell_f%x shell_b%x%s">' % (
                        fg,
                        bg,
                        ul)
                    attr_ = attr
                # Escape HTML characters
                if char == 38:
                    dump += '&amp;'
                elif char == 60:
                    dump += '&lt;'
                elif char == 62:
                    dump += '&gt;'
                else:
                    wx += self.utf8_charwidth(char)
                    if wx <= self.w:
                        dump += unichr(char)
            dump += "\n"
        # Encode in UTF-8
        dump = dump.encode('utf-8')
        dump += '</span>'
        # Cache dump
        if self.dump_cache == dump:
            return ''
        else:
            self.dump_cache = dump
            return '<c cy="%03d" />' % cy + dump


class SynchronizedMethod:

    def __init__(self, lock, orig):
        self.lock = lock
        self.orig = orig

    def __call__(self, *l):
        self.lock.acquire()
        try:
            r = self.orig(*l)
        finally:
            self.lock.release()
            pass
        return r


class Multiplex:

    def __init__(self, cmd=None, env_term=None):
        # Session
        self.session = {}
        self.cmd = cmd
        self.env_term = env_term
        # Synchronize methods
        self.lock = threading.RLock()
        for name in [
            'proc_keepalive',
            'proc_buryall',
            'proc_read',
            'proc_write',
            'proc_dump',
            'proc_getalive'
        ]:
            orig = getattr(self, name)
            setattr(self, name, SynchronizedMethod(self.lock, orig))
        # Supervisor thread
        self.signal_stop = 0
        self.thread = threading.Thread(target=self.proc_thread)
        self.thread.start()

    def stop(self):
        # Stop supervisor thread
        self.signal_stop = 1
        self.thread.join()

    def proc_keepalive(self, sid, jid, shell, w, h):
        if sid not in self.session:
            if not shell:
                shell = self.cmd
            # Start a new session
            self.session[sid] = {
                'jid': jid,
                'shell': shell,
                'state': 'unborn',
                'term': Terminal(w, h),
                'time': time.time(),
                'w': w,
                'h': h,
            }
            return self.proc_spawn(sid)
        elif self.session[sid]['state'] == 'alive':
            self.session[sid]['time'] = time.time()
            # Update terminal size
            if self.session[sid]['w'] != w or self.session[sid]['h'] != h:
                try:
                    fd = self.session[sid]['fd']
                    fcntl.ioctl(
                        fd,
                        termios.TIOCSWINSZ,
                        struct.pack("HHHH", h, w, 0, 0))
                except (IOError, OSError), e:
                    log.error(e)
                self.session[sid]['term'].set_size(w, h)
                self.session[sid]['w'] = w
                self.session[sid]['h'] = h
            return True
        else:
            return False

    def proc_spawn(self, sid):
        # Session
        self.session[sid]['state'] = 'alive'
        shell = self.session[sid]['shell']
        w, h = self.session[sid]['w'], self.session[sid]['h']
        # Fork new process
        try:
            pid, fd = pty.fork()
        except (IOError, OSError):
            self.session[sid]['state'] = 'dead'
            return False
        if pid == 0:

            try:
                ls = os.environ['LANG'].split('.')
            except KeyError:
                ls = []
            if len(ls) < 2:
                ls = ['en_US', 'UTF-8']
            try:
                env = {
                    'COLUMNS': str(w),
                    'LINES': str(h),
                    'TERM': self.env_term,
                    'PATH': (
                        '/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:'
                        '/usr/local/sbin'),
                    'LANG': ls[0] + '.UTF-8',
                    'HOME': '/root',
                    'SHELL': shell,
                }

                setproctitle(self.cmd)
                if self.session[sid]['jid']:
                    os.execve(
                        "/usr/sbin/jexec",
                        (
                            shell.split("/")[-1:] +
                            [self.session[sid]['jid'], shell]
                        ),
                        env
                    )
                else:
                    os.execve(shell, shell.split("/")[-1:], env)
            except Exception, e:
                log.error("Impossible to start a subshell (%r): %s", e, e)
            # self.proc_finish(sid)
            os._exit(0)
        else:
            # Store session vars
            self.session[sid]['pid'] = pid
            self.session[sid]['fd'] = fd
            # Set file control
            fcntl.fcntl(fd, fcntl.F_SETFL, os.O_NONBLOCK)
            # Set terminal size
            try:
                fcntl.ioctl(
                    fd,
                    termios.TIOCSWINSZ,
                    struct.pack("HHHH", h, w, 0, 0))
            except (IOError, OSError), e:
                log.error("Unable to issue ioctl for terminal size: %s", e)
            return True

    def proc_waitfordeath(self, sid):

        try:
            os.close(self.session[sid]['fd'])
        except (KeyError, IOError, OSError):
            pass
        if sid in self.session:
            if 'fd' in self.session[sid]:
                del self.session[sid]['fd']
        try:
            os.waitpid(self.session[sid]['pid'], 0)
        except (KeyError, IOError, OSError):
            pass
        if sid in self.session:
            if 'pid' in self.session[sid]:
                del self.session[sid]['pid']
        self.session[sid]['state'] = 'dead'
        return True

    def proc_bury(self, sid):
        if self.session[sid]['state'] == 'alive':
            try:
                os.kill(self.session[sid]['pid'], signal.SIGTERM)
            except (IOError, OSError):
                pass
        self.proc_waitfordeath(sid)
        if sid in self.session:
            del self.session[sid]
        return True

    def proc_buryall(self):
        for sid in self.session.keys():
            self.proc_bury(sid)

    # Read from process
    def proc_read(self, sid):
        if sid not in self.session:
            return False
        elif self.session[sid]['state'] != 'alive':
            return False
        try:
            fd = self.session[sid]['fd']
            d = os.read(fd, 65536)
            if not d:
                # Process finished, BSD
                self.proc_waitfordeath(sid)
                return False
        except (IOError, OSError):
            # Process finished, Linux
            self.proc_waitfordeath(sid)
            return False
        term = self.session[sid]['term']
        term.write(d)
        # Read terminal response
        d = term.read()
        if d:
            try:
                os.write(fd, d)
            except (IOError, OSError):
                return False
        return True

    # Write to process
    def proc_write(self, sid, d):
        d = d.data
        if sid not in self.session:
            return False
        elif self.session[sid]['state'] != 'alive':
            return False
        try:
            term = self.session[sid]['term']
            d = term.pipe(d)
            fd = self.session[sid]['fd']
            os.write(fd, d)
        except (IOError, OSError):
            return False
        return True

    # Dump terminal output
    def proc_dump(self, sid):
        if sid not in self.session:
            return False
        return self.session[sid]['term'].dump()

    # Get alive sessions, bury timed out ones
    def proc_getalive(self):
        fds = []
        fd2sid = {}
        now = time.time()
        for sid in self.session.keys():
            then = self.session[sid]['time']
            if (now - then) > 60:
                self.proc_bury(sid)
            else:
                if self.session[sid]['state'] == 'alive':
                    fds.append(self.session[sid]['fd'])
                    fd2sid[self.session[sid]['fd']] = sid
        return (fds, fd2sid)

    # Supervisor thread
    def proc_thread(self):
        while not self.signal_stop:
            # Read fds
            (fds, fd2sid) = self.proc_getalive()
            try:
                i, o, e = select.select(fds, [], [], 1.0)
            except (IOError, OSError):
                i = []
            for fd in i:
                sid = fd2sid[fd]
                self.proc_read(sid)
            if len(i):
                time.sleep(0.002)
        self.proc_buryall()

if __name__ == '__main__':
    main(sys.argv[1:])
