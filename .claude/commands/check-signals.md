# Check Memecoin Signals

Run the memecoin signal scanner and act on any "buy now" signals.

## Steps

1. Run the signal scanner:
   ```bash
   cd /home/user/memecoin-intel && python signals.py
   ```

2. Parse the JSON output. For **every entry where `signal == "buy now"`**:

   a. **Send an email** to `vickomela36@gmail.com` using the Gmail MCP tool with:
      - Subject: `🚨 BUY NOW Signal: <symbol> (+<price_change_5m>% in 5m)`
      - Body (plain text):
        ```
        Memecoin Buy Signal Detected

        Symbol:           <symbol>
        Signal:           BUY NOW
        Price:            $<price_usd>
        5m Change:        +<price_change_5m>%
        1h Change:        +<price_change_1h>%
        5m Volume:        $<volume_5m_usd>
        Liquidity:        $<liquidity_usd>
        Pair Address:     <pair_address>
        Detected at:      <timestamp>

        DexScreener: https://dexscreener.com/solana/<pair_address>
        ```

   b. **Log a row** to the Notion "Memecoin Buy Signals Log" database (data source ID: `44763c62-4d07-4fde-bb1c-503846807aeb`) with these properties:
      - `Signal Entry`: `<symbol> <timestamp>` (title)
      - `Symbol`: `<symbol>`
      - `Signal`: `buy now`
      - `Pair Address`: `<pair_address>`
      - `Price USD`: `<price_usd>`
      - `Price Change 5m %`: `<price_change_5m>`
      - `Price Change 1h %`: `<price_change_1h>`
      - `Volume 5m USD`: `<volume_5m_usd>`
      - `Liquidity USD`: `<liquidity_usd>`
      - `date:Timestamp:start`: `<timestamp>`
      - `date:Timestamp:is_datetime`: `1`
      - `Email Sent`: `__YES__` (after sending the email successfully)

3. Print a summary:
   - How many tokens were scanned
   - How many "buy now" signals were found
   - Confirmation that email(s) and Notion log(s) were created
   - If no "buy now" signals: print "No buy now signals this run."
