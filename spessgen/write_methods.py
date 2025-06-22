import string
import typing

import spessgen.methods as methods
import spessgen.types as types
import spessgen.write_types as write_types

class WriteMethods(write_types.WriteTypes):
    def write_banner(self, banner: str | None):
        if banner:
            self.print()
            self.print('#')
            self.print(f'# {banner}')
            self.print('#')

    def _constrain_path(self, method: methods.Method) -> str:
        fmtpath = ''
        for lit, argname, spec, conv in string.Formatter().parse(method.path):
            if lit is not None:
                fmtpath += lit
            if argname is not None:
                if not any(p.json_name == argname for p in method.all_args):
                    raise RuntimeError(f'path format name {argname} not an argument in {method.spec_name}')
                fmtpath += f'{{{argname}:s}}'
        return fmtpath

    def _collect_args(self, var: str, args: list[methods.Method.Argument], json=False) -> None:
        if not args:
            return
        with self.print(f'{var} = {{'):
            for arg in args:
                val = arg.py_name
                if json:
                    val = f'to_json({val})'
                elif arg.py_type != 'str':
                    val = f'str({val})'
                self.print(f'{arg.json_name!r}: {val},')
        self.print('},')

    def _collect_body(self, args: list[methods.Method.Argument] | methods.Method.Argument) -> None:
        if isinstance(args, list):
            return self._collect_args('body', args, json=True)
        self.print(f'body = to_json({args.py_name}),')

    def write_method(self, method: methods.Method, banner: str | None = None) -> None:
        self.write_banner(banner)

        method_args = ''
        for arg in method.all_args:
            method_args += f', {arg.py_name}: {arg.py_type}'
            if arg.optional:
                method_args += ' | None = None'

        return_type = method.py_result
        call_method = '_call'
        if method.paginated:
            call_method = '_call_paginated'
            return_type = f'Paged[{return_type}]'

        self.print()
        with self.print(f'def {method.py_name}(self{method_args}) -> {return_type}:'):
            self.doc_string(method.doc)

            self.print()
            with self.print(f'return self.{call_method}('):
                self.print(f'{method.py_result},')
                self.print(f'{method.method.value!r},')
                self.print(f'{self._constrain_path(method)!r},')
                self._collect_args('path_args', method.path_args)
                self._collect_args('query_args', method.query_args)
                self._collect_body(method.body_args)
                if method.adhoc:
                    self.print('adhoc = True,')
            self.print(')')
