"""
database.py — Mock Database Layer for Wise Help Assistant
==========================================================
All data lives in data/mock_db.json (18 KB, 6 users / 20 transfers /
8 tickets / 8 cards).  Every function reads the file, makes its change,
and writes it back so state persists across server restarts.

Actions supported
-----------------
Transfers : lookup, estimate, create, update_status, list_by_user
Tickets   : create, update, lookup, list_by_user
Cards     : get, freeze, unfreeze, request_replacement, order_new
Users     : lookup_by_email
"""

import json, math, os, random, re, string
from datetime import datetime, timezone
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "mock_db.json")

# ── FX & fee tables ────────────────────────────────────────────────────────
FX_RATES = {
    ("CAD","PHP"):37.31, ("PHP","CAD"):0.0268,
    ("CAD","USD"):0.734, ("USD","CAD"):1.362,
    ("CAD","EUR"):0.676, ("EUR","CAD"):1.479,
    ("CAD","GBP"):0.577, ("GBP","CAD"):1.732,
    ("CAD","INR"):61.10, ("INR","CAD"):0.01637,
    ("CAD","AUD"):1.116, ("AUD","CAD"):0.896,
    ("USD","EUR"):0.921, ("EUR","USD"):1.086,
    ("USD","GBP"):0.786, ("GBP","USD"):1.272,
    ("USD","PHP"):56.45, ("PHP","USD"):0.0177,
    ("USD","INR"):83.12, ("INR","USD"):0.01203,
    ("USD","AUD"):1.521, ("AUD","USD"):0.657,
    ("USD","SGD"):1.337, ("SGD","USD"):0.748,
    ("USD","JPY"):149.82,("JPY","USD"):0.00667,
    ("USD","MXN"):17.15, ("MXN","USD"):0.0583,
    ("GBP","INR"):105.80,("INR","GBP"):0.00945,
    ("GBP","EUR"):1.172, ("EUR","GBP"):0.853,
    ("GBP","AUD"):1.935, ("AUD","GBP"):0.517,
    ("GBP","SGD"):1.702, ("SGD","GBP"):0.588,
    ("GBP","JPY"):190.62,("JPY","GBP"):0.00524,
    ("AUD","SGD"):0.878, ("SGD","AUD"):1.139,
    ("AUD","EUR"):0.606, ("EUR","AUD"):1.651,
    ("AUD","NZD"):1.073, ("NZD","AUD"):0.932,
    ("JPY","EUR"):0.00615,("EUR","JPY"):162.65,
    ("JPY","GBP"):0.00524,
}
SUPPORTED = sorted({c for pair in FX_RATES for c in pair})

FEE_TABLE = {
    "CAD":(0.008,0.50), "USD":(0.007,0.50), "GBP":(0.006,0.30),
    "EUR":(0.007,0.40), "AUD":(0.008,0.50), "SGD":(0.007,0.40),
    "JPY":(0.010,50.0), "MXN":(0.010,1.00), "INR":(0.010,10.0),
    "PHP":(0.010,5.00),
}
DELIVERY = {
    ("CAD","PHP"):"1-3 business days", ("USD","EUR"):"1-2 business days",
    ("USD","GBP"):"Same day - 1 business day", ("GBP","INR"):"1-2 business days",
    ("AUD","USD"):"1-2 business days", ("USD","PHP"):"1-2 business days",
    ("USD","CAD"):"1-2 business days", ("GBP","EUR"):"Same day - 1 business day",
    ("CAD","USD"):"1-2 business days", ("CAD","EUR"):"1-2 business days",
    ("JPY","USD"):"1-2 business days", ("JPY","EUR"):"2-3 business days",
    ("JPY","GBP"):"1-2 business days",
}

def _now(): return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
def _uid(prefix,n=6): return prefix+"-"+"".join(random.choices(string.ascii_uppercase+string.digits,k=n))
def _load(): 
    with open(DB_PATH,encoding="utf-8") as f: return json.load(f)
def _save(db):
    with open(DB_PATH,"w",encoding="utf-8") as f: json.dump(db,f,indent=2,ensure_ascii=False)


# ── USER ──────────────────────────────────────────────────────────────────

def lookup_user(email: str) -> dict:
    """Find a user by email."""
    db = _load()
    email = email.strip().lower()
    user = next((u for u in db["users"] if u["email"].lower() == email), None)
    if not user:
        return {"found": False, "error": f"No account found for '{email}'. Please check the email address."}
    return {"found": True, **user}


# ── TRANSFER ──────────────────────────────────────────────────────────────

def lookup_transfer(transfer_id: str) -> dict:
    """
    Look up a transfer by ID.
    Returns full details including troubleshooting tips for delayed transfers.
    """
    db = _load()
    tid = transfer_id.strip().upper()
    t = next((x for x in db["transfers"] if x["transfer_id"].upper() == tid), None)
    if not t:
        return {
            "found": False,
            "error": f"No transfer found with ID '{tid}'. "
                     "Please double-check the reference number (e.g. TW-001234)."
        }
    result = {
        "found": True,
        "transfer_id":       t["transfer_id"],
        "status":            t["status"],
        "from_currency":     t["from_currency"],
        "to_currency":       t["to_currency"],
        "amount":            t["amount"],
        "fee":               t["fee"],
        "recipient_gets":    t["recipient_gets"],
        "exchange_rate":     t["exchange_rate"],
        "estimated_delivery":t["estimated_delivery"],
        "recipient_name":    t["recipient_name"],
        "recipient_account": t["recipient_account"],
        "created_at":        t["created_at"],
    }
    if t["status"] in ("Delayed","Awaiting Funds") and t.get("troubleshooting_tip"):
        result["troubleshooting_tip"] = t["troubleshooting_tip"]
    if t["status"] == "Delayed" and t.get("delay_reason"):
        result["delay_reason"] = t["delay_reason"]
    return result


def list_transfers(user_email: str, status_filter: Optional[str] = None) -> dict:
    """List all transfers for a user, optionally filtered by status."""
    db = _load()
    email = user_email.strip().lower()
    transfers = [t for t in db["transfers"] if t["user_email"].lower() == email]
    if not transfers:
        return {"found": False, "error": f"No transfers found for '{email}'."}
    if status_filter:
        transfers = [t for t in transfers if t["status"].lower() == status_filter.lower()]
    return {
        "found": True,
        "count": len(transfers),
        "transfers": [
            {"transfer_id":t["transfer_id"],"status":t["status"],
             "from_currency":t["from_currency"],"to_currency":t["to_currency"],
             "amount":t["amount"],"recipient_name":t["recipient_name"],
             "created_at":t["created_at"],"estimated_delivery":t["estimated_delivery"]}
            for t in sorted(transfers, key=lambda x: x["created_at"], reverse=True)
        ]
    }


def estimate_transfer(from_currency: str, to_currency: str, amount: float) -> dict:
    """
    Estimate fee, rate, recipient amount and delivery window.
    Validates currency pair and amount limits.
    """
    fc = from_currency.upper().strip()
    tc = to_currency.upper().strip()

    if fc not in SUPPORTED:
        return {"error": f"'{fc}' is not supported as a send currency. Supported: {', '.join(SUPPORTED)}"}
    if tc not in SUPPORTED:
        return {"error": f"'{tc}' is not supported as a receive currency. Supported: {', '.join(SUPPORTED)}"}
    if fc == tc:
        return {"error": "Source and destination currencies must be different."}
    if amount <= 0:
        return {"error": "Amount must be greater than 0."}
    if amount > 1_000_000:
        return {"error": "Amount exceeds the 1,000,000 limit. For large transfers contact Wise support."}

    rate = FX_RATES.get((fc, tc))
    if not rate:
        return {"error": f"The pair {fc}→{tc} is not currently available. Check wise.com/pricing for supported pairs."}

    pct, fixed = FEE_TABLE.get(fc, (0.009, 0.50))
    fee = round(amount * pct + fixed, 2)
    recipient_gets = round((amount - fee) * rate, 2)
    delivery = DELIVERY.get((fc, tc), "1-3 business days")

    return {
        "from_currency":  fc,
        "to_currency":    tc,
        "send_amount":    amount,
        "fee":            fee,
        "fee_breakdown":  f"{pct*100:.1f}% + {fc} {fixed:.2f} fixed",
        "exchange_rate":  rate,
        "recipient_gets": recipient_gets,
        "delivery":       delivery,
        "note": "Rates are indicative and locked only when you confirm at wise.com.",
    }


def create_transfer(data: dict) -> dict:
    """Create a new transfer record after validating inputs."""
    db = _load()
    est = estimate_transfer(
        data.get("from_currency",""), data.get("to_currency",""),
        float(data.get("amount", 0))
    )
    if "error" in est:
        return est

    tid = _uid("TW", 6)
    record = {
        "transfer_id":        tid,
        "user_id":            data.get("user_id", ""),
        "user_email":         data.get("user_email", ""),
        "from_currency":      est["from_currency"],
        "to_currency":        est["to_currency"],
        "amount":             data["amount"],
        "fee":                est["fee"],
        "recipient_gets":     est["recipient_gets"],
        "exchange_rate":      est["exchange_rate"],
        "status":             "Awaiting Funds",
        "created_at":         _now(),
        "estimated_delivery": est["delivery"],
        "recipient_name":     data.get("recipient_name", ""),
        "recipient_account":  data.get("recipient_account", ""),
        "delay_reason":       None,
        "troubleshooting_tip":"Please complete your bank transfer to fund this transaction.",
    }
    db["transfers"].append(record)
    _save(db)
    return {"created": True, "transfer_id": tid, **record}


def update_transfer_status(transfer_id: str, new_status: str, note: str = "") -> dict:
    """Update the status of an existing transfer."""
    valid = {"Awaiting Funds","In Transit","Funds converted","Sent","Completed","Delayed","Cancelled"}
    if new_status not in valid:
        return {"error": f"Invalid status '{new_status}'. Valid: {', '.join(sorted(valid))}"}
    db = _load()
    tid = transfer_id.strip().upper()
    for t in db["transfers"]:
        if t["transfer_id"].upper() == tid:
            t["status"] = new_status
            if note:
                t["troubleshooting_tip"] = note
            _save(db)
            return {"updated": True, "transfer_id": tid, "new_status": new_status}
    return {"error": f"Transfer '{tid}' not found."}


# ── TICKET ────────────────────────────────────────────────────────────────

def create_ticket(user_email: str, issue: str,
                  priority: str = "Medium",
                  related_transfer_id: Optional[str] = None) -> dict:
    """Create a new support ticket."""
    db = _load()
    pri = priority.strip().capitalize()
    if pri not in ("Low","Medium","High"): pri = "Medium"

    tid = _uid("TKT", 6)
    record = {
        "ticket_id":            tid,
        "user_id":              next((u["user_id"] for u in db["users"]
                                     if u["email"].lower() == user_email.lower()), ""),
        "user_email":           user_email,
        "issue":                issue,
        "priority":             pri,
        "status":               "Open",
        "created_at":           _now(),
        "updated_at":           _now(),
        "agent_notes":          "",
        "related_transfer_id":  related_transfer_id,
    }
    db["tickets"].append(record)
    _save(db)
    return {
        "created":   True,
        "ticket_id": tid,
        "priority":  pri,
        "status":    "Open",
        "message":   f"Ticket {tid} created. A Wise agent will respond to {user_email} within 1-3 business days.",
    }


def lookup_ticket(ticket_id: str) -> dict:
    """Look up a ticket by ID."""
    db = _load()
    tid = ticket_id.strip().upper()
    t = next((x for x in db["tickets"] if x["ticket_id"].upper() == tid), None)
    if not t:
        return {"found": False, "error": f"No ticket found with ID '{tid}'."}
    return {"found": True, **t}


def list_tickets(user_email: str) -> dict:
    """List all tickets for a user."""
    db = _load()
    email = user_email.strip().lower()
    tickets = [t for t in db["tickets"] if t["user_email"].lower() == email]
    if not tickets:
        return {"found": False, "error": f"No tickets found for '{email}'."}
    return {
        "found": True,
        "count": len(tickets),
        "tickets": sorted(tickets, key=lambda x: x["created_at"], reverse=True)
    }


def update_ticket(ticket_id: str, updates: dict) -> dict:
    """Update status, priority, or agent_notes on an existing ticket."""
    db = _load()
    tid = ticket_id.strip().upper()
    for t in db["tickets"]:
        if t["ticket_id"].upper() == tid:
            for k in ("status","priority","agent_notes"):
                if k in updates:
                    t[k] = updates[k]
            t["updated_at"] = _now()
            _save(db)
            return {"updated": True, "ticket_id": tid, **t}
    return {"error": f"Ticket '{tid}' not found."}


# ── CARD ──────────────────────────────────────────────────────────────────

def get_card(user_email: str) -> dict:
    """Get all cards for a user."""
    db = _load()
    email = user_email.strip().lower()
    cards = [c for c in db["cards"] if c["user_email"].lower() == email]
    if not cards:
        return {"found": False, "error": f"No cards found for '{email}'."}
    return {"found": True, "count": len(cards), "cards": cards}


def freeze_card(user_email: str, last_four: Optional[str] = None) -> dict:
    """Freeze a card. Optionally specify last 4 digits if user has multiple cards."""
    db = _load()
    email = user_email.strip().lower()
    for c in db["cards"]:
        if c["user_email"].lower() != email: continue
        if last_four and c["last_four"] != last_four: continue
        if c["status"] == "Frozen":
            return {"already_frozen": True, "card_id": c["card_id"],
                    "message": f"Card ending ****{c['last_four']} is already frozen."}
        if c["status"] in ("Cancelled","Replacement_Requested"):
            return {"error": f"Card ****{c['last_four']} is {c['status']} and cannot be frozen."}
        c["status"] = "Frozen"
        c["frozen_at"] = _now()
        _save(db)
        return {
            "success": True, "action": "frozen",
            "card_id": c["card_id"], "last_four": c["last_four"],
            "message": (f"Card ****{c['last_four']} has been frozen. "
                        "All card payments are now blocked. "
                        "Your account balance and currencies remain unaffected."),
        }
    return {"error": f"No active card found for '{email}'" +
            (f" ending in ****{last_four}" if last_four else "") + "."}


def unfreeze_card(user_email: str, last_four: Optional[str] = None) -> dict:
    """Unfreeze a previously frozen card."""
    db = _load()
    email = user_email.strip().lower()
    for c in db["cards"]:
        if c["user_email"].lower() != email: continue
        if last_four and c["last_four"] != last_four: continue
        if c["status"] != "Frozen":
            return {"not_frozen": True, "card_id": c["card_id"],
                    "message": f"Card ****{c['last_four']} is not frozen (current status: {c['status']})."}
        c["status"] = "Active"
        c["frozen_at"] = None
        _save(db)
        return {
            "success": True, "action": "unfrozen",
            "card_id": c["card_id"], "last_four": c["last_four"],
            "message": f"Card ****{c['last_four']} has been unfrozen and is ready to use.",
        }
    return {"error": f"No frozen card found for '{email}'."}


def request_replacement(user_email: str, reason: str,
                         delivery_address: str,
                         last_four: Optional[str] = None) -> dict:
    """Cancel the existing card and request a replacement to a delivery address."""
    db = _load()
    email = user_email.strip().lower()
    for c in db["cards"]:
        if c["user_email"].lower() != email: continue
        if last_four and c["last_four"] != last_four: continue
        if c["status"] == "Replacement_Requested":
            return {"error": f"A replacement for card ****{c['last_four']} is already in progress (ref: {c.get('replacement_id','')})."}
        old_four = c["last_four"]
        c["status"] = "Replacement_Requested"
        c["replacement_reason"] = reason
        c["replacement_address"] = delivery_address
        c["replacement_requested_at"] = _now()
        rpl_id = _uid("RPL", 6)
        c["replacement_id"] = rpl_id
        _save(db)
        return {
            "success": True,
            "replacement_id":   rpl_id,
            "card_id":          c["card_id"],
            "old_last_four":    old_four,
            "reason":           reason,
            "delivery_address": delivery_address,
            "message": (f"Replacement card requested (ref: {rpl_id}). "
                        f"Card ****{old_four} is now cancelled. "
                        f"Your new card will be delivered to: {delivery_address} "
                        "in 5-10 business days."),
        }
    return {"error": f"No eligible card found for '{email}'."}


def order_new_card(user_email: str, card_type: str,
                   delivery_address: str) -> dict:
    """Order a brand-new card for an existing user."""
    db = _load()
    email = user_email.strip().lower()
    user = next((u for u in db["users"] if u["email"].lower() == email), None)
    if not user:
        return {"error": f"No account found for '{email}'."}
    if not user.get("verified"):
        return {"error": "Your account needs to be verified before you can order a card. "
                         "Please complete identity verification first."}

    ctype = card_type.strip().capitalize()
    if ctype not in ("Physical","Virtual"):
        ctype = "Physical"

    # Generate mock last four
    last_four = str(random.randint(1000,9999))
    card_id   = _uid("CARD", 4)
    order_id  = _uid("ORD", 6)

    record = {
        "card_id":                  card_id,
        "user_id":                  user["user_id"],
        "user_email":               email,
        "last_four":                last_four,
        "status":                   "Active" if ctype=="Virtual" else "Ordered",
        "card_type":                ctype,
        "frozen_at":                None,
        "replacement_reason":       None,
        "replacement_address":      delivery_address if ctype=="Physical" else None,
        "replacement_requested_at": None,
        "replacement_id":           None,
    }
    db["cards"].append(record)
    _save(db)

    msg = (f"Virtual card ****{last_four} is now active and ready to use."
           if ctype == "Virtual"
           else f"Physical card ****{last_four} ordered (ref: {order_id}). "
                f"Delivery to {delivery_address} in 5-10 business days.")
    return {
        "success":    True,
        "order_id":   order_id,
        "card_id":    card_id,
        "card_type":  ctype,
        "last_four":  last_four,
        "status":     record["status"],
        "message":    msg,
    }


# ── Smoke test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== lookup_transfer ===")
    print(json.dumps(lookup_transfer("TW-001234"), indent=2))
    print("\n=== list_transfers (alice) ===")
    r = list_transfers("alice@example.com")
    print(f"Found {r['count']} transfers:")
    for t in r["transfers"]:
        print(f"  {t['transfer_id']} | {t['status']} | {t['from_currency']}→{t['to_currency']} {t['amount']}")
    print("\n=== estimate_transfer ===")
    print(json.dumps(estimate_transfer("CAD","PHP",800), indent=2))
    print("\n=== get_card (alice) ===")
    print(json.dumps(get_card("alice@example.com"), indent=2))
    print("\n=== list_tickets (carol) ===")
    lt = list_tickets("carol@example.com")
    for t in lt["tickets"]:
        print(f"  {t['ticket_id']} | {t['status']} | {t['issue'][:50]}")
    print("\n=== lookup_transfer (NOT FOUND) ===")
    print(json.dumps(lookup_transfer("TW-999999"), indent=2))
