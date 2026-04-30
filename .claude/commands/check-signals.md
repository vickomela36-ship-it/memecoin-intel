Run the memecoin signal check and send alerts for any "buy now" signals.

## Steps

1. Run the signal check:
   ```bash
   cd /home/user/memecoin-intel && python signals.py
   ```

2. Parse the JSON output. For **each entry where `signal == "buy now"`**:

   a. **Send an email** to `vickomela36@gmail.com` using the Gmail tool with:
      - Subject: `🚨 Memecoin BUY NOW Signal: <token>`
      - Body (plain text):
        ```
        BUY NOW signal detected for <token_name> (<token>)

        Price:          $<price_usd>
        5m change:      <price_change_5m_pct>%
        1h change:      <price_change_1h_pct>%
        6h change:      <price_change_6h_pct>%
        1h Volume:      $<volume_usd_1h>
        Liquidity:      $<liquidity_usd>
        DEX link:       <dex_url>
        Timestamp:      <timestamp>
        ```

   b. **Log the signal to Notion** in the database with data-source ID
      `8d726f13-4f6f-426f-99fa-09bfc9255602`.
      Set these properties:
      - `Signal`       → "<token> BUY NOW @ $<price_usd>"
      - `Timestamp`    → <timestamp> (ISO-8601 datetime)
      - `Token`        → "<token_name> (<token>)"
      - `Price_USD`    → <price_usd>
      - `Signal_Type`  → "buy now"
      - `Notes`        → "5m: <price_change_5m_pct>% | 1h: <price_change_1h_pct>% | vol: $<volume_usd_1h> | liq: $<liquidity_usd> | <dex_url>"

3. Print a brief summary: how many tokens were checked, how many "buy now" signals were found, and confirm email + Notion actions taken.
