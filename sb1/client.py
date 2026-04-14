"""httpx wrapper for SpareBank1 personal banking API."""

import httpx

BASE_URL = "https://api.sparebank1.no/personal/banking"
ACCEPT = "application/vnd.sparebank1.v1+json; charset=utf-8"


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": ACCEPT,
    }


def hello_world(token: str) -> str:
    """Call the Hello World endpoint to verify authentication."""
    r = httpx.get(
        "https://api.sparebank1.no/common/helloworld",
        headers=_headers(token),
    )
    r.raise_for_status()
    return r.json().get("message", r.text)


def get_accounts(token: str) -> list[dict]:
    """Return list of accounts with key, name, balance."""
    r = httpx.get(f"{BASE_URL}/accounts", headers=_headers(token))
    r.raise_for_status()
    data = r.json()
    accounts = []
    for a in data.get("accounts", []):
        accounts.append({
            "key": a.get("key", ""),
            "name": a.get("name", ""),
            "accountNumber": a.get("accountNumber", ""),
            "balance": a.get("availableBalance", a.get("balance", "")),
            "currency": a.get("currencyCode", "NOK"),
        })
    return accounts


def get_transactions(
    token: str,
    account_key: str,
    from_date: str,
    to_date: str,
) -> list[dict]:
    """Return transactions for an account in a date range.

    Args:
        token: OAuth2 access token
        account_key: account key from get_accounts()
        from_date: start date YYYY-MM-DD
        to_date: end date YYYY-MM-DD

    Returns:
        List of transaction dicts with date, description, amount
    """
    params = {
        "accountKey": account_key,
        "fromDate": from_date,
        "toDate": to_date,
    }
    r = httpx.get(
        f"{BASE_URL}/transactions",
        headers=_headers(token),
        params=params,
    )
    if not r.is_success:
        raise RuntimeError(f"Transactions request failed {r.status_code}: {r.text}")
    data = r.json()
    txns = []
    for t in data.get("transactions", []):
        txns.append({
            "date": t.get("accountingDate", t.get("interestDate", ""))[:10],
            "description": t.get("description", "").strip(),
            "amount": t.get("amount", 0),
        })
    return txns
