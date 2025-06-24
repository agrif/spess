import typing

import spessgen.methods as methods
import spessgen.types as types
import spessgen.write_methods as write_methods

KEY_TYPE_DOCS = ' '.join([
    'This abstract class represents all objects that unambiguously refer',
    'to a single :class:`.{type.py_name}`. Any type that has the',
    '``{type.keyed.foreign}`` attribute is accepted as a valid',
    '``{type.keyed.name}``.',
])

WAIT_DOCS = ' '.join([
    'Wait interactively until this object is ready for more actions.',
    'For a non-interactive, async wait, await this object directly.',
])

AWAIT_DOCS = ' '.join([
    'Wait asynchronously until this object is ready for more actions.',
    'For an interactive, blocking wait, see :func:`wait`.',
])

class WriteTypes(write_methods.WriteMethods):
    def write_types(self, iter_types: types.Resolver.IterTypes) -> None:
        for type, children in iter_types:
            self.write_type(type, children)

    def write_type(self, type: types.Type, children: types.Resolver.IterTypes) -> None:
        self._write_key_class(type)
        self.print()
        self.print(f'# spec_name: {type.spec_name}')
        if isinstance(type.definition, types.Struct):
            self._write_struct(type, type.definition, children)
        elif isinstance(type.definition, types.Enum):
            self._write_enum(type, type.definition, children)
        else:
            typing.assert_never(type.definition)

    def _write_key_class(self, type: types.Type) -> None:
        if type.keyed:
            self.print()
            with self.print(f'class {type.keyed.name}(typing.Protocol):'):
                self.doc_string(KEY_TYPE_DOCS.format(type=type), rest=True)
                self.print('@property')
                self.print(f'def {type.keyed.foreign}(self) -> str: ...')

    def _write_key_var(self, type: types.Type) -> None:
        if type.keyed:
            self.print()
            self.print(f'_class_key: typing.ClassVar[str] = {type.keyed.foreign!r}')

    def _write_properties(self, type: types.Type) -> None:
        for k, v in type.properties.items():
            self.print()
            self.print('@property')
            with self.print(f'def {k}(self) -> str:'):
                self.doc_string(f'Alias for `{v}`.')
                self.print(f'return {v}')

    def _write_top(self, type: types.Type, children: types.Resolver.IterTypes) -> None:
        self.doc_string(type.doc)
        self._write_key_var(type)
        self.write_types(children)

    def _write_bottom(self, type: types.Type) -> None:
        self._write_properties(type)
        self._write_wait(type)
        self._write_convenience_methods(type)

    def _write_convenience_methods(self, type: types.Type) -> None:
        # convenience methods are anything with arguments keyed to us
        if not type.keyed:
            return

        def is_ours(method: methods.Method) -> bool:
            for arg in method.all_args:
                if arg.consolidated:
                    continue
                if arg.keyed == type.py_full_name:
                    return True
                # only check the first argument
                break
            return False

        for method, banner in self.converter.iter_methods(is_ours):
            self.write_convenience_method(type, method, banner=banner)

    def _write_wait(self, type: types.Type) -> None:
        if not type.wait:
            return

        self.print()
        with self.print("def wait(self, message: str = 'waiting') -> None:"):
            self.doc_string(WAIT_DOCS, rest=True)
            self.print()
            with self.print('backend._wait(message, ['):
                for wait in type.wait:
                    self.print(f'{wait},')
            self.print('])')

        self.print()
        with self.print("def __await__(self) -> typing.Awaitable[None]:"):
            self.doc_string(AWAIT_DOCS, rest=True)
            self.print()
            with self.print('return backend._await(['):
                for wait in type.wait:
                    self.print(f'{wait},')
            self.print('])')

    def _write_struct(self, type: types.Type, struct: types.Struct, children: types.Resolver.IterTypes) -> None:
        dataclass_args: dict[str, typing.Any] = {}
        base_classes = []
        if type.keyed:
            base_classes.append('Keyed')
            dataclass_args['eq'] = False

        base = ''
        if base_classes:
            base = f'({", ".join(base_classes)})'
        dataclass = ''
        if dataclass_args:
            dataclass = f'({", ".join(f"{k}={v!r}" for k, v in dataclass_args.items())})'

        self.print(f'@dataclasses.dataclass{dataclass}')
        with self.print(f'class {type.py_name}{base}:'):
            if not type.doc:
                # dataclass adds a docstring that is very noisy in real docs
                # it's not enough to set this to None or empty string
                self.print("__doc__ = ' '")
                self.print()

            self._write_top(type, children)
            self.print()
            for field in struct.fields.values():
                self._write_struct_field(field)
            self._write_struct_json(struct.fields)
            self._write_bottom(type)

    def _write_struct_field(self, field: types.Struct.Field) -> None:
        self.doc_comment(field.doc)
        if field.optional:
            self.print(f'{field.py_name}: {field.py_type} | None = None')
        else:
            self.print(f'{field.py_name}: {field.py_type}')

    def _write_struct_json(self, fields: dict[str, types.Struct.Field]) -> None:
        self.print()
        with self.print('def to_json(self) -> Json:'):
            with self.print('v = {'):
                for field in (f for f in fields.values() if not f.optional):
                    self.print(f'{field.json_name!r}: to_json(self.{field.py_name}),')
            self.print('}')
            for field in (f for f in fields.values() if f.optional):
                with self.print(f'if self.{field.py_name} is not None:'):
                    self.print(f'v[{field.json_name!r}] = to_json(self.{field.py_name})')
            self.print('return v')

        self.print()
        self.print('@classmethod')
        with self.print('def from_json(cls, v: Json) -> typing.Self:'):
            with self.print('if not isinstance(v, dict):'):
                self.print('raise TypeError(type(v))')
            with self.print('return cls('):
                for field in fields.values():
                    converted = f'v[{field.json_name!r}]'
                    if field.py_type != 'Json':
                        converted = f'from_json({field.py_type}, {converted})'
                    if field.optional:
                        self.print(f'{field.py_name} = {converted} if {field.json_name!r} in v else None,')
                    else:
                        self.print(f'{field.py_name} = {converted},')
            self.print(')')

    def _write_enum(self, type: types.Type, enum: types.Enum, children: types.Resolver.IterTypes) -> None:
        with self.print(f'class {type.py_name}(Enum):'):
            self._write_top(type, children)
            self.print()
            for py_name, json_name in enum.variants.items():
                self.print(f'{py_name} = {json_name!r}')
            self._write_bottom(type)
