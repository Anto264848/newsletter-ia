"""Session HTTP partagée : User-Agent explicite, timeouts et retries automatiques."""
from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Identification honnête d'un lecteur RSS automatisé. Si un site refuse ce robot, on respecte son choix :
# la source est simplement ignorée (et peut être désactivée dans config/sources.yaml).
USER_AGENT = "Mozilla/5.0 (compatible; NewsletterIA-Bot/1.0; RSS reader)"


def make_session(retries: int = 3) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=retries,
        connect=retries,
        read=retries,
        backoff_factor=1.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "HEAD"}),
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": (
                "application/rss+xml, application/atom+xml, application/xml, text/xml, "
                "application/json;q=0.9, */*;q=0.8"
            ),
            "Accept-Language": "fr,en;q=0.8",
        }
    )
    return session
