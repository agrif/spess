import typing

import spessgen.methods as methods
import spessgen.types as types
import spessgen.write_types as write_types

class ModelWriter(write_types.WriteTypes):
    def __init__(self, converter: methods.Converter, module: str) -> None:
        super().__init__(converter)
        self.module = module

    def go(self) -> None:
        self.generated_header()

        self.print('from __future__ import annotations')
        self.print()
        self.print('import dataclasses')
        self.print('import typing')
        self.print()
        self.print('from spess._json import Json, from_json, to_json, Enum, datetime, date')
        if self.resolver.models_module != self.module:
            models = self.resolver.models_module
            self.print(f'import spess.{models} as {models}')

        self.print()
        abs_types = self.resolver.iter_types(self.module, absolute=True)
        self.dunder_all([t.py_name for t, _ in abs_types])

        self.write_types(self.resolver.iter_types(self.module))
