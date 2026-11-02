"""Read-only ERP compatibility adapter. No silent writes or synthetic DB fallbacks.

Legacy order_id is preserved as the root ID. V1.1 line IDs are scoped to the
order, never represented as fake root orders in persisted genealogy.
"""
from .models import SalesOrder, OrderLine, OrderScope

class OrderNotConfirmed(ValueError):
    pass

class OrderNotFound(ValueError):
    pass

def from_legacy_row(row):
    # SQL contract: order_id, product_id, quantity, due_date, priority, status, version
    order_id, product_id, qty, due_date, priority, status, version = row
    return SalesOrder(order_id=order_id, due_date=due_date, status=status,
        priority=priority, version=version, source='legacy',
        lines=[OrderLine(line_no=1, product_id=product_id, quantity=qty)])

def from_v11_rows(header, lines):
    # Header: order_id, due_date, priority, status, version
    # Lines: line_no, product_id, quantity
    order_id, due_date, priority, status, version = header
    return SalesOrder(order_id=order_id, due_date=due_date, priority=priority,
        status=status, version=version, source='v11',
        lines=[OrderLine(line_no=r[0],product_id=r[1],quantity=r[2]) for r in lines])

def select_orders(orders, scope: OrderScope):
    if scope.mode == 'global':
        selected = [o for o in orders if o.status == 'CONFIRMED']
    else:
        by_id = {o.order_id: o for o in orders}
        missing = sorted(set(scope.order_ids) - set(by_id))
        if missing: raise OrderNotFound(','.join(missing))
        selected = [by_id[x] for x in scope.order_ids]
        if any(o.status != 'CONFIRMED' for o in selected):
            raise OrderNotConfirmed('ORDER_NOT_CONFIRMED')
    return sorted(selected,key=lambda o:(o.due_date,-o.priority,o.order_id))

def read_legacy_orders(conn, status=None, limit=50, offset=0):
    if not 1 <= limit <= 100 or offset < 0: raise ValueError('INVALID_PAGINATION')
    if status is not None and status not in ('DRAFT','CONFIRMED','CANCELLED'):
        raise ValueError('INVALID_ORDER_STATUS')
    with conn.cursor() as cur:
        cur.execute("""SELECT order_id,product_id,quantity,due_date,priority,status,version
            FROM mock_erp.sales_orders
            WHERE (%s::text IS NULL OR status=%s::text)
            ORDER BY due_date,priority DESC,order_id LIMIT %s OFFSET %s""",
            (status,status,limit,offset))
        return [from_legacy_row(r) for r in cur.fetchall()]

def read_legacy_order(conn, order_id):
    with conn.cursor() as cur:
        cur.execute("""SELECT order_id,product_id,quantity,due_date,priority,status,version
            FROM mock_erp.sales_orders WHERE order_id=%s""",(order_id,))
        row=cur.fetchone()
    if row is None: raise OrderNotFound(order_id)
    return from_legacy_row(row)
