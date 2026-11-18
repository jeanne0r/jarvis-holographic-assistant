"""Set the protocol encoding before consuming JSON-RPC; never repair stored text."""
import sys


def configure_stdio():
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='strict')
