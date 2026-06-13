# Fixture: deliberately invalid Python source (SC-012).
#
# This file MUST NOT parse successfully. It is used to verify that
# the analysis engine raises GazeParseError (wrapping SyntaxError)
# rather than crashing with an unhandled exception.
#
# Do NOT fix the syntax error below.


def broken(x: int):
    return x +
