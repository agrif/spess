import code
import logging
import pathlib
import readline
import rlcompleter

import rich.logging
import rich.pretty

import spess
from spess.models import *

def main() -> None:
    # set up pretty logger
    logging.basicConfig(
        format = '%(message)s',
        level=logging.INFO,
        handlers=[rich.logging.RichHandler(markup=True)],
    )

    # create client
    client = spess.client.Client()

    # set up interactive namespace
    vars = globals()
    vars.update({
        'client': client,
        'c': client,
        'models': spess.models,
        'm': spess.models,
        'responses': spess.responses,
        'r': spess.responses,
    })

    # run a repl
    readline.set_completer(rlcompleter.Completer(vars).complete)
    readline.parse_and_bind('tab: complete')
    rich.pretty.install()
    code.InteractiveConsole(vars).interact()

if __name__ == '__main__':
    main()
