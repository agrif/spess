SPESS
=====

Stick your agent token in a file named `token` in the root, then
install the dependencies (see `pyproject.toml`) and run `python3 -m
spess`.

```py
me = c.my_agent()
ship = c.my_ship(f'{me.symbol}-1')
wp = c.system_waypoints(ship, traits=[WaypointTrait.SHIPYARD]).first()
ship.orbit()
ship.navigate(wp)
ship.wait()
ship.dock()
```
