SPESS
=====

Install *spess* in a virtual environment:

```
python3 -m venv spess-env && source ./spess-env/bin/activate
pip install git+https://github.com/agrif/spess
```

Stick your agent token in a file named *~/.config/spess/tokens.txt* on
unix-ey systems. On other systems, check `python -m spess.config` for
which paths to use.

Run `spess` to get a REPL!

```py
me = c.my_agent()
ship = c.ship(f'{me.symbol}-1')
wp = c.system_waypoints(ship, traits=[WaypointTrait.SHIPYARD]).first()
ship.orbit()
ship.navigate(wp)
ship.wait()
ship.dock()
```
