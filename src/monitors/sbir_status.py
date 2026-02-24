"""Monitor SBIR/STTR program authorization status.

CRITICAL: SBIR/STTR programs expired Sept 30, 2025.
This monitor tracks reauthorization status and alerts when programs reopen.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from src.scrapers.base_scraper import BaseScraper
from src.utils.logger import setup_logger

logger = setup_logger("sbir_status")

SBIR_CHECK_URLS = {
    "main": "https://www.sbir.gov/",
    "nsf": "https://seedfund.nsf.gov/",
    "doe": "https://science.osti.gov/sbir",
    "congress": "https://www.congress.gov/bill/119th-congress",
}

# Keywords indicating reauthorization or active status
ACTIVE_KEYWORDS = [
    "accepting applications",
    "open solicitation",
    "submit proposal",
    "apply now",
    "reauthorized",
    "reauthorization signed",
    "program extended",
    "solicitation open",
    "new solicitation",
]

SUSPENDED_KEYWORDS = [
    "expired",
    "not accepting",
    "authorization lapsed",
    "program suspended",
    "temporarily closed",
    "pending reauthorization",
    "awaiting reauthorization",
]


class SBIRStatusMonitor(BaseScraper):
    """Monitor SBIR/STTR program status across agencies.

    Checks if programs are accepting applications and alerts
    on any status changes, especially reauthorization.
    """

    def __init__(self):
        super().__init__(rate_limit_calls=5, rate_limit_period=60)

    @property
    def name(self) -> str:
        return "sbir_monitor"

    def search(self, keywords: list[str] | None = None):
        """Not used — this is a monitor, not a scraper."""
        return []

    def check_status(self) -> dict:
        """Check SBIR/STTR status across all agencies.

        Returns:
            Status dict with per-agency status and overall assessment.
        """
        status = {
            "last_checked": datetime.now().isoformat(),
            "overall_status": "SUSPENDED",
            "reauthorized": False,
            "programs": {
                "NSF_SBIR": {
                    "agency": "National Science Foundation",
                    "status": "SUSPENDED",
                    "reason": "Congressional authorization expired Sept 30, 2025",
                    "accepting_apps": False,
                    "url": "https://seedfund.nsf.gov/",
                    "last_checked": datetime.now().isoformat(),
                },
                "DOE_SBIR": {
                    "agency": "Department of Energy",
                    "status": "SUSPENDED",
                    "reason": "Authorization expired Oct 1, 2025",
                    "accepting_apps": False,
                    "url": "https://science.osti.gov/sbir",
                    "last_checked": datetime.now().isoformat(),
                },
                "NIH_SBIR": {
                    "agency": "National Institutes of Health",
                    "status": "SUSPENDED",
                    "reason": "Authorization expired",
                    "accepting_apps": False,
                    "url": "https://sbir.nih.gov/",
                    "last_checked": datetime.now().isoformat(),
                },
                "DoD_SBIR": {
                    "agency": "Department of Defense",
                    "status": "PENDING_REAUTH",
                    "reason": "Some programs may continue under existing obligations",
                    "accepting_apps": False,
                    "url": "https://www.dodsbirsttr.mil/",
                    "last_checked": datetime.now().isoformat(),
                },
            },
            "notes": [
                "SBIR/STTR authorization expired September 30, 2025",
                "Reauthorization requires Congressional action",
                "Monitor congress.gov for reauthorization bills",
                "Some agencies may issue new solicitations once reauthorized",
            ],
        }

        # Check live status of key sites
        for site_key, url in SBIR_CHECK_URLS.items():
            try:
                detected = self._check_site(url)
                if detected.get("active"):
                    status["reauthorized"] = True
                    status["overall_status"] = "REAUTHORIZED"
                    logger.info("[sbir] REAUTHORIZATION DETECTED at %s!", url)

                    # Update relevant programs
                    for prog_key, prog in status["programs"].items():
                        if detected.get("active"):
                            prog["status"] = "ACTIVE"
                            prog["accepting_apps"] = True
                            prog["reason"] = "Program reauthorized"

            except Exception as e:
                logger.warning("[sbir] Could not check %s: %s", url, e)

        return status

    def _check_site(self, url: str) -> dict:
        """Check a single site for SBIR status indicators."""
        try:
            response = self._fetch(url)
            text = response.text.lower()

            is_active = any(kw in text for kw in ACTIVE_KEYWORDS)
            is_suspended = any(kw in text for kw in SUSPENDED_KEYWORDS)

            return {
                "url": url,
                "active": is_active and not is_suspended,
                "suspended_signals": is_suspended,
                "active_signals": is_active,
                "checked_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error("[sbir] Error checking %s: %s", url, e)
            return {"url": url, "active": False, "error": str(e)}

    def check_for_changes(self, previous_status_path: str = "data/sbir_status.json") -> dict | None:
        """Compare current status with previous and return changes.

        Returns:
            Dict with changes if any, None if no changes.
        """
        current = self.check_status()

        # Load previous status
        try:
            with open(previous_status_path) as f:
                previous = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            previous = {"overall_status": "UNKNOWN"}

        # Detect changes
        prev_overall = previous.get("overall_status", "UNKNOWN")
        curr_overall = current["overall_status"]

        if prev_overall != curr_overall:
            return {
                "changed": True,
                "previous_status": prev_overall,
                "new_status": curr_overall,
                "reauthorized": current["reauthorized"],
                "message": (
                    f"SBIR/STTR status changed: {prev_overall} → {curr_overall}"
                ),
                "current_status": current,
            }

        return None


def main():
    parser = argparse.ArgumentParser(description="Check SBIR/STTR program status")
    parser.add_argument("--output", default="data/sbir_status.json")
    parser.add_argument("--check-changes", action="store_true", help="Check for changes vs previous")
    args = parser.parse_args()

    monitor = SBIRStatusMonitor()

    if args.check_changes:
        changes = monitor.check_for_changes(args.output)
        if changes:
            print(f"STATUS CHANGE: {changes['message']}")
            if changes["reauthorized"]:
                print("SBIR/STTR REAUTHORIZED — ALERT REQUIRED!")
        else:
            print("No status changes detected")

    status = monitor.check_status()

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(status, f, indent=2)

    print(f"SBIR status: {status['overall_status']}")
    for prog_key, prog in status["programs"].items():
        accepting = "YES" if prog["accepting_apps"] else "NO"
        print(f"  {prog_key}: {prog['status']} (accepting: {accepting})")

    monitor.close()


if __name__ == "__main__":
    main()
