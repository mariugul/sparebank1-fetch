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


@main.command("hello")
def hello():
    """Test authentication with a Hello World request."""
    token = auth.get_access_token()
    msg = client.hello_world(token)
    click.echo(msg)


@main.command("save-token")
@click.option("--access-token", required=True, envvar="ACCESS_TOKEN", help="access_token from curl response")
@click.option("--refresh-token", required=True, envvar="REFRESH_TOKEN", help="refresh_token from curl response")
@click.option("--expires-in", default=600, help="expires_in from curl response (default: 600)")
def save_token(access_token, refresh_token, expires_in):
    """Save a token obtained manually (e.g. via curl) to ~/.sb1_token."""
    auth.save_token(access_token, refresh_token, expires_in)
    click.echo("✓ Token saved to ~/.sb1_token")


@main.command()
def refresh():
    """Force a token refresh using the stored refresh_token."""
    client_id = os.environ.get("SB1_CLIENT_ID", "")
    if not client_id:
        raise click.ClickException("SB1_CLIENT_ID not set. Add it to ~/.sb1_env or export it.")
    token = auth._load_token()
    if not token or not token.get("refresh_token"):
        raise click.ClickException("No refresh token found. Run 'sb1 save-token' or 'sb1 login' first.")
    client_secret = os.environ.get("SB1_CLIENT_SECRET") or None
    new_token = auth._refresh(token, client_id, client_secret)
    click.echo(f"✓ Token refreshed, expires in {new_token.get('expires_in', '?')}s")


@main.command("accounts")
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table", help="Output format")
def accounts_cmd(fmt):
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


@main.command("transactions")
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
    try:
        account_key = client.resolve_account_key(token, account_key)
    except ValueError as e:
        raise click.ClickException(str(e))
    txns = client.get_transactions(token, account_key, from_date, to_date)

    out = open(output, "w", encoding="utf-8", newline="") if output else sys.stdout

    try:
        if fmt == "json":
            out.write(json.dumps(txns, indent=2, ensure_ascii=False) + "\n")
        elif fmt == "csv":
            writer = csv.DictWriter(out, fieldnames=["id", "date", "description", "amount", "remote_account", "type_code", "booking_status", "account_name"])
            writer.writeheader()
            writer.writerows(txns)
        else:
            out.write(f"{'DATE':<12}  {'AMOUNT':>12}  {'STATUS':<8}  {'TYPE':<8}  {'REMOTE ACCOUNT':<16}  {'ACCOUNT':<20}  DESCRIPTION\n")
            out.write("-" * 120 + "\n")
            for t in txns:
                out.write(f"{t['date']:<12}  {str(t['amount']):>12}  {t.get('booking_status',''):<8}  {t.get('type_code',''):<8}  {t.get('remote_account',''):<16}  {t.get('account_name',''):<20}  {t['description']}\n")
    finally:
        if output:
            out.close()
            click.echo(f"✓ {len(txns)} transactions written to {output}", err=True)
        else:
            click.echo(f"✓ {len(txns)} transactions", err=True)
