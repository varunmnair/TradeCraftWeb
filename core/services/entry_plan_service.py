"""Entry planning orchestration service."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from core.dynamic_avg import DynamicAveragingPlanner
from core.multilevel_entry import MultiLevelEntryPlanner
from core.runtime.session_registry import SessionRegistry
from core.utils import sanitize_for_json

LOGGER = logging.getLogger("tradecraftx.entry_plan")

STRATEGY_TYPE_MULTI_LEVEL = "multi_level"
STRATEGY_TYPE_DYNAMIC_AVERAGING = "dynamic_averaging"


class EntryPlanService:
    def __init__(self, registry: SessionRegistry) -> None:
        self._registry = registry

    def list_entry_levels(self, session_id: str) -> Dict[str, Any]:
        context = self._get_context(session_id)
        entry_levels = context.session_cache.get_entry_levels()
        return {"items": sanitize_for_json(entry_levels)}

    def _get_strategy_type_from_job_type(self, job_type: str) -> Optional[str]:
        if job_type == "plan_generate":
            return STRATEGY_TYPE_MULTI_LEVEL
        elif job_type == "dynamic_avg_generate":
            return STRATEGY_TYPE_DYNAMIC_AVERAGING
        return None

    def generate_plan(
        self,
        session_id: str,
        strategy_type: str,
        *,
        apply_risk: bool = False,
    ) -> Dict[str, Any]:
        context = self._get_context(session_id)
        session_cache = context.session_cache

        session_cache.refresh_entry_levels()

        cmp_manager = session_cache.get_cmp_manager()
        holdings = session_cache.get_holdings()
        entry_levels = session_cache.get_entry_levels()
        gtt_cache = session_cache.get_gtt_cache()

        LOGGER.info(f"generate_plan: strategy={strategy_type}, entry_levels count={len(entry_levels)}")
        LOGGER.info(f"generate_plan: holdings count={len(holdings)}")
        LOGGER.info(f"generate_plan: gtt_cache count={len(gtt_cache)}")

        if not entry_levels:
            LOGGER.warning(
                "generate_plan: NO entry levels found! Entry strategies are broker-specific."
            )

        if strategy_type == STRATEGY_TYPE_MULTI_LEVEL:
            strategy = MultiLevelEntryPlanner(
                context.broker,
                cmp_manager,
                holdings,
                entry_levels,
                gtt_cache,
            )
            candidates = strategy.identify_candidates()
            LOGGER.info(f"generate_plan: multi_level candidates identified={len(candidates)}")

            plan = strategy.generate_plan(candidates, apply_risk_management=apply_risk)
            LOGGER.info(f"generate_plan: multi_level plan generated={len(plan.get('plan', []))}")

            all_skipped = plan.get("skipped", []) + plan.get("pending_cmp", [])
            return {
                "strategy_type": strategy_type,
                "plan": sanitize_for_json(plan.get("plan", [])),
                "skipped": sanitize_for_json(all_skipped),
            }

        elif strategy_type == STRATEGY_TYPE_DYNAMIC_AVERAGING:
            planner = DynamicAveragingPlanner(
                broker=context.broker,
                cmp_manager=cmp_manager,
                holdings=holdings,
                entry_levels=entry_levels,
                gtt_cache=gtt_cache,
                trigger_offset_factor=0.3,
            )
            candidates = planner.identify_candidates()
            LOGGER.info(f"generate_plan: dynamic_averaging candidates identified={len(candidates)}")

            plan = planner.generate_plan(candidates, apply_risk_management=apply_risk)
            LOGGER.info(f"generate_plan: dynamic_averaging plan generated={len(plan.get('plan', []))}")

            return {
                "strategy_type": strategy_type,
                "plan": sanitize_for_json(plan.get("plan", [])),
                "skipped": sanitize_for_json(plan.get("skipped", [])),
            }

        raise ValueError(f"Unknown strategy type: {strategy_type}")

    def apply_risk_to_plan(
        self,
        session_id: str,
        strategy_type: str,
        draft_plan: list,
    ) -> Dict[str, Any]:
        context = self._get_context(session_id)
        session_cache = context.session_cache

        session_cache.refresh_entry_levels()

        cmp_manager = session_cache.get_cmp_manager()
        holdings = session_cache.get_holdings()
        entry_levels = session_cache.get_entry_levels()
        gtt_cache = session_cache.get_gtt_cache()

        LOGGER.info(f"apply_risk_to_plan: strategy={strategy_type}, plan count={len(draft_plan)}")

        if strategy_type == STRATEGY_TYPE_MULTI_LEVEL:
            strategy = MultiLevelEntryPlanner(
                context.broker,
                cmp_manager,
                holdings,
                entry_levels,
                gtt_cache,
            )
            result = strategy.apply_risk_to_plan(draft_plan)

            all_skipped = result.get("skipped", []) + result.get("pending_cmp", [])
            return {
                "strategy_type": strategy_type,
                "plan": sanitize_for_json(result.get("plan", [])),
                "skipped": sanitize_for_json(all_skipped),
            }

        elif strategy_type == STRATEGY_TYPE_DYNAMIC_AVERAGING:
            planner = DynamicAveragingPlanner(
                broker=context.broker,
                cmp_manager=cmp_manager,
                holdings=holdings,
                entry_levels=entry_levels,
                gtt_cache=gtt_cache,
                trigger_offset_factor=0.3,
            )
            result = planner.generate_plan(draft_plan, apply_risk_management=True)

            return {
                "strategy_type": strategy_type,
                "plan": sanitize_for_json(result.get("plan", [])),
                "skipped": sanitize_for_json(result.get("skipped", [])),
            }

        raise ValueError(f"Unknown strategy type: {strategy_type}")

    def purge_plans(self, session_id: str, strategy_type: Optional[str] = None) -> Dict[str, Any]:
        from db.database import SessionLocal
        from sqlalchemy.sql import func
        from db.models import Job

        db_session = SessionLocal()

        try:
            query = db_session.query(Job).filter(Job.session_id == session_id)

            if strategy_type == STRATEGY_TYPE_MULTI_LEVEL:
                query = query.filter(Job.job_type == "plan_generate")
            elif strategy_type == STRATEGY_TYPE_DYNAMIC_AVERAGING:
                query = query.filter(Job.job_type == "dynamic_avg_generate")
            else:
                query = query.filter(
                    Job.job_type.in_(["plan_generate", "dynamic_avg_generate"])
                )

            jobs = query.all()
            count = len(jobs)

            for job in jobs:
                job.status = "purged"
                job.result_json = None
                job.updated_at = func.now()

            db_session.commit()

            LOGGER.info(f"purge_plans: purged {count} jobs for session {session_id}")
            return {"purged_count": count, "session_id": session_id}

        except Exception as e:
            db_session.rollback()
            LOGGER.error(f"purge_plans: failed to purge plans: {e}")
            raise
        finally:
            db_session.close()

    def _get_context(self, session_id: str):
        context = self._registry.get_session(session_id)
        if not context:
            raise ValueError("Invalid or expired session_id")
        return context
