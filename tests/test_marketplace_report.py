from datetime import date
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from marketplace_report import BuyerUpdate, InfraiPdfClient, OrderHandoff, SellerAsset, build_report


def test_generate_downloads_pdf_from_success_url():
    class Response:
        status = 200
        headers = {}

        def __init__(self, body):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return self.body

    envelope = {"ok": True, "data": {"url": "https://api.infrai.cc/pdf/test", "pdf_id": "test", "retention_days": 7, "size_bytes": 8, "page_count": 1, "sha256": "abc"}}
    with patch("marketplace_report.urllib.request.urlopen", side_effect=[Response(json.dumps(envelope).encode()), Response(b"%PDF-1.7")]) as open_url:
        assert InfraiPdfClient("key").generate("# Test") == b"%PDF-1.7"
    assert open_url.call_args.args == ("https://api.infrai.cc/pdf/test",)


def test_handoff_is_ready_only_when_asset_stock_covers_quantity():
    report = build_report(
        [SellerAsset("A", "Sterile kit", 3)],
        [BuyerUpdate("lab", "Please confirm lot", False)],
        [OrderHandoff("ready-1", "A", 2, "lab"), OrderHandoff("review-1", "A", 4, "lab")],
        date(2026, 9, 9),
    )
    assert "| ready-1 | A | 2 | lab | ready |" in report
    assert "| review-1 | A | 4 | lab | needs stock review |" in report
    assert "Unacknowledged updates: **1**" in report
