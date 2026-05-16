import os

# Notion database that stores every "Buy Now" signal
NOTION_DATABASE_ID = "685b3530-321a-4a7e-a5af-6553774f29b0"

# Email recipient for buy-now alerts
ALERT_EMAIL = os.getenv("ALERT_EMAIL", "vickomela36@gmail.com")

# Signal thresholds — a token must pass ALL three to be "Buy Now"
MIN_PRICE_CHANGE_24H = 20.0      # minimum 24-hour price increase (%)
MIN_VOLUME_24H_USD   = 100_000   # minimum 24-hour trading volume ($)
MIN_LIQUIDITY_USD    = 50_000    # minimum pool liquidity ($)

# How many trending token profiles to evaluate per run
MAX_PROFILES = 50
