import typing

import spessgen.methods as methods
import spessgen.types as types
import spessgen.write_types as write_types

class ModelWriter(write_types.WriteTypes):
    def go(self) -> None:
        self.generated_header()

        self.print('from __future__ import annotations')
        self.print()
        self.print('import dataclasses')
        self.print('import typing')
        self.print()
        self.print('import spess._backend as backend')
        self.print('from spess._json import Json, from_json, to_json')
        if self.resolver.models_module != self.module:
            models = self.resolver.models_module
            self.print(f'import spess.{models} as {models}')
        self.print(f'from spess._model_bases import date, datetime, Enum, LocalClient, Synced, Keyed')
        self.print('from spess._paged import Paged')
        if self.converter.responses_module != self.module:
            responses = self.converter.responses_module
            self.print(f'import spess.{responses} as {responses}')

        self.print()
        all_types = []
        for t, _ in self.resolver.iter_tree(self.module, absolute=True):
            all_types.append(t.py_name)
            if t.keyed:
                all_types.append(t.keyed.name)
        all_types.sort()
        self.dunder_all(all_types)

        self.write_types(self.resolver.iter_tree(self.module))
