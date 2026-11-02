"""Explicit one-shot outbox -> PostgreSQL receipt sink.

No workflow transition, AI invocation, ERP write, or external broker. At-least-once
safe: receipt event_id and message_id are unique. A crash between receipt and
finish is retried idempotently.
"""
import argparse
import json
import os
from app.db.repository import connect
from app.workflow.worker import pump_once


def store_receipt(conn, msg):
    if msg['topic'] != 'workflow.state_changed':
        raise ValueError('UNSUPPORTED_TOPIC')
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute('SELECT event_id FROM platform.workflow_outbox WHERE message_id=%s', (msg['message_id'],))
            row=cur.fetchone()
            if row is None: raise ValueError('MESSAGE_NOT_FOUND')
            event_id=row[0]
            cur.execute('''INSERT INTO platform.outbox_delivery_receipts
                (event_id,message_id,topic) VALUES(%s,%s,%s)
                ON CONFLICT(event_id) DO NOTHING''',(event_id,msg['message_id'],msg['topic']))
            cur.execute('SELECT message_id,topic FROM platform.outbox_delivery_receipts WHERE event_id=%s',(event_id,))
            if cur.fetchone() != (msg['message_id'],msg['topic']):
                raise ValueError('RECEIPT_CONTRACT_CONFLICT')


def dispatch_receipts(conn, limit=100, owner='v1-receipt-sink'):
    return pump_once(conn,lambda m:store_receipt(conn,m),owner=owner,limit=limit)


def main():
    parser=argparse.ArgumentParser(description='Explicit audited local Outbox receipt dispatch (NO workflow advancement)')
    parser.add_argument('--limit',type=int,default=100)
    parser.add_argument('--confirm',action='store_true',help='Required to modify outbox status')
    args=parser.parse_args()
    if not args.confirm: parser.error('Pass --confirm for explicit receipt dispatch; no automatic background worker')
    if not 1<=args.limit<=100: parser.error('limit must be 1..100')
    dsn=os.environ.get('DATABASE_URL')
    if not dsn: parser.error('DATABASE_URL required')
    with connect(dsn) as conn:
        conn.autocommit=True
        results=dispatch_receipts(conn,args.limit)
    print(json.dumps({'receipt_sink':'postgresql_local','outcomes':results},ensure_ascii=False))

if __name__=='__main__': main()
