"""Sanitização de conteúdo NÃO CONFIÁVEL — Fase 8 / PRD §6-Segurança.

Todo material de upload/import é não-confiável (CLAUDE.md). Ele passa por este
scanner (a) na ingestão, antes de virar corpus, e (b) na saída do `rag_busca`,
antes de entrar num prompt — defesa em profundidade. Além disso, todo material
já é delimitado como `<material>…</material>` (dados, nunca instruções) pelos
agentes.

Dois modos:
- LLM Guard (grupo opcional `security`, `USE_LLM_GUARD=true`): scanners
  PromptInjection + Secrets, com sanitização.
- Fallback heurístico (default, sempre presente): regex determinístico que
  neutraliza frases de injeção e redige segredos. É sobre ele que roda o teste
  de injeção indireta no CI, sem baixar modelos.

Neutralizar ≠ apagar tudo: trocamos só os trechos perigosos por um marcador,
preservando o restante do material para o pipeline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .config import settings
from .observability import get_logger

log = get_logger("security")

_MARCADOR = "[removido: possível injeção de prompt]"
_REDIGIDO = "[segredo redigido]"

# Frases típicas de injeção indireta (PT/EN). `re.I` no uso.
_INJECTION_PATTERNS: list[str] = [
    r"ignore\s+(as|todas as|the|all)\b.*?(instru|instruction|regra|rule)",
    r"desconsidere?\b.*?(instru|regra|acima|anterior)",
    r"disregard\b.*?(instruction|rule|above|previous)",
    r"aprove\s+(tudo|todas|todos)\b",
    r"approve\s+(everything|all)\b",
    r"marque?\s+.*?como\s+aprovad",
    r"(você|voce|you)\s+(agora|are now|é agora)\b",
    r"(system|do sistema)\s+prompt",
    r"reveal\b.*?(secret|api[\s_-]?key|senha|password|token)",
    r"(mostre|revele|imprima)\b.*?(segredo|api[\s_-]?key|senha|token|chave)",
    r"</?\s*material\s*>",  # tentativa de forjar/fechar o delimitador
    r"</?\s*(system|instructions?)\s*>",
]

# Padrões de segredo (chaves/keys). Conservadores para evitar falso-positivo.
_SECRET_PATTERNS: list[str] = [
    r"sk-[A-Za-z0-9]{20,}",
    r"AKIA[0-9A-Z]{16}",
    r"AIza[0-9A-Za-z_\-]{30,}",
    r"ghp_[A-Za-z0-9]{30,}",
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
]

_INJECTION_RE = [re.compile(p, re.I | re.S) for p in _INJECTION_PATTERNS]
_SECRET_RE = [re.compile(p) for p in _SECRET_PATTERNS]


@dataclass
class ScanResult:
    sanitized: str
    injection: bool = False
    secrets: bool = False
    reasons: list[str] = field(default_factory=list)

    @property
    def flagged(self) -> bool:
        return self.injection or self.secrets


def _heuristica(text: str) -> ScanResult:
    reasons: list[str] = []
    injection = False
    secrets = False
    out = text

    for rx in _INJECTION_RE:
        novo, n = rx.subn(_MARCADOR, out)
        if n:
            injection = True
            reasons.append(f"injeção: /{rx.pattern[:40]}/ ×{n}")
            out = novo
    for rx in _SECRET_RE:
        novo, n = rx.subn(_REDIGIDO, out)
        if n:
            secrets = True
            reasons.append(f"segredo: /{rx.pattern[:24]}/ ×{n}")
            out = novo

    return ScanResult(sanitized=out, injection=injection, secrets=secrets, reasons=reasons)


def _llm_guard(text: str) -> ScanResult:
    """LLM Guard (PromptInjection + Secrets). Só quando habilitado e instalado."""
    from llm_guard.input_scanners import PromptInjection, Secrets

    out = text
    injection = False
    secrets = False
    reasons: list[str] = []
    for scanner, nome in ((PromptInjection(), "injection"), (Secrets(), "secrets")):
        out, valido, _score = scanner.scan(out)
        if not valido:
            reasons.append(f"llm_guard:{nome}")
            if nome == "injection":
                injection = True
            else:
                secrets = True
    # Combina com a heurística para garantir a neutralização textual dos trechos.
    heur = _heuristica(out)
    return ScanResult(
        sanitized=heur.sanitized,
        injection=injection or heur.injection,
        secrets=secrets or heur.secrets,
        reasons=reasons + heur.reasons,
    )


def scan_content(text: str, *, origem: str = "material") -> ScanResult:
    """Sanitiza conteúdo não-confiável. Nunca levanta: em erro, cai na heurística."""
    if not text:
        return ScanResult(sanitized=text)
    try:
        result = _llm_guard(text) if settings.use_llm_guard else _heuristica(text)
    except Exception:  # noqa: BLE001 — segurança não pode derrubar a ingestão.
        log.warning("scanner falhou; usando heurística", origem=origem)
        result = _heuristica(text)
    if result.flagged:
        log.warning(
            "conteúdo não-confiável sinalizado",
            origem=origem,
            injection=result.injection,
            secrets=result.secrets,
            reasons=result.reasons,
        )
    return result


def sanitizar(text: str, *, origem: str = "material") -> str:
    """Atalho: só o texto sanitizado (descarta os flags)."""
    return scan_content(text, origem=origem).sanitized
