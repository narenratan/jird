Jird
====

**Jird** is a little language for writing and hearing music in just intonation.

It uses ratios to express frequencies, durations, and volumes.

The jird documentation is available on [readthedocs](jird.readthedocs.io).

Developing
----------
Common dev tasks are wrapped with [tox](https://tox.wiki/en/latest/).
With tox installed, running `tox` in the jird repo runs all the non-slow
tests and various checks on the code and docs. See the tox.ini file for
the individual tasks, which can be run as `tox -e typeguard` for example.
