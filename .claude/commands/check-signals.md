Search for the top trending memecoins right now using WebSearch. Look for tokens with strong price momentum (>20% in 1h or >50% in 24h), high trading volume (>$500k), and good liquidity. Evaluate each token and assign a signal: "buy now", "hold", or "sell".

For EVERY token with a "buy now" signal:
1. Log a new row to the Notion database at https://www.notion.so/787edb6d23364430b1ca47d87981f3bc using the mcp__Notion__notion-create-pages tool with parent data_source_id "48dfee3a-38dc-452b-b50f-42333ca97fa1". Set: Token Name, Signal="Buy Now", Price USD, 1h Change %, 24h Change %, Volume 24h, Liquidity USD, Chain, Timestamp (today's UTC datetime), DexScreener URL, Contract Address.
2. Draft an email to vickomela36@gmail.com using mcp__Gmail__create_draft with subject "🚨 Memecoin Buy Now Signal – <TokenName> (<date>)" and an HTML body containing: token name, chain, current price, 1h % change, 24h % change, 24h volume, liquidity, and the DexScreener link.

Print a summary table of ALL tokens scanned and highlight the buy now signals.
