"""Database query helpers for Grant Hunter AI."""

from datetime import datetime, date, timedelta

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from src.database.models import Grant, Application, Alert, SearchLog, get_session
from src.utils.logger import setup_logger

logger = setup_logger("db_queries")


class GrantQueries:
    """Common database queries for grants and applications."""

    def __init__(self, session: Session | None = None):
        self.session = session or get_session()

    def close(self):
        self.session.close()

    # --- Grant CRUD ---

    def add_grant(self, **kwargs) -> Grant:
        """Add a new grant to the database."""
        grant = Grant(**kwargs)
        self.session.add(grant)
        self.session.commit()
        logger.info("Added grant: %s (fit: %s%%)", grant.title[:60], grant.fit_score)
        return grant

    def get_grant(self, grant_id: int) -> Grant | None:
        return self.session.query(Grant).filter(Grant.id == grant_id).first()

    def grant_exists(self, url: str) -> bool:
        """Check if a grant with this URL already exists."""
        return self.session.query(Grant).filter(Grant.url == url).first() is not None

    def update_grant(self, grant_id: int, **kwargs) -> Grant | None:
        grant = self.get_grant(grant_id)
        if grant:
            for key, value in kwargs.items():
                setattr(grant, key, value)
            grant.updated_at = datetime.utcnow()
            self.session.commit()
        return grant

    def delete_grant(self, grant_id: int) -> bool:
        grant = self.get_grant(grant_id)
        if grant:
            self.session.delete(grant)
            self.session.commit()
            return True
        return False

    # --- Grant Queries ---

    def get_urgent_grants(self, days: int = 7) -> list[Grant]:
        """Get grants with deadlines within N days."""
        cutoff = date.today() + timedelta(days=days)
        return (
            self.session.query(Grant)
            .filter(
                Grant.deadline <= cutoff,
                Grant.deadline >= date.today(),
                Grant.status.in_(["found", "qualified"]),
            )
            .order_by(Grant.deadline)
            .all()
        )

    def get_qualified_grants(self, min_fit: int = 70) -> list[Grant]:
        """Get grants that meet minimum fit score."""
        return (
            self.session.query(Grant)
            .filter(
                Grant.fit_score >= min_fit,
                Grant.status.in_(["found", "qualified"]),
                Grant.deadline >= date.today(),
            )
            .order_by(desc(Grant.fit_score))
            .all()
        )

    def get_pipeline(self) -> dict[str, list[Grant]]:
        """Get grants organized by urgency level."""
        today = date.today()
        active_grants = (
            self.session.query(Grant)
            .filter(
                Grant.status.in_(["found", "qualified"]),
                Grant.deadline >= today,
            )
            .order_by(Grant.deadline)
            .all()
        )

        pipeline = {"urgent": [], "important": [], "planning": []}
        for grant in active_grants:
            days = (grant.deadline - today).days if grant.deadline else 999
            if days <= 7:
                pipeline["urgent"].append(grant)
            elif days <= 30:
                pipeline["important"].append(grant)
            else:
                pipeline["planning"].append(grant)
        return pipeline

    def search_grants(self, keyword: str) -> list[Grant]:
        """Search grants by keyword in title and description."""
        pattern = f"%{keyword}%"
        return (
            self.session.query(Grant)
            .filter(
                (Grant.title.ilike(pattern))
                | (Grant.description.ilike(pattern))
                | (Grant.funder.ilike(pattern))
            )
            .order_by(desc(Grant.fit_score))
            .all()
        )

    def get_similar_grants(self, grant_id: int, limit: int = 5) -> list[Grant]:
        """Find grants similar to the given one (same type/tags)."""
        grant = self.get_grant(grant_id)
        if not grant:
            return []

        query = self.session.query(Grant).filter(
            Grant.id != grant_id,
            Grant.status.in_(["found", "qualified"]),
        )

        if grant.grant_type:
            query = query.filter(Grant.grant_type == grant.grant_type)

        return query.order_by(desc(Grant.fit_score)).limit(limit).all()

    def get_grants_needing_reminder(self, reminder_days: list[int] | None = None) -> list[Grant]:
        """Get grants that need a reminder sent today."""
        if reminder_days is None:
            reminder_days = [14, 7, 3, 1]

        results = []
        today = date.today()
        for days in reminder_days:
            target_deadline = today + timedelta(days=days)
            grants = (
                self.session.query(Grant)
                .filter(
                    Grant.deadline == target_deadline,
                    Grant.status.in_(["found", "qualified"]),
                )
                .all()
            )
            results.extend(grants)
        return results

    # --- Application CRUD ---

    def create_application(self, grant_id: int, **kwargs) -> Application:
        app = Application(grant_id=grant_id, **kwargs)
        self.session.add(app)
        self.session.commit()
        return app

    def get_application(self, app_id: int) -> Application | None:
        return self.session.query(Application).filter(Application.id == app_id).first()

    def get_applications_by_status(self, status: str) -> list[Application]:
        return (
            self.session.query(Application)
            .filter(Application.status == status)
            .order_by(desc(Application.updated_at))
            .all()
        )

    def update_application(self, app_id: int, **kwargs) -> Application | None:
        app = self.get_application(app_id)
        if app:
            for key, value in kwargs.items():
                setattr(app, key, value)
            app.updated_at = datetime.utcnow()
            self.session.commit()
        return app

    # --- Alerts ---

    def create_alert(self, grant_id: int, alert_type: str, urgency: str, message: str) -> Alert:
        alert = Alert(
            grant_id=grant_id,
            alert_type=alert_type,
            urgency=urgency,
            message=message,
            sent_date=datetime.utcnow(),
        )
        self.session.add(alert)
        self.session.commit()
        return alert

    def get_unread_alerts(self) -> list[Alert]:
        return (
            self.session.query(Alert)
            .filter(Alert.read == False)
            .order_by(desc(Alert.sent_date))
            .all()
        )

    # --- Search Logs ---

    def log_search(self, source: str, query: str, results: int, new_found: int, duration: float, errors: str = "") -> SearchLog:
        log = SearchLog(
            source=source,
            search_query=query,
            results_count=results,
            new_grants_found=new_found,
            duration_seconds=duration,
            errors=errors,
        )
        self.session.add(log)
        self.session.commit()
        return log

    # --- Statistics ---

    def get_stats(self) -> dict:
        """Get overall statistics."""
        today = date.today()
        total = self.session.query(func.count(Grant.id)).scalar() or 0
        qualified = (
            self.session.query(func.count(Grant.id))
            .filter(Grant.status == "qualified")
            .scalar() or 0
        )
        active = (
            self.session.query(func.count(Grant.id))
            .filter(Grant.deadline >= today, Grant.status.in_(["found", "qualified"]))
            .scalar() or 0
        )
        apps_submitted = (
            self.session.query(func.count(Application.id))
            .filter(Application.status == "submitted")
            .scalar() or 0
        )
        apps_won = (
            self.session.query(func.count(Application.id))
            .filter(Application.status == "won")
            .scalar() or 0
        )
        total_potential = (
            self.session.query(func.sum(Grant.amount_max))
            .filter(Grant.status.in_(["found", "qualified"]), Grant.deadline >= today)
            .scalar() or 0
        )
        total_won = (
            self.session.query(func.sum(Application.award_amount))
            .filter(Application.status == "won")
            .scalar() or 0
        )

        return {
            "total_found": total,
            "qualified": qualified,
            "active": active,
            "submitted": apps_submitted,
            "won": apps_won,
            "total_potential_usd": total_potential,
            "total_won_usd": total_won,
        }
