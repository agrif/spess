import string
import typing

import humps

from spessgen.config import *
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
                elif arg.py_type != 'str':
                    val = f'str({val})'
                self.print(f'{arg.json_name!r}: {val},')
        self.print('},')

    def _collect_body(self, args: list[methods.Method.Argument] | methods.Method.Argument) -> None:
        if isinstance(args, list):
            return self._collect_args('body', args, json=True)
        self.print(f'body = to_json({args.py_name}),')

    def _resolve_type(self, method: methods.Method, arg: methods.Method.Argument) -> str:
        py_type = types.remove_prefix(arg.py_type, prefix=self.module)
        if arg.keyed:
            ktype = self.resolver.get(arg.keyed)
            if not ktype.keyed:
                raise RuntimeError(f'keyed method {method.py_name} uses unkeyed type {ktype.py_name}')
            kname = types.remove_prefix(ktype.keyed.name, prefix=self.module)
            return f'{py_type} | {kname}'
        return py_type

    def _resolve_return(self, method: methods.Method) -> str:
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

    def write_convenience_method(self, type: types.Type, method: methods.Method, banner: str | None = None) -> None:
        if not type.keyed:
            raise ValueError('convenience methods only work on keyed types')

        if banner:
            self.write_banner(banner)

        try:
            method_name = CONVENIENCE_METHOD_NAME[type.py_full_name][method.spec_name]
        except KeyError:
            method_name = method.py_name
            common = humps.decamelize(type.py_name)
            if method_name.endswith('_' + common):
                method_name = method_name[:-len(common) - 1]
            if method_name.startswith(common + '_'):
                method_name = method_name[len(common) + 1:]
            if method_name == common:
                method_name = 'update'

        # look for obvious collisions
        if isinstance(type.definition, types.Struct):
            if method_name in type.definition.fields:
                raise RuntimeError(f'convenience method {method_name} ({method.spec_name}) conflicts with field on {type.py_name}')
        elif isinstance(type.definition, types.Enum):
            if method_name in type.definition.variants:
                raise RuntimeError(f'convenience method {method_name} ({method.spec_name}) conflicts with variant on {type.py_name}')
        else:
            typing.assert_never(type.definition)

        method_args = []
        call_args = []
        return_type = self._resolve_return(method)

        used_self = False
        for arg in method.all_args:
            if arg.consolidated:
                continue
            ma = f'{arg.py_name}: {self._resolve_type(method, arg)}'
            ca = arg.py_name
            if arg.optional:
                ma += ' | None = None'
                ca += f'={arg.py_name}'

            if arg.keyed == type.py_full_name and not used_self:
                used_self = True
                if arg.optional:
                    call_args.append(f'{arg.py_name}=self.{type.keyed.local}')
                else:
                    call_args.append(f'self.{type.keyed.local}')
            else:
                method_args.append(ma)
                call_args.append(ca)

        method_args_rep = ''.join(', ' + ma for ma in method_args)
        call_args_rep = ', '.join(call_args)

        self.print()
        self.print(f'# spec_name: {method.spec_name}')
        with self.print(f'def {method_name}(self{method_args_rep}) -> {return_type}:'):
            self.doc_string(method.doc)
            self.print()
            self.print(f'return self._c.{method.py_name}({call_args_rep})')
