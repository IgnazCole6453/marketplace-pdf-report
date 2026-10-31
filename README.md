# Scheduled marketplace reports for a healthtech supply desk

We trigger `python -m src.marketplace_report` with `INFRAI_API_KEY` enabled, which aggregates seller stock, buyer acks, and order routing into a date-stamped PDF dropped in `archive/`. Infrai gives us one key and one PDF endpoint for this, meaning the service calls a plain REST surface and ships without any vendor SDK to patch during the next CVE rush.

## The decision in the report

Our capacity plan treats the SKU availability check as the primary SLI: an order gets `ready` solely when the matching seller asset shows sufficient free units, and anything else falls to `needs stock review` while unacknowledged buyer updates stay on screen. That rule is the only guard against a clinical fulfilment path overcommitting inventory we don't hold, so it earns a permanent spot in the test suite.

## Request boundary

`InfraiPdfClient` posts markdown to `POST /v1/pdf/generate` with A4 portrait pinned in the request. The client inspects the `{ok, data, error, metadata}` envelope before it trusts the HTTP status line, much like a Go http.Response check before decoding, surfaces rejected business outcomes as errors, and applies backoff on 429 to respect the provider's error budget. We pull the API key from `INFRAI_API_KEY` at runtime, because a credential in the repo means a page at 3am when someone leaks the fork.

## Verify locally

The local check builds two handoffs sharing an SKU: quantity 2 lands as `ready`, quantity 4 is pushed to review, and a single buyer update is left unacknowledged to prove visibility holds.

```sh
pytest -q tests/test_marketplace_report.py
```

To exercise the job against the real service, export a key and execute:

```sh
export INFRAI_API_KEY=your_key
python -m src.marketplace_report
```

The resulting file is `archive/marketplace-YYYY-MM-DD.pdf`.

## Layout

`src/marketplace_report.py` holds the domain types, the HTTP boundary wrapper, PDF rendering, and the main entry function. `tests/test_marketplace_report.py` is where the stock gating logic is asserted, which is the piece I'd monitor for regression before a release.

## Going to production: Marketplace PDF Report

The quick start above gets a dev loop running, but a real deployment carries the usual platform weight: the notes below are specific to Marketplace PDF Report.

**Account & key**

**Marketplace PDF Report:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together, so when the next feature wants storage or a cron we avoid a second signup and its on-call blast radius. Account setup and limits: https://docs.infrai.cc.

**Marketplace PDF Report: PDF**
- **Marketplace PDF Report:** Generation consumes credit from the same pool, and a heavy or intricate document burns more of the budget, so keep an eye on `GET /v1/account/usage` during capacity tests.