from __future__ import annotations

import contextlib
import dataclasses
import os.path
import typing

import humps

from spessgen.config import *
import spessgen.methods as methods
import spessgen.spec as spec

WAIT_DOCS = ' '.join([
    'Wait interactively until this object is ready for more actions.',
    'For a non-interactive, async wait, await this object directly.',
])

AWAIT_DOCS = ' '.join([
    'Wait asynchronously until this object is ready for more actions.',
    'For an interactive, blocking wait, see :func:`wait`.',
])

def remove_prefix(name: str, prefix: str | None = None, replace: str | None = None) -> str:
    # generic arguments, apply to all
    if '[' in name and name.endswith(']'):
        i = name.index('[')
        a = name[:i]
        bs = name[i+1:-1].split(',')
        a = remove_prefix(a, prefix)
        b = ', '.join(remove_prefix(b.strip(), prefix) for b in bs)
        return f'{a}[{b}]'

    # base case
    if prefix is None:
        return name
    elif name.startswith(prefix + '.'):
        suffix = name[len(prefix) + 1:]
        if replace is not None:
            return replace + '.' + suffix
        else:
            return suffix
    else:
        return name

@dataclasses.dataclass
class Type:
    spec_name: str | None
    py_full_name: str
    py_name: str
    doc: str | None
    definition: Struct | Enum

    synced: str | None
    keyed: Keyed | None
    as_keyed: list[str]
    properties: dict[str, str]
    convenience: dict[str, methods.Convenience]

    def _map_types(self, f: typing.Callable[[str], str]) -> typing.Self:
        return dataclasses.replace(
            self,
            py_name=f(self.py_name),
            definition=self.definition._map_types(f),
            keyed=self.keyed._map_types(f) if self.keyed else None
        )

    def attributes(self) -> list[str]:
        attrs = self.definition.attributes()
        attrs += self.properties.keys()
        attrs += self.convenience.keys()
        return attrs

    def check_name(self, name: str) -> None:
        if name in self.attributes():
            raise RuntimeError(f'duplicate attributes on {self.py_name}: {name}')

@dataclasses.dataclass
class Struct:
    @dataclasses.dataclass
    class Field:
        py_name: str
        json_name: str
        py_full_type: str
        py_type: str
        doc: str | None
        optional: bool

        def _map_types(self, f: typing.Callable[[str], str]) -> typing.Self:
            return dataclasses.replace(self, py_type=f(self.py_type))

    fields: dict[str, Field]

    def _map_types(self, f: typing.Callable[[str], str]) -> typing.Self:
        return dataclasses.replace(
            self,
            fields={k: v._map_types(f) for k, v in self.fields.items()},
        )

    def attributes(self) -> list[str]:
        return list(self.fields.keys())

@dataclasses.dataclass
class Enum:
    variants: dict[str, str]

    def _map_types(self, f: typing.Callable[[str], str]) -> typing.Self:
        return self

    def attributes(self) -> list[str]:
        return list(self.variants.keys())

TypeTree: typing.TypeAlias = tuple[Type, list['TypeTree']]

class Resolver:
    def __init__(self, spec: spec.Spec, models_module) -> None:
        self.spec = spec
        self.type_tree: list[TypeTree] = []
        self.models_module = models_module

        for k, schema in self.spec.components.schemas.items():
            self.resolve(k, schema, parent=self.models_module)

    @contextlib.contextmanager
    def _subtypes(self) -> typing.Iterator[list[TypeTree]]:
        type_tree = self.type_tree
        try:
            self.type_tree = []
            yield self.type_tree
        finally:
            self.type_tree = type_tree

    def _resolve_ref(self, ref: str) -> tuple[str, spec.Schema]:
        if not '/' in ref:
            raise ValueError(f'bad $ref: {ref!r}')
        root, leaf = ref.rsplit('/', 1)
        if root != '#/components/schemas':
            raise NotImplementedError(f'unknown $ref: {ref!r}')
        return (leaf, self.spec.components.schemas[leaf])

    def _resolve_array(self, spec_name: str, schema: spec.Schema, parent: str | None, name_hint: str) -> str:
        if schema.items is None:
            raise ValueError('list schema with no items')
        if name_hint.endswith('s'):
            name_hint = name_hint[:-1]
        else:
            name_hint += 'Item'
        sub = self.resolve(spec_name, schema.items, parent=parent, name_hint=name_hint)
        return f'list[{sub}]'

    def _define_struct(self, spec_name: str, py_parent_name: str, schema: spec.Schema) -> Struct:
        if schema.properties is None:
            raise ValueError('struct schema with no properties')

        required = set()
        if schema.required is not None:
            required = set(schema.required)

        # re-order properties so optional are at end
        properties: dict[str, spec.SchemaLike] = {}
        for k, v in schema.properties.items():
            if k in required:
                properties[k] = v
        for k, v in schema.properties.items():
            if k not in required:
                properties[k] = v

        fields: dict[str, Struct.Field] = {}
        for k, v in properties.items():
            py_name = humps.decamelize(k)
            if py_name in KEYWORDS:
                py_name += '_'

            py_type = self.resolve(spec_name + '.' + k, v, parent=py_parent_name)
            py_type = STRUCT_FIELD_TYPE.get(spec_name, {}).get(k, py_type)

            fields[py_name] = Struct.Field(
                py_name = py_name,
                json_name = k,
                py_type = py_type,
                py_full_type = py_type,
                doc = self.resolve_schema(v).description,
                optional = k not in required,
            )

        return Struct(fields)

    def _define_enum(self, schema: spec.Schema) -> Enum:
        if schema.enum is None:
            raise ValueError('enum schema with no enum')

        common = len(os.path.commonprefix(schema.enum))
        variants = []
        for var in schema.enum:
            pyvar = humps.decamelize(var[common:])
            if pyvar in KEYWORDS:
                pyvar += '_'
            variants.append((pyvar, var))
        variants.sort(key=lambda t: t[0])
        return Enum(dict(variants))

    def _set_as_keyed(self, ty: Type) -> None:
        attrs = ty.attributes()
        for key_type, keyed in KEYED_TYPES.items():
            if keyed.foreign in attrs:
                ty.as_keyed.append(key_type)

    def _add_convenience(self, ty: Type) -> None:
        wait = WAIT.get(ty.py_name, [])
        if wait:
            ty.check_name('wait')
            ty.convenience['wait'] = methods.Convenience(
                spec_name = None,
                py_name = 'wait',
                args = [w for w in wait] + [methods.Convenience.Argument(
                    py_name = 'message',
                    py_type = 'str',
                    optional = True,
                )],
                py_result = 'None',
                py_impl = 'backend._wait',
                doc = WAIT_DOCS,
                doc_rest = True,
                tags = ['Waiting'],
            )
            ty.check_name('__await__')
            ty.convenience['__await__'] = methods.Convenience(
                spec_name = None,
                py_name = '__await__',
                args = [w for w in wait],
                py_result = 'typing.Awaitable[None]',
                py_impl = 'backend._await',
                doc = AWAIT_DOCS,
                doc_rest = True,
                tags = ['Waiting'],
            )

    def resolve_schema(self, schema: spec.SchemaLike) -> spec.Schema:
        return self.resolve_schema_named(schema)[1]

    def resolve_schema_named(self, schema: spec.SchemaLike) -> tuple[str | None, spec.Schema]:
        if isinstance(schema, spec.SchemaRef):
            return self._resolve_ref(schema.ref)
        elif isinstance(schema, spec.SchemaEmpty):
            return (None, spec.Schema())

        if schema.allOf is not None:
            if len(schema.allOf) == 1:
                return self.resolve_schema_named(schema.allOf[0])
            else:
                raise NotImplementedError(f'unhandled allOf: {schema.allOf!r}')

        if schema.anyOf is not None:
            if len(schema.anyOf) >= 1:
                # kind of a hack, ignore variants
                return self.resolve_schema_named(schema.anyOf[0])
            else:
                raise NotImplementedError(f'unhandled anyOf: {schema.anyOf!r}')

        return (None, schema)

    def resolve(
            self,
            spec_name: str,
            schema: spec.SchemaLike,
            parent: str | None = None,
            name_hint: str | None = None,
            define: bool = True,
    ) -> str:
        return self.resolve_type(spec_name, schema, parent=parent, name_hint=name_hint, define=define, resolve_only=True)[0]

    def _add_type(self, ty: Type, subtypes: list[TypeTree]) -> None:
        # we only care about conflicts with siblings
        if [t for t, _ in self.type_tree if t.py_name == ty.py_name]:
            raise RuntimeError(f'conflicting type names: {ty.py_name}')
        self.type_tree.append((ty, subtypes))

    def resolve_type(
            self,
            spec_name: str,
            schema: spec.SchemaLike,
            parent: str | None = None,
            name_hint: str | None = None,
            define: bool = True,
            resolve_only: bool = False,
            promote_orphans: bool = False,
    ) -> tuple[str, Type | None]:
        # resolve schema for real
        refname, schema = self.resolve_schema_named(schema)
        if refname is not None:
            # do not re-define refs
            return self.resolve_type(refname, schema, parent=self.models_module, define=False)

        if parent is None:
            parent = self.models_module

        if name_hint is None:
            name_hint = spec_name
        name_hint = name_hint.rsplit('.', 1)[-1]

        try:
            py_name = TYPE_NAME[spec_name]
        except KeyError:
            py_name = humps.pascalize(name_hint)
            if py_name in KEYWORDS:
                py_name += '_'
        if parent is not None:
            py_name = parent + '.' + py_name

        definition: Struct | Enum | None = None
        subtypes = []

        match schema.type:
            case schema.Type.ARRAY:
                return (self._resolve_array(spec_name, schema, parent=parent, name_hint=name_hint), None)
            case schema.Type.BOOLEAN:
                return ('bool', None)
            case schema.Type.INTEGER:
                return ('int', None)
            case schema.Type.NULL:
                return ('None', None)
            case schema.Type.NUMBER:
                return ('float', None)
            case schema.Type.OBJECT:
                if resolve_only and not define:
                    return (py_name, None)
                with self._subtypes() as subtypes:
                    definition = self._define_struct(spec_name, py_name, schema)
            case schema.Type.STRING if schema.format == schema.Format.DATE_TIME:
                return ('datetime', None)
            case schema.Type.STRING if schema.enum is not None:
                if resolve_only and not define:
                    return (py_name, None)
                definition = self._define_enum(schema)
            case schema.Type.STRING:
                return ('str', None)
            case None:
                return ('Json', None)
            case _ as unreachable:
                typing.assert_never(unreachable)

        if definition is None:
            raise NotImplementedError(f'no definition for {schema!r}')

        keyed = KEYED_TYPES.get(py_name)
        synced = None
        if keyed and parent is not None:
            keyed = dataclasses.replace(keyed)
            keyed.name = parent + '.' + keyed.name
            synced = keyed.foreign

        ty = Type(
            spec_name = spec_name,
            py_full_name = py_name,
            py_name = py_name,
            doc = schema.description,
            definition = definition,
            synced = synced,
            keyed = keyed,
            as_keyed = [],
            properties = {},
            convenience = {},
        )

        properties = PROPERTIES.get(py_name, {})
        if keyed and keyed.local != keyed.foreign:
            props_with_key = {keyed.foreign: 'self.' + keyed.local}
            props_with_key.update(properties)
            properties = props_with_key
        for prop, val in properties.items():
            ty.check_name(prop)
            ty.properties[prop] = val

        self._set_as_keyed(ty)
        self._add_convenience(ty)

        if define:
            self._add_type(ty, subtypes)
        elif promote_orphans:
            # we're not defining ty, but we will define the children
            def promote(subtree: tuple[Type, list[TypeTree]]) -> tuple[Type, list[TypeTree]]:
                promoted = subtree[0]._map_types(lambda t: remove_prefix(t, prefix=ty.py_name, replace=parent))
                return (promoted, [promote(x) for x in subtree[1]])

            ty, subtypes = promote((ty, subtypes))
            for child in subtypes:
                self._add_type(*child)

        return (ty.py_name, ty)

    IterTypes: typing.TypeAlias = typing.Iterator[tuple[Type, 'IterTypes']]
    def iter_tree(self, module: str | None = None, absolute: bool = False, types: list[TypeTree] | None = None, prefix: str | None = None) -> IterTypes:
        if types is None:
            types = self.type_tree

        if prefix is None:
            prefix = module

        for ty, children in types:
            renamed = remove_prefix(ty.py_name, prefix=prefix)
            if prefix is not None and renamed == ty.py_name:
                continue
            yield (
                dataclasses.replace(
                    ty._map_types(lambda t: remove_prefix(t, prefix=module)),
                    py_name=renamed,
                ),
                self.iter_tree(module=module, types=children, prefix=prefix if absolute else ty.py_name),
            )

    def iter_flat(self, module: str | None = None, absolute: bool = False, types: IterTypes | None = None) -> typing.Iterator[Type]:
        if types is None:
            types = self.iter_tree(module=module, absolute=absolute)
        for ty, children in types:
            yield ty
            yield from self.iter_flat(module=module, absolute=absolute, types=children)

    def get(self, py_name: str, from_types: IterTypes | None = None) -> Type:
        if from_types is None:
            from_types = self.iter_tree(absolute=True)
        for ty, children in from_types:
            if ty.py_name == py_name:
                return ty
            try:
                return self.get(py_name, from_types=children)
            except KeyError:
                pass
        raise KeyError(py_name)

    def children(self, ty: Type) -> typing.Iterator[str]:
        if isinstance(ty.definition, Struct):
            for field in ty.definition.fields.values():
                child = field.py_type
                if child.startswith('list[') and child.endswith(']'):
                    child = child[len('list['):-len(']')]
                yield child
        elif isinstance(ty.definition, Enum):
            pass
        else:
            typing.assert_never(ty.definition)

    def parents(self, ty: Type) -> typing.Iterator[Type]:
        for parent in self.iter_flat():
            for child in self.children(parent):
                if child == ty.py_name:
                    yield parent
                    break
