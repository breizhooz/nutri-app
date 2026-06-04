"""Garde anti-SSRF pour les fetch sortants du crawler (SEC-03).

Le crawler récupère des URLs **fournies par l'utilisateur**. Sans contrôle, il
peut être détourné pour atteindre le réseau interne (Postgres, Redis, MinIO…) ou
les métadonnées cloud (169.254.169.254) — c'est une SSRF.

``assert_public_url`` n'autorise que http(s) vers une cible dont **toutes** les IP
résolues sont publiques. Les IP littérales privées/loopback/link-local/réservées
sont rejetées, de même qu'un hostname qui résout vers une de ces plages.

Limite connue (résiduelle) : ce contrôle valide l'URL d'entrée. Une redirection
HTTP ou un DNS-rebinding (TOCTOU entre la résolution ici et celle du client)
peut encore pointer vers une cible interne — d'où l'appel de garde **aussi** sur
chaque saut côté appelant et la recommandation moyen-terme (résolution + pin
d'IP au moment de la connexion).
"""

import ipaddress
import socket
from urllib.parse import urlparse

ALLOWED_SCHEMES = frozenset({"http", "https"})


class UnsafeUrlError(ValueError):
    """Levée quand une URL est interdite (schéma non autorisé ou cible interne)."""


def _assert_ip_public(ip: ipaddress._BaseAddress) -> None:
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local  # couvre 169.254.0.0/16 (métadonnées cloud)
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    ):
        raise UnsafeUrlError(f"adresse non publique interdite: {ip}")


def _default_resolver(host: str) -> list[str]:
    """Résout un hostname vers la liste de ses IP (IPv4 + IPv6)."""
    return [info[4][0] for info in socket.getaddrinfo(host, None)]


def assert_public_url(url: str, *, resolver=_default_resolver) -> None:
    """Valide qu'``url`` est http(s) et pointe vers une IP publique.

    ``resolver`` est injectable pour les tests (évite tout DNS réseau). Lève
    ``UnsafeUrlError`` si l'URL est malformée, d'un schéma non autorisé, ou
    résout vers une adresse non publique.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise UnsafeUrlError(f"schéma non autorisé: {parsed.scheme or '(vide)'}")

    host = parsed.hostname
    if not host:
        raise UnsafeUrlError("hostname manquant dans l'URL")

    # IP littérale : on vérifie directement, sans résolution.
    try:
        _assert_ip_public(ipaddress.ip_address(host))
        return
    except ValueError as exc:
        if isinstance(exc, UnsafeUrlError):
            raise
        # Pas une IP littérale → c'est un hostname, on résout.

    try:
        resolved = resolver(host)
    except socket.gaierror as exc:
        raise UnsafeUrlError(f"résolution DNS impossible pour {host}") from exc

    if not resolved:
        raise UnsafeUrlError(f"aucune IP résolue pour {host}")

    for raw_ip in resolved:
        _assert_ip_public(ipaddress.ip_address(raw_ip))
