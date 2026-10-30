-- Idempotent reference seed. Business scenario loaded by Python JSON loader.
INSERT INTO mock_erp.materials(material_id,make_buy,lead_days,moq,lot_multiple) VALUES
('EM-100','MAKE',3,0,1),('ST-100','MAKE',2,0,1),('RT-100','MAKE',2,0,1),('BR-01','BUY',4,10,10),('HS-01','BUY',5,10,10),('SC-01','BUY',3,10,10),('CW-01','BUY',3,10,10),('RC-01','BUY',3,10,10),('SH-01','BUY',3,10,10) ON CONFLICT DO NOTHING;
INSERT INTO mock_erp.sales_orders(order_id,product_id,quantity,due_date,priority,status) VALUES
('SO-2026-001','EM-100',100,'2026-11-30',10,'CONFIRMED'),('SO-2026-002','EM-100',20,'2026-12-03',5,'CONFIRMED') ON CONFLICT DO NOTHING;
INSERT INTO mock_erp.bom_versions(bom_id,version,status,effective_from) VALUES ('EM-100','V1','RELEASED','2026-01-01') ON CONFLICT DO NOTHING;
INSERT INTO mock_erp.bom_items(bom_id,version,line_id,parent_id,component_id,qty_per) VALUES
('EM-100','V1',1,'EM-100','ST-100',1),('EM-100','V1',2,'EM-100','RT-100',1),('EM-100','V1',3,'EM-100','BR-01',2),('EM-100','V1',4,'EM-100','HS-01',1),('EM-100','V1',5,'ST-100','SC-01',1),('EM-100','V1',6,'ST-100','CW-01',1),('EM-100','V1',7,'RT-100','RC-01',1),('EM-100','V1',8,'RT-100','SH-01',1) ON CONFLICT DO NOTHING;
INSERT INTO mock_wms.inventory_balances(material_id,warehouse_id,on_hand,reserved,blocked,snapshot_at) VALUES
('ST-100','WH-A',60,0,0,'2026-10-29T10:00:00+08:00'),('RT-100','WH-A',80,0,0,'2026-10-29T10:00:00+08:00'),('BR-01','WH-A',250,0,0,'2026-10-29T10:00:00+08:00'),('HS-01','WH-A',70,0,0,'2026-10-29T10:00:00+08:00'),('SC-01','WH-A',10,0,0,'2026-10-29T10:00:00+08:00'),('CW-01','WH-A',15,0,0,'2026-10-29T10:00:00+08:00'),('RC-01','WH-A',5,0,0,'2026-10-29T10:00:00+08:00'),('SH-01','WH-A',15,0,0,'2026-10-29T10:00:00+08:00') ON CONFLICT DO NOTHING;
INSERT INTO mock_erp.supply_orders(supply_id,material_id,open_qty,arrival_date) VALUES
('SUP-001','RT-100',5,'2026-11-26'),('SUP-002','HS-01',10,'2026-11-26'),('SUP-003','HS-01',40,'2026-11-29'),('SUP-004','SC-01',15,'2026-11-27'),('SUP-005','CW-01',5,'2026-11-24') ON CONFLICT DO NOTHING;
INSERT INTO mock_mes.production_orders(production_order_id,product_id,planned_qty,status) VALUES ('MO-DEMO-001','EM-100',100,'PLANNED') ON CONFLICT DO NOTHING;
