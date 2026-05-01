"""
Hourly runner: fetches buy-now signals and prints JSON to stdout.
The Claude loop reads this output and handles email + Notion logging.
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from signals import get_signals

if __name__ == "__main__":
    buy_signals = get_signals(only_buy=True)
    print(json.dumps(buy_signals))
