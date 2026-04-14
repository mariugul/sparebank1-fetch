# sparebank1-fetch

CLI tool for fetching accounts and transactions from the [SpareBank1 personal banking API](https://developer.sparebank1.no).

## Setup

### 1. Register your app

Go to [developer.sparebank1.no](https://developer.sparebank1.no), register a **personal client** app, and note your `client_id` and `client_secret`.

Set the redirect URI to: `http://localhost:12345/callback`

### 2. Install

```bash
uv sync
```

### 3. Authenticate (BankID)

```bash
uv run sb1 login --client-id YOUR_ID --client-secret YOUR_SECRET --save
```

This opens your browser for BankID login. Token is saved to `~/.sb1_token`, credentials to `~/.sb1_env`.

## Usage

```bash
# List accounts
uv run sb1 accounts

# Fetch transactions (last 30 days, CSV to stdout)
uv run sb1 transactions --account <key>

# Fetch last 7 days
uv run sb1 transactions --account <key> --days 7

# Custom date range, save to file
uv run sb1 transactions --account <key> --from 2026-01-01 --to 2026-04-14 -o output.csv

# JSON output
uv run sb1 transactions --account <key> --format json
```

## Pipeline with bank2excel and Firefly

```bash
uv run sb1 transactions --account <key> --days 7 -o /tmp/raw.csv
bank2excel process /tmp/raw.csv -o /tmp/normalized.csv
# Then trigger_import via Firefly MCP
```

## Docker

```bash
docker pull ghcr.io/mariugul/sparebank1-fetch:latest

docker run --rm -it \
  -e SB1_CLIENT_ID=your_id \
  -e SB1_CLIENT_SECRET=your_secret \
  -v ~/.sb1_token:/root/.sb1_token \
  -p 12345:12345 \
  ghcr.io/mariugul/sparebank1-fetch accounts
```

> **Note:** The `login` command requires a browser and port 12345 exposed. For automated use (cron), authenticate once locally and mount the token file.
