"""SpareBank1 CLI — fetch accounts and transactions."""

import csv
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import click

from sb1 import auth, client

ENV_FILE = Path.home() / ".sb1_env"


def _load_env():
    """Load SB1_CLIENT_ID and SB1_CLIENT_SECRET from ~/.sb1_env if present."""
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


@click.group()
def main():
    """SpareBank1 personal API CLI."""
    _load_env()


@main.command()
@click.option("--client-id", envvar="SB1_CLIENT_ID", prompt="Client ID", help="OAuth2 client ID from developer.sparebank1.no")
@click.option("--client-secret", envvar="SB1_CLIENT_SECRET", prompt="Client Secret", hide_input=True, help="OAuth2 client secret")
@click.option("--save", is_flag=True, default=False, help="Save credentials to ~/.sb1_env")
def login(client_id, client_secret, save):
    """Authenticate with BankID and save token."""
    if save:
        ENV_FILE.write_text(f"SB1_CLIENT_ID={client_id}\nSB1_CLIENT_SECRET={client_secret}\n")
        ENV_FILE.chmod(0o600)
        click.echo(f"✓ Credentials saved to {ENV_FILE}")
    auth.login(client_id, client_secret)


@main.command()
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table", help="Output format")
def accounts(fmt):
    """List all SpareBank1 accounts."""
    token = auth.get_access_token()
    accs = client.get_accounts(token)
    if fmt == "json":
        click.echo(json.dumps(accs, indent=2, ensure_ascii=False))
    else:
        click.echo(f"{'KEY':<36}  {'NAME':<30}  {'ACCOUNT NUMBER':<20}  {'BALANCE':>12}  {'CCY'}")
        click.echo("-" * 110)
        for a in accs:
            click.echo(f"{a['key']:<36}  {a['name']:<30}  {a['accountNumber']:<20}  {str(a['balance']):>12}  {a['currency']}")


@main.command()
@click.option("--account", "account_key", required=True, envvar="SB1_ACCOUNT_KEY", help="Account key (from 'sb1 accounts')")
@click.option("--from", "from_date", default=None, help="Start date YYYY-MM-DD (default: 30 days ago)")
@click.option("--to", "to_date", default=None, help="End date YYYY-MM-DD (default: today)")
@click.option("--days", default=None, type=int, help="Fetch last N days (overrides --from/--to)")
@click.option("--format", "fmt", type=click.Choice(["csv", "json", "table"]), default="csv", help="Output format")
@click.option("--output", "-o", default=None, help="Output file (default: stdout)")
def transactions(account_key, from_date, to_date, days, fmt, output):
    """Fetch transactions for an account."""
    today = date.today()

    if days:
        from_date = str(today - timedelta(days=days))
        to_date = str(today)
    else:
        if not from_date:
            from_date = str(today - timedelta(days=30))
        if not to_date:
            to_date = str(today)

    token = auth.get_access_token()
    txns = client.get_transactions(token, account_key, from_date, to_date)

    out = open(output, "w", encoding="utf-8", newline="") if output else sys.stdout

    try:
        if fmt == "json":
            out.write(json.dumps(txns, indent=2, ensure_ascii=False) + "\n")
        elif fmt == "csv":
            writer = csv.DictWriter(out, fieldnames=["date", "description", "amount"])
            writer.writeheader()
            writer.writerows(txns)
        else:
            out.write(f"{'DATE':<12}  {'AMOUNT':>12}  DESCRIPTION\n")
            out.write("-" * 80 + "\n")
            for t in txns:
                out.write(f"{t['date']:<12}  {str(t['amount']):>12}  {t['description']}\n")
    finally:
        if output:
            out.close()
            click.echo(f"✓ {len(txns)} transactions written to {output}", err=True)
        else:
            click.echo(f"✓ {len(txns)} transactions", err=True)
