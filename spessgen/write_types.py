import typing

import spessgen.methods as methods
import spessgen.types as types
import spessgen.writer as writer

class WriteTypes(writer.Writer):
    def __init__(self, converter: methods.Converter) -> None:
        super().__init__()
        self.spec = converter.spec
        self.resolver = converter.resolver
        self.converter = converter

    def write_types(self, iter_types: types.Resolver.IterTypes) -> None:
        for type, children in iter_types:
            self.write_type(type, children)

    def write_type(self, type: types.Type, children: types.Resolver.IterTypes) -> None:
        self.print()
        self.print(f'# spec_name: {type.spec_name}')
        if isinstance(type.definition, types.Struct):
            self._write_struct(type, type.definition, children)
        elif isinstance(type.definition, types.Enum):
            self._write_enum(type, type.definition, children)
        else:
            typing.assert_never(type.definition)

    def _write_struct(self, type: types.Type, struct: types.Struct, children: types.Resolver.IterTypes) -> None:
        self.print('@dataclasses.dataclass')
        with self.print(f'class {type.py_name}:'):
            self.doc_string(type.doc)
            self.write_types(children)
            self.print()
            for field in struct.fields.values():
                self._write_struct_field(field)
            self._write_struct_json(struct.fields)

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
            self.doc_string(type.doc)
            self.write_types(children)
            self.print()
            for py_name, json_name in enum.variants.items():
                self.print(f'{py_name} = {json_name!r}')
