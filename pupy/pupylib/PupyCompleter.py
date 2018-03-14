# -*- coding: utf-8 -*-
# --------------------------------------------------------------
# Copyright (c) 2015, Nicolas VERDIER (contact@n1nj4.eu)
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE
# --------------------------------------------------------------

import sys
import os
import os.path
import shlex
import re

from argparse import REMAINDER

from .PupyErrors import PupyModuleExit, PupyModuleUsageError

def list_completer(l):
    def func(text, line, begidx, endidx, context):
        return [x+" " for x in l if x.startswith(text)]
    return func

def void_completer(text, line, begidx, endidx, context):
    return []

def path_completer(text, line, begidx, endidx, context):
    l=[]
    if not text:
        l=os.listdir(".")
    else:
        try:
            dirname=os.path.dirname(text)
            if not dirname:
                dirname="."
            basename=os.path.basename(text)
            for f in os.listdir(dirname):
                if f.startswith(basename):
                    if os.path.isdir(os.path.join(dirname,f)):
                        l.append(os.path.join(dirname,f)+os.sep)
                    else:
                        l.append(os.path.join(dirname,f)+" ")
        except Exception as e:
            pass
    return l

def module_name_completer(text, line, begidx, endidx, context):
    modules = (
        x.get_name() for x in context.server.iter_modules(
        by_clients=True,
        clients_filter=context.handler.default_filter)
    )

    return [
        module for module in modules if module.startswith(text) or not(text)
    ]

def module_args_completer(text, line, begidx, endidx, context):
    module_name = context.parsed.module
    try:
        module = context.server.get_module(module_name)
    except ValueError:
        return []

    args = shlex.split(line)

    completer = module.arg_parser.get_completer()
    context.parsed.module = module
    context.parsed.args = args

    line = text
    text = text
    begindex = 0
    endindex = len(text)

    return completer.complete(text, line, begidx, endidx, context)


class CompletionContext(object):

    __slots__ = (
        'server', 'handler', 'config', 'parsed'
    )

    def __init__(self, server, handler, config, parsed=None):
        self.server = server
        self.handler = handler
        self.config = config
        self.parsed = parsed

class PupyModCompleter(object):
    def __init__(self, parser):
        self.conf = {
            "positional_args":[],
            "optional_args":[],
        }
        self.parser = parser

    def add_positional_arg(self, names, **kwargs):
        """ names can be a string or a list to pass args aliases at once """
        if not type(names) is list and not type(names) is tuple:
            names = [names]
        for name in names:
            self.conf['positional_args'].append((name, kwargs))

    def add_optional_arg(self, names, **kwargs):
        """ names can be a string or a list to pass args aliases at once """
        if not type(names) is list and not type(names) is tuple:
            names=[names]
        for name in names:
            self.conf['optional_args'].append((name, kwargs))

    def get_optional_nargs(self, name):
        for n, kwargs in self.conf['optional_args']:
            if name == n:
                if 'action' in kwargs:
                    action = kwargs['action']
                    if action in ('store_true', 'store_false'):
                        return 0
                break

        return 1

    def get_optional_args(self, nargs=None):
        if nargs is None:
            return [
                x[0] for x in self.conf['optional_args']
            ]
        else:
            return [
                x[0] for x in self.conf['optional_args'] \
                if self.get_optional_nargs(x[0]) == nargs
            ]

    def get_last_text(self, text, line, begidx, endidx, context):
        try:
            return line[0:begidx-1].rsplit(' ',1)[1].strip()
        except Exception:
            return None

    def get_positional_arg_index(self, text, tab, begidx, endidx, context):
        posmax = len(self.conf['positional_args'])

        if not tab:
            return 0, False

        elif not self.conf['positional_args']:
            return 0, False

        elif posmax < 2:
            return 0, False

        opt0 = self.get_optional_args(nargs=0)
        opt1 = self.get_optional_args(nargs=1)
        ltab = len(tab)

        i = 0
        omit = 0

        for i in xrange(0, ltab):
            if i >= omit:
                if i-omit >= posmax:
                    return posmax, True

                name, kwargs = self.conf['positional_args'][i-omit]
                if 'nargs' in kwargs and kwargs['nargs'] == REMAINDER:
                    return i - omit, True

            if tab[i] in opt0 or ( i == ltab-1 and any(opt.startswith(tab[i]) for opt in opt0)):
                omit += 1

            elif tab[i] in opt1 or ( i == ltab-1 and any(opt.startswith(tab[i]) for opt in opt1)):
                omit += 1

            elif i > 1 and tab[i-1] in opt1:
                omit += 1

        if not text:
            i += 1

        if i < omit:
            return 0, False

        pos = i - omit
        remainder = False

        name, kwargs = self.conf['positional_args'][pos]
        if 'nargs' in kwargs and kwargs['nargs'] == REMAINDER:
            remainder = True

        return pos, remainder

    def get_optional_args_completer(self, name):
        return [
            x[1]["completer"] for x in self.conf["optional_args"] if x[0]==name
        ][0]

    def get_positional_args_completer(self, index):
        if index < len(self.conf['positional_args']):
            return self.conf['positional_args'][index][1]['completer']

    def complete(self, text, line, begidx, endidx, context):
        last_text = self.get_last_text(text, line, begidx, endidx, context)

        if last_text in self.get_optional_args(nargs=1):
            completer = self.get_optional_args_completer(last_text)
            return completer(text, line, begidx, endidx, context)

        positional_index, remainder = self.get_positional_arg_index(
            text, context.parsed.args, begidx, endidx, context)

        if text.startswith('-') and not remainder:
            return [
                x+' ' for x in self.get_optional_args() if x.startswith(text)
            ]
        else:
            completer = self.get_positional_args_completer(positional_index)
            if not completer:
                return None

            if context and context.parsed and context.parsed.args:
                try:
                    parsed, rest = self.parser.parse_known_args(context.parsed.args)
                    context.parsed = parsed
                    context.parsed.args = rest
                except (PupyModuleUsageError, PupyModuleExit):
                    pass

            return completer(text, line, begidx, endidx, context)
