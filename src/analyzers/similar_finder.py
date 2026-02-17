"""Similar grants finder — finds grants similar to a given one."""

from src.database.models import Grant, get_session
from src.utils.logger import setup_logger
from src.utils.text_processor import TextProcessor

logger = setup_logger("similar_finder")


class SimilarFinder:
    """Find grants similar to a given grant based on text similarity and metadata."""

    def __init__(self, session=None):
        self.session = session or get_session()

    def find_similar(self, grant_id: int, limit: int = 5) -> list[dict]:
        """Find grants similar to the specified grant.

        Uses a combination of:
        - Grant type matching
        - Keyword overlap in title/description
        - Funder similarity
        - Amount range overlap
        - Industry tag overlap

        Args:
            grant_id: ID of the reference grant.
            limit: Maximum number of similar grants to return.

        Returns:
            List of dicts with grant info and similarity score.
        """
        reference = self.session.query(Grant).filter(Grant.id == grant_id).first()
        if not reference:
            logger.warning("Grant %d not found", grant_id)
            return []

        # Get all other active grants
        candidates = (
            self.session.query(Grant)
            .filter(Grant.id != grant_id, Grant.status.in_(["found", "qualified"]))
            .all()
        )

        scored: list[tuple[Grant, float]] = []
        ref_text = f"{reference.title} {reference.description or ''}".lower()
        ref_tags = set(reference.industry_tags or [])

        for candidate in candidates:
            score = self._similarity_score(reference, candidate, ref_text, ref_tags)
            scored.append((candidate, score))

        # Sort by similarity score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        results = []
        for grant, sim_score in scored[:limit]:
            results.append({
                "id": grant.id,
                "title": grant.title,
                "funder": grant.funder,
                "fit_score": grant.fit_score,
                "amount": grant.amount_display,
                "deadline": str(grant.deadline) if grant.deadline else "N/A",
                "similarity": int(sim_score * 100),
                "url": grant.url,
            })

        return results

    def _similarity_score(self, ref: Grant, candidate: Grant, ref_text: str, ref_tags: set) -> float:
        """Calculate similarity between two grants."""
        score = 0.0

        # Same grant type (0.2)
        if ref.grant_type and ref.grant_type == candidate.grant_type:
            score += 0.2

        # Tag overlap (0.3)
        cand_tags = set(candidate.industry_tags or [])
        if ref_tags and cand_tags:
            overlap = len(ref_tags & cand_tags) / len(ref_tags | cand_tags)
            score += overlap * 0.3

        # Keyword overlap in title/description (0.3)
        cand_text = f"{candidate.title} {candidate.description or ''}".lower()
        ref_words = set(ref_text.split()) - {"the", "a", "an", "and", "or", "for", "of", "in", "to", "is"}
        cand_words = set(cand_text.split()) - {"the", "a", "an", "and", "or", "for", "of", "in", "to", "is"}
        if ref_words and cand_words:
            word_overlap = len(ref_words & cand_words) / max(len(ref_words), len(cand_words))
            score += word_overlap * 0.3

        # Amount range similarity (0.1)
        if ref.amount_max and candidate.amount_max:
            ratio = min(ref.amount_max, candidate.amount_max) / max(ref.amount_max, candidate.amount_max)
            score += ratio * 0.1

        # Same funder bonus (0.1)
        if ref.funder and candidate.funder and ref.funder.lower() == candidate.funder.lower():
            score += 0.1

        return min(1.0, score)

    def close(self):
        self.session.close()
