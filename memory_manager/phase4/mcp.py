"""Same controlled tools; NTFS-aware token loading chosen only by the host."""
from ..phase3.mcp import main
from .credentials import load_token

if __name__ == '__main__': main(token_reader=load_token)
