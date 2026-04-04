"""Rate limiting for playlist refresh functionality.

Rules:
1. Limit any single IP to hitting refresh once per minute
2. Refresh blocked while playlist is still processing
3. Any single IP may only refresh 3x per day
4. Admin IPs are whitelisted (bypass all limits)
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Tuple
from app.config import settings


# In-memory storage for rate limiting
# Structure: {ip: {"last_refresh": timestamp, "daily_count": int, "daily_reset": date}}
_rate_limits: Dict[str, dict] = {}


def _get_today() -> str:
    """Get today's date as string for daily reset tracking."""
    return datetime.utcnow().strftime("%Y-%m-%d")


def _get_ip_data(ip: str) -> dict:
    """Get or create rate limit data for an IP."""
    today = _get_today()

    if ip not in _rate_limits:
        _rate_limits[ip] = {
            "last_refresh": 0,
            "daily_count": 0,
            "daily_reset": today
        }

    # Reset daily count if it's a new day
    if _rate_limits[ip]["daily_reset"] != today:
        _rate_limits[ip]["daily_count"] = 0
        _rate_limits[ip]["daily_reset"] = today

    return _rate_limits[ip]


def is_admin(ip: str) -> bool:
    """Check if IP is in admin whitelist."""
    if not settings.admin_ips:
        return False
    admin_list = [x.strip() for x in settings.admin_ips.split(",") if x.strip()]
    return ip in admin_list


def check_refresh_allowed(ip: str) -> Tuple[bool, str]:
    """Check if refresh is allowed for this IP.

    Returns:
        Tuple of (allowed: bool, reason: str)
    """
    # Admins bypass all limits
    if is_admin(ip):
        return True, "admin"

    data = _get_ip_data(ip)
    now = time.time()

    # Check 1: Once per minute
    seconds_since_last = now - data["last_refresh"]
    if seconds_since_last < 60:
        wait_time = int(60 - seconds_since_last)
        return False, f"Rate limited. Try again in {wait_time} seconds."

    # Check 3: Max 3 refreshes per day
    if data["daily_count"] >= 3:
        return False, "Daily refresh limit reached (3/day). Try again tomorrow."

    return True, "ok"


def record_refresh(ip: str) -> None:
    """Record a refresh action for rate limiting."""
    if is_admin(ip):
        return  # Don't track admins

    data = _get_ip_data(ip)
    data["last_refresh"] = time.time()
    data["daily_count"] += 1


def get_refresh_stats(ip: str) -> dict:
    """Get rate limit stats for an IP (for debugging)."""
    if is_admin(ip):
        return {"admin": True, "unlimited": True}

    data = _get_ip_data(ip)
    now = time.time()

    return {
        "daily_count": data["daily_count"],
        "daily_limit": 3,
        "seconds_until_next": max(0, int(60 - (now - data["last_refresh"]))),
        "daily_reset": data["daily_reset"]
    }
