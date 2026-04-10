# memecoin-intel

Solana memecoin swing recovery scanner — catches 2x-3x price recoveries after dumps on high-volume, established tokens.

## Strategy: Swing Recovery After Dump

1. **Scan** trending high-volume Solana tokens via Birdeye/Jupiter
2. **Filter** by age (>24h) and market cap (>$2M) to avoid rugs
3. **Detect dumps** — price dropped ≥30% from recent high with elevated sell volume
4. **Entry signal** — price bouncing off bottom + RSI oversold + buy volume returning
5. **Exit** — take profit at 2x/3x or stop-loss at -20%

## Project Structure

```
memecoin-intel/
├── config.py           # API keys, strategy parameters, thresholds
├── helius_client.py    # Helius API — token metadata, age, supply
├── jupiter_client.py   # Jupiter/Birdeye API — prices, OHLCV, volume
├── signals.py          # Dump detection + recovery entry signal engine
├── tracker.py          # PnL logging, position management
├── scanner.py          # Main loop — scan, signal, trade
├── dashboard.py        # Streamlit UI
└── requirements.txt
```

## Setup

```bash
pip install -r requirements.txt

export HELIUS_API_KEY="your-helius-key"
export BIRDEYE_API_KEY="your-birdeye-key"
```

## Usage

**Run the scanner** (paper trading):
```bash
python scanner.py
```

**Run the dashboard**:
```bash
streamlit run dashboard.py
```

## Signal Criteria

| Parameter | Default |
|-----------|---------|
| Min token age | 24 hours |
| Min market cap | $2M |
| Min 24h volume | $500K |
| Dump threshold | -30% from high |
| Volume spike | 2x normal during dump |
| Recovery bounce | ≥5% off bottom |
| RSI oversold | <35 |
| Buy volume ratio | >55% |
| Take profit | 2x / 3x |
| Stop loss | -20% |

All parameters are configurable in `config.py`.
