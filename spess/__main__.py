import code
import logging
import pathlib
import readline
import rlcompleter

import rich.logging
import rich.pretty

import spess.client
import spess.models
import spess.responses

from spess.models import *

def main() -> None:
    # set up pretty logger
    logging.basicConfig(
        format = '%(message)s',
        level=logging.INFO,
        handlers=[rich.logging.RichHandler(markup=True)],
    )

    # load token
    here = pathlib.Path(__file__).parent
    with open(here / '..' / 'token') as f:
        token = f.read().strip()

    # create client
    client = spess.client.Client(token)

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
