import threading
from unittest.mock import Mock, patch
import pytest
from app.workflow.scheduler import run_forever, handle_notification


def test_scheduler_rejects_invalid_interval():
    with pytest.raises(ValueError,match='INTERVAL'):
        run_forever('dsn','worker','2026-11-20',interval=0)


def test_scheduler_retries_poll_error_without_crashing():
    with patch('app.workflow.scheduler.poll_once',side_effect=RuntimeError('transient')) as poll:
        assert run_forever('dsn','worker','2026-11-20',interval=0.001,max_cycles=2)==2
        assert poll.call_count==2


def test_notification_rejects_unexpected_topic():
    with pytest.raises(ValueError,match='UNSUPPORTED'):
        handle_notification(None,{'topic':'erp.write'},'2026-11-20')


def test_stale_notification_does_not_advance():
    with patch('app.workflow.scheduler.read',return_value={'version':4,'state':'CALCULATING'}):
        result=handle_notification(None,{'topic':'workflow.state_changed','workflow_id':'WF1','payload':{'version':3}},'2026-11-20')
    assert result['stale'] is True
