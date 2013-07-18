#!/bin/bash
# vim:set sw=2:

#
# A magic script, it looks for callable (functions) in a python file
# and defines wrappers for those files in this bash file.
# This way it's possible to call python function "natively" from bash.
#

WRAPPER_PREFIX=igor_
PYMODULE=common.common

_pyc_cmds()
{
cat <<EOP | python -
import $PYMODULE
for f in $PYMODULE.__dict__:
  if callable($PYMODULE.__dict__[f]):
    print(f)
EOP
}

pyc()
{
cat <<EOP | python - "$@"
import sys
import $PYMODULE
_args = sys.argv[1:]
cmd = _args[0]
args = _args[1:]
func = $PYMODULE.__dict__[cmd]
print(func(*args))
EOP
}


# We import all common.py functions into bash:
for cmd in $(_pyc_cmds)
do
  eval "${WRAPPER_PREFIX}$cmd() { pyc $cmd \"\$@\" ; }"
done

[[ $0 == $BASH_SOURCE ]] && "$@"
