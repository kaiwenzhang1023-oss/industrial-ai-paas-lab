"""M3-02 V0.2 frozen policy contract. This is a local governed tool adapter,
not an MCP wire-protocol server and not an external LLM integration.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping

POLICY_VERSION = 'm3-02-v0.2'

@dataclass(frozen=True)
class ToolRule:
    arguments: tuple[str, ...]
    principals: frozenset[str]
    states: frozenset[str]
    read_only: bool = True

DEFAULT_RULES: Mapping[str, ToolRule] = {
    'order.read': ToolRule(('order_id',), frozenset({'recommendation-agent-v1'}), frozenset({'GENERATING_ADVICE'})),
    'bom.read': ToolRule(('order_id',), frozenset({'recommendation-agent-v1'}), frozenset({'GENERATING_ADVICE'})),
    'inventory.read': ToolRule(('order_id',), frozenset({'recommendation-agent-v1'}), frozenset({'GENERATING_ADVICE'})),
    'mrp.read': ToolRule(('mrp_run_id',), frozenset({'recommendation-agent-v1'}), frozenset({'GENERATING_ADVICE'})),
}

class GovernanceError(ValueError):
    pass

def authorize(ctx, tool, args, *, workflow_state, rules=DEFAULT_RULES):
    rule = rules.get(tool)
    if rule is None or not rule.read_only:
        raise GovernanceError('TOOL_DENIED')
    if ctx.principal not in rule.principals:
        raise GovernanceError('PRINCIPAL_DENIED')
    if workflow_state not in rule.states:
        raise GovernanceError('WORKFLOW_STATE_DENIED')
    if not isinstance(args, dict) or set(args) != set(rule.arguments):
        raise GovernanceError('TOOL_ARGUMENT_SCHEMA_INVALID')
    if any(not isinstance(v, str) or not v for v in args.values()):
        raise GovernanceError('TOOL_ARGUMENT_TYPE_INVALID')
    if tool == 'mrp.read':
        if args['mrp_run_id'] != ctx.mrp_run_id:
            raise GovernanceError('CROSS_RUN_READ_DENIED')
    elif args['order_id'] != ctx.order_id:
        raise GovernanceError('CROSS_ORDER_READ_DENIED')
    return rule

@dataclass(frozen=True)
class ExecutionPolicy:
    version: str = POLICY_VERSION
    max_tool_calls: int = 8
    max_buy_lines: int = 100
    allowed_models: frozenset[str] = frozenset({'offline-contract-v1'})

    def check_model(self, model_id):
        if model_id not in self.allowed_models:
            raise GovernanceError('MODEL_NOT_APPROVED')

    def check_draft(self, draft):
        if len(draft['lines']) > self.max_buy_lines:
            raise GovernanceError('DRAFT_LINE_LIMIT_EXCEEDED')
        if 'HUMAN_REVIEW_REQUIRED' not in draft['risk_flags']:
            raise GovernanceError('HUMAN_REVIEW_FLAG_REQUIRED')
