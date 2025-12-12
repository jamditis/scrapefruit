"""ExtractionRule repository for database operations."""

from typing import Optional, List
from uuid import uuid4

from database.connection import get_session
from models.rule import ExtractionRule


class RuleRepository:
    """Repository for ExtractionRule CRUD operations."""

    def create_rule(
        self,
        job_id: str,
        name: str,
        selector_type: str,
        selector_value: str,
        attribute: Optional[str] = None,
        transform: Optional[str] = None,
        is_required: bool = False,
        is_list: bool = False,
        template_id: Optional[str] = None,
    ) -> ExtractionRule:
        """Create a new extraction rule."""
        session = get_session()
        try:
            # Get max display order for this job
            existing = session.query(ExtractionRule).filter(
                ExtractionRule.job_id == job_id
            ).all()
            max_order = max([r.display_order for r in existing], default=-1)

            rule = ExtractionRule(
                id=str(uuid4()),
                job_id=job_id,
                template_id=template_id,
                name=name,
                selector_type=selector_type,
                selector_value=selector_value,
                attribute=attribute,
                transform=transform,
                is_required=is_required,
                is_list=is_list,
                display_order=max_order + 1,
            )
            session.add(rule)
            session.commit()
            session.refresh(rule)
            return rule
        except Exception:
            session.rollback()
            raise

    def get_rule(self, rule_id: str) -> Optional[ExtractionRule]:
        """Get a rule by ID."""
        session = get_session()
        return session.query(ExtractionRule).filter(ExtractionRule.id == rule_id).first()

    def list_rules(
        self,
        job_id: Optional[str] = None,
        template_id: Optional[str] = None,
    ) -> List[ExtractionRule]:
        """List rules for a job or template."""
        session = get_session()
        query = session.query(ExtractionRule)

        if job_id:
            query = query.filter(ExtractionRule.job_id == job_id)
        if template_id:
            query = query.filter(ExtractionRule.template_id == template_id)

        return query.order_by(ExtractionRule.display_order).all()

    def update_rule(self, rule_id: str, **kwargs) -> Optional[ExtractionRule]:
        """Update rule fields."""
        session = get_session()
        try:
            rule = session.query(ExtractionRule).filter(ExtractionRule.id == rule_id).first()
            if not rule:
                return None

            for key, value in kwargs.items():
                if hasattr(rule, key):
                    setattr(rule, key, value)

            session.commit()
            session.refresh(rule)
            return rule
        except Exception:
            session.rollback()
            raise

    def delete_rule(self, rule_id: str) -> bool:
        """Delete a rule."""
        session = get_session()
        try:
            rule = session.query(ExtractionRule).filter(ExtractionRule.id == rule_id).first()
            if rule:
                session.delete(rule)
                session.commit()
                return True
            return False
        except Exception:
            session.rollback()
            raise

    def reorder_rules(self, job_id: str, rule_ids: List[str]) -> List[ExtractionRule]:
        """Reorder rules for a job."""
        session = get_session()
        try:
            rules = []
            for i, rule_id in enumerate(rule_ids):
                rule = session.query(ExtractionRule).filter(
                    ExtractionRule.id == rule_id,
                    ExtractionRule.job_id == job_id,
                ).first()
                if rule:
                    rule.display_order = i
                    rules.append(rule)

            session.commit()
            return rules
        except Exception:
            session.rollback()
            raise

    def copy_rules_from_template(self, template_id: str, job_id: str) -> List[ExtractionRule]:
        """Copy rules from a template to a job."""
        session = get_session()
        try:
            template_rules = self.list_rules(template_id=template_id)
            new_rules = []

            for tr in template_rules:
                rule = ExtractionRule(
                    id=str(uuid4()),
                    job_id=job_id,
                    template_id=None,  # Detach from template
                    name=tr.name,
                    selector_type=tr.selector_type,
                    selector_value=tr.selector_value,
                    attribute=tr.attribute,
                    transform=tr.transform,
                    is_required=tr.is_required,
                    is_list=tr.is_list,
                    display_order=tr.display_order,
                )
                session.add(rule)
                new_rules.append(rule)

            session.commit()
            for rule in new_rules:
                session.refresh(rule)
            return new_rules
        except Exception:
            session.rollback()
            raise
