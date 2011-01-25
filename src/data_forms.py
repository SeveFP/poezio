# Copyright 2010-2011 Le Coz Florent <louiz@louiz.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# Poezio is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Poezio.  If not, see <http://www.gnu.org/licenses/>.

"""
Defines the data-forms Tab and all the Windows for it.
"""

import logging
log = logging.getLogger(__name__)
import curses

from windows import g_lock
import windows
from tabs import Tab

class DataFormsTab(Tab):
    """
    A tab contaning various window type, displaying
    a form that the user needs to fill.
    """
    def __init__(self, core, form, on_cancel, on_send, kwargs):
        Tab.__init__(self, core)
        self._form = form
        self._on_cancel = on_cancel
        self._on_send = on_send
        self._kwargs = kwargs
        for field in self._form:
            self.fields.append(field)
        self.topic_win = windows.Topic()
        self.tab_win = windows.GlobalInfoBar()
        self.form_win = FormWin(form, self.height-3, self.width, 1, 0)
        self.help_win = windows.HelpText("Ctrl+Y: send form, Ctrl+G: cancel")
        self.key_func['KEY_UP'] = self.form_win.go_to_previous_input
        self.key_func['KEY_DOWN'] = self.form_win.go_to_next_input
        self.key_func['^G'] = self.on_cancel
        self.key_func['^Y'] = self.on_send
        self.resize()

    def on_cancel(self):
        self._on_cancel(self._form)

    def on_send(self):
        self._form.reply()
        self.form_win.reply()
        self._on_send(self._form)

    def on_input(self, key):
        if key in self.key_func:
            return self.key_func[key]()
        self.form_win.on_input(key)

    def resize(self):
        Tab.resize(self)
        self.topic_win.resize(1, self.width, 0, 0, self.core.stdscr)
        self.tab_win.resize(1, self.width, self.height-2, 0, self.core.stdscr)
        self.form_win.resize(self.height-3, self.width, 1, 0)
        self.help_win.resize(1, self.width, self.height-1, 0, None)
        self.lines = []

    def refresh(self, tabs, informations, _):
        self.topic_win.refresh(self._form['title'])
        self.tab_win.refresh(tabs, tabs[0])
        self.help_win.refresh()
        self.form_win.refresh()

class FieldInput(object):
    """
    All input type in a data form should inherite this class,
    in addition with windows.Input or any relevant class from the
    'windows' library.
    """
    def __init__(self, field):
        self._field = field
        self.color = 14

    def set_color(self, color):
        self.color = color
        self.refresh()

    def update_field_value(self, value):
        raise NotImplementedError

    def resize(self, height, width, y, x):
        self._resize(height, width, y, x, None)

    def is_dummy(self):
        return False

    def reply(self):
        """
        Set the correct response value in the field
        """
        raise NotImplementedError

class DummyInput(FieldInput, windows.Win):
    def __init__(self, field):
        FieldInput.__init__(self, field)
        windows.Win.__init__(self)

    def do_command(self):
        return

    def refresh(self):
        return

    def is_dummy(self):
        return True

class BooleanWin(FieldInput, windows.Win):
    def __init__(self, field):
        FieldInput.__init__(self, field)
        windows.Win.__init__(self)
        self.last_key = 'KEY_RIGHT'
        self.value = bool(field.getValue())

    def do_command(self, key):
        if key == 'KEY_LEFT' or key == 'KEY_RIGHT':
            self.value = not self.value
            self.last_key = key
        self.refresh()

    def refresh(self):
        with g_lock:
            self._win.attron(curses.color_pair(self.color))
            self.addnstr(0, 0, ' '*(8), self.width)
            self.addstr(0, 2, "%s"%self.value)
            self.addstr(0, 8, '→')
            self.addstr(0, 0, '←')
            if self.last_key == 'KEY_RIGHT':
                self.addstr(0, 8, '')
            else:
                self.addstr(0, 0, '')
            self._win.attroff(curses.color_pair(self.color))
            self._refresh()

    def reply(self):
        self._field['label'] = ''
        self._field.setAnswer(self.value)

class ListMultiWin(FieldInput, windows.Win):
    def __init__(self, field):
        FieldInput.__init__(self, field)
        windows.Win.__init__(self)
        values = field.getValue()
        self.options = [[option, True if option['value'] in values else False]\
                            for option in field.getOptions()]
        self.val_pos = 0

    def do_command(self, key):
        if key == 'KEY_LEFT':
            if self.val_pos > 0:
                self.val_pos -= 1
        elif key == 'KEY_RIGHT':
            if self.val_pos < len(self.options)-1:
                self.val_pos += 1
        elif key == ' ':
            self.options[self.val_pos][1] = not self.options[self.val_pos][1]
        else:
            return
        self.refresh()

    def refresh(self):
        with g_lock:
            self._win.attron(curses.color_pair(self.color))
            self.addnstr(0, 0, ' '*self.width, self.width)
            if self.val_pos > 0:
                self.addstr(0, 0, '←')
            if self.val_pos < len(self.options)-1:
                self.addstr(0, self.width-1, '→')
            option = self.options[self.val_pos]
            self.addstr(0, self.width//2-len(option)//2, option[0]['label'])
            self.addstr(0, 2, '✔' if option[1] else '☐')
            self._win.attroff(curses.color_pair(self.color))
            self._refresh()

    def reply(self):
        self._field['label'] = ''
        self._field.delOptions()
        values = [option[0]['value'] for option in self.options if option[1] is True]
        self._field.setAnswer(values)

class ListSingleWin(FieldInput, windows.Win):
    def __init__(self, field):
        FieldInput.__init__(self, field)
        windows.Win.__init__(self)
        # the option list never changes
        self.options = field.getOptions()
        # val_pos is the position of the currently selected option
        self.val_pos = 0
        for i, option in enumerate(self.options):
            if field.getValue() == option['value']:
                self.val_pos = i

    def do_command(self, key):
        if key == 'KEY_LEFT':
            if self.val_pos > 0:
                self.val_pos -= 1
        elif key == 'KEY_RIGHT':
            if self.val_pos < len(self.options)-1:
                self.val_pos += 1
        else:
            return
        self.refresh()

    def refresh(self):
        with g_lock:
            self._win.attron(curses.color_pair(self.color))
            self.addnstr(0, 0, ' '*self.width, self.width)
            if self.val_pos > 0:
                self.addstr(0, 0, '←')
            if self.val_pos < len(self.options)-1:
                self.addstr(0, self.width-1, '→')
            option = self.options[self.val_pos]['label']
            self.addstr(0, self.width//2-len(option)//2, option)
            self._win.attroff(curses.color_pair(self.color))
            self._refresh()

    def reply(self):
        self._field['label'] = ''
        self._field.delOptions()
        self._field.setAnswer(self.options[self.val_pos]['value'])

class TextSingleWin(FieldInput, windows.Input):
    def __init__(self, field):
        FieldInput.__init__(self, field)
        windows.Input.__init__(self)
        self.text = field.getValue() if isinstance(field.getValue(), str)\
            else ""
        self.pos = len(self.text)
        self.color = 14

    def reply(self):
        self._field['label'] = ''
        self._field.setAnswer(self.get_text())

class TextPrivateWin(TextSingleWin):
    def __init__(self, field):
        TextSingleWin.__init__(self, field)

    def rewrite_text(self):
        with g_lock:
            self._win.erase()
            if self.color:
                self._win.attron(curses.color_pair(self.color))
            self.addstr('*'*len(self.text[self.line_pos:self.line_pos+self.width-1]))
            if self.color:
                (y, x) = self._win.getyx()
                size = self.width-x
                self.addnstr(' '*size, size, curses.color_pair(self.color))
            self.addstr(0, self.pos, '')
            if self.color:
                self._win.attroff(curses.color_pair(self.color))
            self._refresh()

class FormWin(object):
    """
    A window, with some subwins (the various inputs).
    On init, create all the subwins.
    On resize, move and resize all the subwin and define how the text will be written
    On refresh, write all the text, and refresh all the subwins
    """
    input_classes = {'boolean': BooleanWin,
                     'fixed': DummyInput,
                     # jid-multi
                     'jid-single': TextSingleWin,
                     'list-multi': ListMultiWin,
                     'list-single': ListSingleWin,
                     # text-multi
                     'text-private': TextPrivateWin,
                     'text-single': TextSingleWin,
                     }
    def __init__(self, form, height, width, y, x):
        self._form = form
        self._win = curses.newwin(height, width, y, x)
        self.current_input = 0
        self.inputs = []        # dict list
        for (name, field) in self._form.getFields():
            if field['type'] == 'hidden':
                continue
            try:
                input_class = self.input_classes[field['type']]
            except:
                field.setValue(field['type'])
                input_class = TextSingleWin
            instructions = field['instructions']
            label = field['label']
            if field['type'] == 'fixed':
                label = field.getValue()
            inp = input_class(field)
            self.inputs.append({'label':label,
                                'instructions':instructions,
                                'input':inp})

    def resize(self, height, width, y, x):
        self._win.resize(height, width)
        self.height = height
        self.width = width

    def reply(self):
        """
        Set the response values in the form, for each field
        from the corresponding input
        """
        for inp in self.inputs:
            if inp['input'].is_dummy():
                continue
            else:
                inp['input'].reply()
        self._form['title'] = ''
        self._form['instructions'] = ''

    def go_to_next_input(self):
        if not self.inputs:
            return
        if self.current_input == len(self.inputs) - 1:
            return
        self.inputs[self.current_input]['input'].set_color(14)
        self.current_input += 1
        jump = 0
        while self.current_input+jump != len(self.inputs) - 1 and self.inputs[self.current_input+jump]['input'].is_dummy():
            jump += 1
        if self.inputs[self.current_input+jump]['input'].is_dummy():
            return
        self.current_input += jump
        self.inputs[self.current_input]['input'].set_color(13)

    def go_to_previous_input(self):
        if not self.inputs:
            return
        if self.current_input == 0:
            return
        self.inputs[self.current_input]['input'].set_color(14)
        self.current_input -= 1
        jump = 0
        while self.current_input-jump > 0 and self.inputs[self.current_input+jump]['input'].is_dummy():
            jump += 1
        if self.inputs[self.current_input+jump]['input'].is_dummy():
            return
        self.current_input -= jump
        self.inputs[self.current_input]['input'].set_color(13)

    def on_input(self, key):
        if not self.inputs:
            return
        self.inputs[self.current_input]['input'].do_command(key)

    def refresh(self):
        with g_lock:
            self._win.erase()
            y = 0
            i = 0
            for name, field in self._form.getFields():
                if field['type'] == 'hidden':
                    continue
                label = self.inputs[i]['label']
                self._win.addstr(y, 0, label)
                self.inputs[i]['input'].resize(1, self.width//3, y+1, 2*self.width//3)
                if field['instructions']:
                    y += 1
                    self._win.addstr(y, 0, field['instructions'])
                y += 1
                i += 1
            self._win.refresh()
        for inp in self.inputs:
            inp['input'].refresh()
        self.inputs[self.current_input]['input'].set_color(13)
        self.inputs[self.current_input]['input'].refresh()
