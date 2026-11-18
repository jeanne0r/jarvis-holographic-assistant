"""P6-L2 entry point; requires its own explicit authorization, never replays L1."""
from scripts.pilot_phase6b_panel import main
if __name__=='__main__':raise SystemExit(main(pilot='P6-L2'))
