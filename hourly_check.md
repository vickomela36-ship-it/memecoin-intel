# Hourly Memecoin Signal Check

Run the following steps every time this prompt executes:

1. Run the signal checker:
   ```
   python /home/user/memecoin-intel/signals.py
   ```

2. Parse the JSON output. Each item in the list has:
   - `signal` — always "buy now" for items in this list
   - `coin` — e.g. "Pepe (PEPE)"
   - `symbol` — e.g. "PEPE"
   - `price_usd` — current price
   - `price_change_1h` — % change last hour
   - `volume_24h` — 24h volume in USD
   - `confidence` — "high" | "medium" | "low"
   - `timestamp` — ISO-8601 UTC
   - `dex_url` — DexScreener link
   - `notes` — human-readable summary

3. For EACH item in the output:

   a. Send an email to vickomela36@gmail.com with:
      - Subject: `🚨 Buy Now: {coin} — {price_change_1h:+.1f}% in 1h`
      - Body (HTML): a clear alert with coin name, price, 1h change, 24h volume,
        confidence level, DexScreener link, and timestamp.

   b. Log the signal to Notion data source `collection://d6d6dae1-44c2-4ce5-bbd4-52b6a096bc72`
      with these properties:
      - `Coin` = coin name (e.g. "Pepe (PEPE)")
      - `Signal` = "buy now"
      - `date:Timestamp:start` = timestamp (ISO-8601 datetime)
      - `date:Timestamp:is_datetime` = 1
      - `Price USD` = price_usd (number)
      - `Volume 24h` = volume_24h (number)
      - `Price Change 1h %` = price_change_1h (number)
      - `Confidence` = confidence value
      - `Notes` = notes string + " | " + dex_url

4. If the script returns no items (exit code 1 or empty list), log:
   "No buy now signals at {current UTC time}" and do nothing else.

5. Always report back a brief summary of what was done.
