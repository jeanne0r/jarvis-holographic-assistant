"""System-enforced shared reservations; child calls do not create new budgets."""
from datetime import datetime
import time
from zoneinfo import ZoneInfo
from ..store import uid


def create(memory, principal, *, monthly_remote_micros=0, token_limit=65536):
    principal.require('budget_admin')
    if type(monthly_remote_micros) is not int or not 0 <= monthly_remote_micros <= 10_000_000 or type(token_limit) is not int or not 0 <= token_limit <= 1000000:
        raise ValueError('Approved host budget limits')
    bid = uid()
    with memory.db: memory.db.execute('INSERT INTO p2_budgets VALUES(?,?,?,?)', (bid, principal.name, monthly_remote_micros, token_limit))
    return bid


def reserve(memory, principal, budget_id, mission_id, model, *, tokens, remote_micros=0, parent_call=None):
    principal.require('metered_caller')
    if type(tokens) is not int or tokens < 0 or type(remote_micros) is not int or remote_micros < 0: raise ValueError('Reservation bounds')
    month = datetime.now(ZoneInfo('Europe/Zurich')).strftime('%Y-%m')
    with memory.db:
        memory.db.execute('BEGIN IMMEDIATE')
        budget = memory.db.execute('SELECT * FROM p2_budgets WHERE id=? AND owner=?', (budget_id, principal.name)).fetchone()
        if not budget: raise PermissionError('Budget ownership')
        if parent_call and not memory.db.execute('SELECT 1 FROM p2_usage WHERE id=? AND budget_id=?', (parent_call, budget_id)).fetchone(): raise PermissionError('Child budget mismatch')
        usage = memory.db.execute("SELECT coalesce(sum(CASE WHEN state='not_started' THEN 0 WHEN state='settled' THEN used_tokens ELSE reserved_tokens END),0),coalesce(sum(CASE WHEN state='not_started' THEN 0 ELSE coalesce(actual_remote_micros,reserved_remote_micros) END),0) FROM p2_usage WHERE budget_id=? AND month=?", (budget_id, month)).fetchone()
        if usage[0] + tokens > budget['token_limit'] or usage[1] + remote_micros > budget['monthly_remote_micros']:
            raise PermissionError('System budget exhausted')
        cid = uid()
        memory.db.execute('INSERT INTO p2_usage VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)', (cid, budget_id, month, mission_id, parent_call, model, tokens, None, remote_micros, None, None, 'reserved', time.time()))
        return cid


def settle(memory, principal, call_id, *, used_tokens, actual_remote_micros, latency):
    principal.require('metered_caller')
    with memory.db:
        row = memory.db.execute('SELECT u.* FROM p2_usage u JOIN p2_budgets b ON b.id=u.budget_id WHERE u.id=? AND b.owner=?', (call_id, principal.name)).fetchone()
        if not row or row['state'] != 'reserved': raise ValueError('Call already settled or inaccessible')
        if not 0 <= used_tokens <= row['reserved_tokens'] or not 0 <= actual_remote_micros <= row['reserved_remote_micros'] or latency < 0:
            raise ValueError('Usage exceeds reservation; reconciliation required')
        memory.db.execute("UPDATE p2_usage SET used_tokens=?,actual_remote_micros=?,latency=?,state='settled' WHERE id=?", (used_tokens, actual_remote_micros, latency, call_id))
