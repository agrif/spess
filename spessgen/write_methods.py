import string
import typing

import spessgen.methods as methods
import spessgen.types as types
import spessgen.writer as writer

class WriteMethods(writer.Writer):
    def __init__(self, converter: methods.Converter, module: str) -> None:
        super().__init__()
        self.spec = converter.spec
        self.resolver = converter.resolver
        self.converter = converter
        self.module = module

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
                elif arg.py_type.startswith('list['):
                    val = f"','.join(str(x) for x in {val})"
                    if arg.optional:
                        val += f' if {arg.py_name} is not None else None'
                elif arg.py_type != 'str':
                    val = f'str({val})'
                    if arg.optional:
                        val += f' if {arg.py_name} is not None else None'
                self.print(f'{arg.json_name!r}: {val},')
        self.print('},')

    def _collect_body(self, args: list[methods.Method.Argument] | methods.Method.Argument) -> None:
        if isinstance(args, list):
            return self._collect_args('body', args, json=True)
        self.print(f'body = to_json({args.py_name}),')

    def _resolve_type(self, method: methods.Method | methods.Convenience, arg: methods.Method.Argument | methods.Convenience.Argument) -> str:
        py_type = types.remove_prefix(arg.py_type, prefix=self.module)
        if arg.keyed:
            ktype = self.resolver.get(arg.keyed)
            if not ktype.keyed:
                raise RuntimeError(f'keyed method {method.py_name} uses unkeyed type {ktype.py_name}')
            kname = types.remove_prefix(ktype.keyed.name, prefix=self.module)
            return f'{py_type} | {kname}'
        return py_type

    def _resolve_return(self, method: methods.Method | methods.Convenience) -> str:
        result = types.remove_prefix(method.py_result, prefix=self.module)
        if method.paginated:
            return f'Paged[{result}]'
        return result

    def _cast_arg(self, method: methods.Method, arg: methods.Method.Argument) -> None:
        if arg.consolidated:
            self.print(f'{arg.py_name} = {arg.consolidated.convert}({arg.consolidated.src})')
        elif arg.keyed:
            self.print(f'{arg.py_name} = self._resolve({arg.keyed}, {arg.py_name})')

    def write_method(self, method: methods.Method, banner: str | None = None) -> None:
        self.write_banner(banner)

        method_args = ''
        for arg in method.all_args:
            if arg.consolidated:
                continue
            method_args += f', {arg.py_name}: {self._resolve_type(method, arg)}'
            if arg.optional:
                method_args += ' | None = None'

        return_type = self._resolve_return(method)
        call_method = '_call_paginated' if method.paginated else '_call'

        self.print()
        self.print(f'# spec_name: {method.spec_name}')
        with self.print(f'def {method.py_name}(self{method_args}) -> {return_type}:'):
            self.doc_string(method.doc)

            self.print()
            for arg in method.all_args:
                self._cast_arg(method, arg)
            if method.sync_code:
                self.print()
                with self.print(f'def _sync(r: {method.py_result}) -> {method.py_result}:'):
                    for sync_code in method.sync_code:
                        self.print(sync_code.format('r'))
                    self.print('return r')
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
                if method.sync_code:
                    self.print('sync = _sync,')
            self.print(')')

    def write_convenience_method(self, type: types.Type, conv: methods.Convenience, banner: str | None = None) -> None:
        self.write_banner(banner)

        method_args = []
        call_args = []
        return_type = self._resolve_return(conv)

        for arg in conv.args:
            if isinstance(arg, str):
                call_args.append(arg)
                continue

            ma = f'{arg.py_name}: {self._resolve_type(conv, arg)}'
            ca = arg.py_name
            if arg.optional:
                ma += ' | None = None'
                ca += f'={arg.py_name}'
            method_args.append(ma)
            call_args.append(ca)

        method_args_rep = ''.join(', ' + ma for ma in method_args)
        call_args_rep = ', '.join(call_args)

        self.print()
        if conv.spec_name:
            self.print(f'# spec_name: {conv.spec_name}')
        with self.print(f'def {conv.py_name}(self{method_args_rep}) -> {return_type}:'):
            self.doc_string(conv.doc, rest=conv.doc_rest)
            self.print()
            self.print(f'return {conv.py_impl}({call_args_rep})')
