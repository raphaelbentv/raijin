# ADR 0001 — Stratégie de retry OCR

**Statut** : Accepté — 2026-04-21
**Contexte** : Sprint 2, pipeline OCR Azure Document Intelligence

## Décision

Le pipeline OCR distingue trois catégories d'échecs.

| Catégorie | Exception | Comportement |
|-----------|-----------|--------------|
| Transient (réseau, 5xx, 429) | `AzureDiTransientError` | retry automatique avec backoff exponentiel (30s → 300s) + jitter, max `OCR_MAX_RETRIES` tentatives |
| Permanent (4xx, document illisible, quota) | `AzureDiPermanentError` | pas de retry, invoice → `failed`, `validation_errors` rempli |
| Infra DB | `SQLAlchemyError` | retry court (3 tentatives, 30s) |
| Inconnu | `Exception` générique | invoice → `failed`, trace loggée |

## Justification

- **Backoff exponentiel** : évite de surcharger Azure DI pendant une dégradation, respecte les rate limits (429).
- **Jitter** : évite le thundering herd si plusieurs workers repartent en même temps.
- **max_retries borné** : un document durablement illisible ne doit pas occuper un worker en boucle.
- **`acks_late=True`** : la tâche n'est ack qu'après completion ; un kill du worker au milieu re-livre la tâche à un autre worker.
- **`task_time_limit=300s`, `task_soft_time_limit=270s`** : déjà configuré dans `celery_app.py`, protège contre les Azure DI qui pendent.

## Observabilité

- Logs structurés (`structlog`) avec `invoice_id` et `attempt` à chaque étape.
- Endpoint `GET /health/worker` côté API → ping Celery → retour `ok`/`degraded`.
- Statuts invoice (`uploaded` → `processing` → `ready_for_review`/`failed`) + `validation_errors` JSONB permettent de reconstruire la timeline.

## Conséquences

- Un tenant avec 100% de factures illisibles ne bloque pas les autres tenants.
- Les coûts Azure DI ne sont pas doublés par des retries excessifs (max 3 par défaut).
- En cas de panne Azure >15 min, les tâches finissent par échouer et doivent être relancées manuellement.

## Ouvert

- Dead-letter queue Redis pour re-process manuel des échecs — à ajouter quand volume > 500/mois.
- Alerting sur taux d'échec > 5% — à brancher Prometheus/Grafana phase 2.
