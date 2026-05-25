# Central configuration — override values via environment variables or edit here.

# Notion database created for buy-now signal logging
NOTION_DATABASE_ID = "ab89b1e5dcf34beda8dab65f0c749640"

# Alert recipient
EMAIL_RECIPIENT = "vickomela36@gmail.com"

# Signal thresholds
BUY_NOW_CHANGE_THRESHOLD = 15.0   # minimum 24h price change % to trigger buy now
BUY_NOW_VOLUME_RATIO = 0.20       # minimum volume/market_cap ratio
TOP_COINS_TO_SCAN = 20            # top memecoins by volume to scan each run
