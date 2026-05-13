import os
from dotenv import load_dotenv

load_dotenv()

GMAIL_SENDER = os.environ["GMAIL_SENDER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
GMAIL_RECIPIENT = "vickomela36@gmail.com"

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
# Memecoin Buy Signals database (notion.so/347d49061af04a12b116e0601217bcaf)
NOTION_DATABASE_ID = "347d49061af04a12b116e0601217bcaf"

# DexScreener filter thresholds for "buy now"
MIN_LIQUIDITY_USD = 50_000
MIN_VOLUME_24H_USD = 100_000
MIN_VOL_LIQ_RATIO = 1.5
MIN_PRICE_CHANGE_24H = 5.0   # percent
CHAINS = ["solana", "ethereum", "bsc"]
