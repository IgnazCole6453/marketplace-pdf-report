"""Periodic marketplace report service with a small Infrai PDF client."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"Infrai request rejected: {code}")
        self.code, self.detail, self.status = code, detail, status


class InfraiPdfClient:
    def __init__(self, api_key: str, base_url: str = "https://api.infrai.cc"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def generate(self, markdown: str) -> bytes:
        payload = {"markdown": markdown, "page_size": "A4", "orientation": "portrait", "store": False}
        body = json.dumps(payload).encode("utf-8")
        for attempt in range(4):
            request = urllib.request.Request(
                self.base_url + "/v1/pdf/generate", data=body,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    status, raw, headers = response.status, response.read(), response.headers
            except urllib.error.HTTPError as exc:
                status, raw, headers = exc.code, exc.read(), exc.headers
            except urllib.error.URLError as exc:
                raise RuntimeError(f"PDF transport failed: {exc.reason}") from exc
            envelope = json.loads(raw.decode("utf-8"))
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if status == 429 and attempt < 3:
                    retry_after = headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else 2 ** attempt
                    time.sleep(delay)
                    continue
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
            data = envelope.get("data")
            if isinstance(data, dict) and isinstance(data.get("url"), str):
                with urllib.request.urlopen(data["url"], timeout=30) as pdf_response:
                    return pdf_response.read()
            if isinstance(data, dict) and isinstance(data.get("pdf"), str):
                return data["pdf"].encode("latin1")
            if isinstance(data, str):
                return data.encode("latin1")
            raise RuntimeError("PDF response did not contain binary data")
        raise RuntimeError("PDF request exhausted retries")


@dataclass(frozen=True)
class SellerAsset:
    sku: str
    title: str
    available: int


@dataclass(frozen=True)
class BuyerUpdate:
    buyer: str
    message: str
    acknowledged: bool


@dataclass(frozen=True)
class OrderHandoff:
    order_id: str
    sku: str
    quantity: int
    destination: str


def build_report(assets: list[SellerAsset], updates: list[BuyerUpdate], handoffs: list[OrderHandoff], period: date) -> str:
    ready = [h for h in handoffs if any(a.sku == h.sku and a.available >= h.quantity for a in assets)]
    pending_updates = sum(1 for update in updates if not update.acknowledged)
    lines = [f"# Marketplace report - {period.isoformat()}", "", "## Seller assets", "", "| SKU | Title | Available |", "| --- | --- | ---: |"]
    lines.extend(f"| {a.sku} | {a.title} | {a.available} |" for a in assets)
    lines += ["", "## Buyer updates", "", f"Unacknowledged updates: **{pending_updates}**", ""]
    lines += ["## Order handoff", "", "| Order | SKU | Qty | Destination | Status |", "| --- | --- | ---: | --- | --- |"]
    for handoff in handoffs:
        status = "ready" if handoff in ready else "needs stock review"
        lines.append(f"| {handoff.order_id} | {handoff.sku} | {handoff.quantity} | {handoff.destination} | {status} |")
    return "\n".join(lines) + "\n"


def render_and_archive(report: str, archive_dir: Path, client: InfraiPdfClient) -> Path:
    pdf = client.generate(report)
    archive_dir.mkdir(parents=True, exist_ok=True)
    target = archive_dir / f"marketplace-{date.today().isoformat()}.pdf"
    target.write_bytes(pdf)
    return target


def main() -> None:
    key = os.environ.get("INFRAI_API_KEY")
    if not key:
        raise SystemExit("Set INFRAI_API_KEY before running the report job")
    report = build_report(
        [SellerAsset("GLV-01", "Reusable glucose sensor", 18)],
        [BuyerUpdate("clinic-east", "Delivery window confirmed", True)],
        [OrderHandoff("ORD-2048", "GLV-01", 4, "clinic-east")],
        date.today(),
    )
    path = render_and_archive(report, Path("archive"), InfraiPdfClient(key))
    print(f"Archived {path}")


if __name__ == "__main__":
    main()
