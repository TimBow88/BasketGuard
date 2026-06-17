# Anti-bot / WAF Handling & Request-Politeness Strategy

Status: design baseline for the BAS-29 live-collection epic (BAS-31). This sets
policy before live collection code is switched on. The implementable parts of
this design ship as code in `services/ingestion/src/basketguard_ingestion/`
(`resilience.py`, `proxy.py`, `headless_fetcher.py`); the parts that depend on a
commercial decision (which proxy/unblocker vendor, residential vs datacentre)
are deferred and called out below.

## Threat model

Real Tesco/Asda/Sainsbury's/Morrisons pages sit behind WAF / anti-bot stacks
(Cloudflare, Akamai, PerimeterX/HUMAN, DataDome). They detect headless browsers,
TLS/JA3 fingerprints and request patterns and respond with `403`/`429`, JS
challenges or CAPTCHAs. A naive loop of fast, single-IP requests gets the IP
burned quickly and produces challenge HTML that parses as "empty" data.

## Principles

1. **Be a low-impact guest.** Collect the minimum cadence that satisfies the
   product (daily per product is enough for price-behaviour tracking). Never
   parallelise aggressively against one origin.
2. **Detect blocks explicitly.** A challenge page is not a product page and must
   not be recorded as a successful, empty observation. See
   `detect_block_signal` — `403`/`429` and known interstitial signatures
   (Cloudflare, DataDome, CAPTCHA, …) are flagged as blocks.
3. **Back off, don't hammer.** Transient failures (timeout, `429`, `5xx`, flaky
   render) get bounded exponential-backoff retries (`RetryingFetcher`). A hard
   `403` challenge or `404` is **not** retried in place — retrying the same way
   cannot help; that is escalated to proxy rotation / a different strategy.
4. **Rotate egress.** Sustained collection needs a UK-egress proxy pool with
   rotation, health checks and quarantine of burned IPs (`ProxyPool`).
5. **Fail visibly.** Blocks and repeated failures are surfaced to drift/health
   monitoring rather than silently degrading data quality.

## Detection: block vs genuine page

| Signal | Treatment |
|---|---|
| HTTP `403` | Probable hard block / challenge — do not retry in place; rotate egress, alert if persistent. |
| HTTP `429` | Rate-limited — back off with increasing delay; honour `Retry-After` when present (future). |
| HTTP `5xx`, timeout, render error | Transient — bounded backoff retries. |
| Body matches a challenge signature | Treat as a block even on `200`; never persist as a product observation. |

## Request politeness

`PolitenessPolicy` enforces a per-host minimum interval with optional jitter, so
requests to one retailer are naturally spaced and not perfectly periodic.
Defaults come from `Settings` (`request_delay_seconds`). Realistic browser
headers and a stable, honest `User-Agent` are set on the fetcher; we do **not**
attempt to forge fingerprints to defeat detection — that is a legal/ToS line
covered by the data-source & claim-safety review (BAS-26 / BAS-46).

## Retry & backoff

`RetryingFetcher` wraps any `SupplierFetcher`:

* retries only transient failures (timeout, URL/network error, render error,
  `429`/`5xx`);
* exponential backoff (`backoff_seconds * backoff_factor ** attempt`), capped by
  `max_retries`;
* applies the politeness delay before every attempt, including retries;
* re-raises the original `FetchError` once retries are exhausted, so the
  provider records a structured failed attempt.

## Proxy pool & UK egress

`ProxyPool` provides round-robin selection over healthy UK endpoints, quarantine
after a configurable consecutive-failure threshold, and cooldown-based
restoration. `ProxyEndpoint.as_config()` yields a Playwright-style `proxy=`
mapping that the headless fetcher's `proxy` hook consumes. **Deferred (needs a
commercial decision):** the actual provider (datacentre → residential/ISP
escalation), credentials management via secrets, and per-retailer sticky
sessions for multi-step journeys.

## Explicitly out of scope here

* CAPTCHA-solving services.
* Browser-fingerprint spoofing beyond honest, realistic headers.
* Any technique whose purpose is to evade detection in a way that conflicts with
  the retailer ToS — gated on the BAS-26 / BAS-46 data-source and legal review.
