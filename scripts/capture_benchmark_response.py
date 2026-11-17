"""Run the existing unprofiled benchmark; write its response after timing ends."""
import json
from pathlib import Path
import runpy
import sys
from unittest.mock import patch
from nba_gm_data import app_actions as aa

output = Path(sys.argv[sys.argv.index('--output') + 1])
dispatch, captured = aa.dispatch_app_action, {}


def capture(*args, **kwargs):
    result = dispatch(*args, **kwargs)
    captured['response'] = result
    return result


with patch.object(aa, 'dispatch_app_action', capture):
    runpy.run_path(str(Path(__file__).with_name('benchmark_advance_speed.py')), run_name='__main__')
# The original benchmark already owns this response throughout its timed span.
# Only an extra reference is kept here; serialization happens after the timer.
(output / 'response.json').write_text(json.dumps(captured.pop('response'), sort_keys=True))
