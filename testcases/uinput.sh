#!/bin/bash -e

#
# An - yet incomplete - example of how to use uinput
#

main()
{
    # Change into "our" directory tree
    cd "${0}.d"

    # And run the python script
    python main.py

    return 0
}


main

exit $?
