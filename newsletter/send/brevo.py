"""Envoi via l'API Brevo (offre gratuite) : création d'une campagne vers la liste d'abonnés, puis envoi immédiat.

Documentation : https://developers.brevo.com/reference/create-email-campaign
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable

import requests

log = logging.getLogger(__name__)

API = "https://api.brevo.com/v3"
SENT_STATUSES = {"sent", "queued", "in_process", "inprocess", "archive", "scheduled"}


class BrevoError(Exception):
    pass


class BrevoClient:
    def __init__(
        self,
        api_key: str,
        session: requests.Session | None = None,
        timeout: int = 30,
        retries: int = 3,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.session = session or requests.Session()
        self.headers = {"api-key": api_key, "accept": "application/json", "content-type": "application/json"}
        self.timeout = timeout
        self.retries = retries
        self.sleep = sleep

    def _request(self, method: str, path: str, *, retry: bool = True, **kw) -> requests.Response:
        attempts = self.retries if retry else 1
        for attempt in range(1, attempts + 1):
            try:
                resp = self.session.request(method, API + path, headers=self.headers, timeout=self.timeout, **kw)
            except requests.RequestException as exc:
                if attempt == attempts:
                    raise BrevoError(f"Brevo {method} {path} : erreur réseau {exc}") from exc
                self.sleep(5 * 2 ** (attempt - 1))
                continue
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt == attempts:
                    break
                wait = float(resp.headers.get("Retry-After") or 5 * 2 ** (attempt - 1))
                log.warning("Brevo HTTP %s, nouvel essai dans %.0fs", resp.status_code, wait)
                self.sleep(min(wait, 120))
                continue
            return resp
        raise BrevoError(f"Brevo {method} {path} : HTTP {resp.status_code} {resp.text[:300]}")

    @staticmethod
    def _check(resp: requests.Response, what: str) -> None:
        if resp.status_code >= 400:
            raise BrevoError(f"{what} : HTTP {resp.status_code} {resp.text[:500]}")

    # --- Vérification anti double envoi côté Brevo (en plus du verrou local) ---
    def find_campaigns(self, marker: str) -> list[dict[str, Any]]:
        resp = self._request("GET", "/emailCampaigns", params={"type": "classic", "limit": 50, "offset": 0, "sort": "desc"})
        self._check(resp, "Liste des campagnes")
        return [c for c in resp.json().get("campaigns", []) or [] if marker in (c.get("name") or "")]

    def already_sent(self, marker: str) -> dict[str, Any] | None:
        for c in self.find_campaigns(marker):
            if str(c.get("status", "")).lower().replace(" ", "_") in SENT_STATUSES:
                return c
        return None

    def delete_drafts(self, marker: str) -> None:
        for c in self.find_campaigns(marker):
            if str(c.get("status", "")).lower() == "draft":
                log.info("Suppression d'un brouillon Brevo resté d'un essai précédent (id %s)", c["id"])
                self._request("DELETE", f"/emailCampaigns/{c['id']}")

    # --- Envoi ---
    def create_campaign(
        self, *, name: str, subject: str, sender_name: str, sender_email: str, html: str,
        list_id: int, preview_text: str = "",
    ) -> int:
        body = {
            "name": name,
            "subject": subject,
            "sender": {"name": sender_name, "email": sender_email},
            "htmlContent": html,
            "recipients": {"listIds": [list_id]},
            "previewText": preview_text,
            "inlineImageActivation": False,
        }
        # Pas de retry automatique sur la création (éviterait des brouillons en double).
        resp = self._request("POST", "/emailCampaigns", json=body, retry=False)
        self._check(resp, "Création de la campagne")
        cid = int(resp.json()["id"])
        log.info("Campagne Brevo créée (id %s)", cid)
        return cid

    def send_now(self, campaign_id: int) -> None:
        resp = self._request("POST", f"/emailCampaigns/{campaign_id}/sendNow")
        self._check(resp, "Envoi immédiat de la campagne")
        log.info("Campagne %s envoyée ✅", campaign_id)


def send_issue(
    client: BrevoClient, issue: dict[str, Any], html: str, *, newsletter_name: str, sender_name: str,
    sender_email: str, list_id: int, preview_text: str,
) -> int:
    """Envoie le numéro. Lève BrevoError si un envoi existe déjà pour cette semaine."""
    marker = f"[{issue['week']}]"
    existing = client.already_sent(marker)
    if existing:
        raise BrevoError(
            f"Une campagne {marker} existe déjà chez Brevo (id {existing.get('id')}, statut "
            f"{existing.get('status')}) : envoi annulé pour éviter un doublon."
        )
    client.delete_drafts(marker)
    cid = client.create_campaign(
        name=f"{newsletter_name} n°{issue['number']} {marker}",
        subject=issue["title"],
        sender_name=sender_name,
        sender_email=sender_email,
        html=html,
        list_id=list_id,
        preview_text=preview_text,
    )
    client.send_now(cid)
    return cid
