import csv, io, itertools
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import store
from app.pipeline import run, sample_text
from app.errors import BusinessError

client = TestClient(app, raise_server_exceptions=False)


_COUNTER = itertools.count()

def unique_text():
    return sample_text() + f"# 批次 {next(_COUNTER)}\n"


def fresh_run():
    text = unique_text()
    return store.save(text, run(text))


def pending_ids(result):
    return {item["id"] for item in result["pending"]}


def correction(ident, value="9", version="2", unit="m"):
    return (f"id,kind,start,end,value,aux,version,unit\n"
            f"{ident},ship,2026-11-18T00:00:00+00:00,2026-11-18T20:00:00+00:00,"
            f"{value},30,{version},{unit}\n")


def test_unverified_ship_kept_in_pending_with_reason_and_source_line(result):
    items = {item["id"]: item for item in result["pending"]}
    assert set(items) == {"BAD1", "BAD2"}
    assert items["BAD1"]["reason"] == "MISSING"
    assert items["BAD1"]["raw"]["value"] == "N/A"
    assert items["BAD1"]["line"] == 58
    assert items["BAD1"]["reason_text"]


def test_unverified_ship_never_occupies_a_slot(result):
    assert pending_ids(result) == {"BAD1", "BAD2"}
    assert not set(pending_ids(result)) & {row["id"] for row in result["assigned"]}
    assert not set(pending_ids(result)) & {row["id"] for row in result["final"]}


def test_bad_newer_version_does_not_fall_back_to_old(sample):
    text = (sample
            + "LATE1,ship,2026-11-18T00:00:00Z,,8,30,1,m\n"
            + "LATE1,ship,2026-11-18T00:00:00Z,,N/A,30,2,m\n")
    result = run(text)
    assert "LATE1" in pending_ids(result)
    assert not any(row["id"] == "LATE1" for row in result["assigned"])


def test_bad_older_version_does_not_block_newer_valid(sample):
    text = (sample
            + "LATE2,ship,2026-11-18T00:00:00Z,,N/A,30,1,m\n"
            + "LATE2,ship,2026-11-18T20:00:00Z,2026-11-19T00:00:00Z,8,30,2,m\n")
    result = run(text)
    assert "LATE2" not in pending_ids(result)
    assert any(row["id"] == "LATE2" for row in result["assigned"])


def test_publish_freezes_scheduled_slots():
    run_item = fresh_run()
    published = store.publish(run_item["id"], run_item["revision"])
    slots = {row["id"]: (row["start_s"], row["end_s"])
             for row in published["result"]["final"] if row["status"] == "SCHEDULED"}
    assert published["state"]["published"] is True
    assert set(slots) == {"SHIP01", "SHIP02", "SHIP03", "SHIP04"}
    assert all(row["published"] for row in published["result"]["final"])


def test_correction_only_touches_pending_and_keeps_published_slots():
    run_item = fresh_run()
    published = store.publish(run_item["id"], run_item["revision"])
    before = {row["id"]: (row["start_s"], row["end_s"]) for row in published["result"]["final"]}
    corrected = store.correct(published["id"], published["revision"], correction("BAD1"))
    after = {row["id"]: (row["start_s"], row["end_s"]) for row in corrected["result"]["final"]}
    assert "BAD1" in after and "BAD1" not in before
    for ident in before:
        assert after[ident] == before[ident]
    assert pending_ids(corrected["result"]) == {"BAD2"}
    assert corrected["state"]["correction_round"] == 1


def test_correction_rejects_ships_outside_pending():
    run_item = fresh_run()
    with pytest.raises(BusinessError) as caught:
        store.correct(run_item["id"], run_item["revision"], correction("SHIP01"))
    assert caught.value.code == "CORRECTION_SCOPE"


def test_correction_stale_revision_keeps_pending(monkeypatch):
    run_item = fresh_run()
    with pytest.raises(BusinessError) as caught:
        store.correct(run_item["id"], run_item["revision"] + 5, correction("BAD1"))
    assert caught.value.status == 409
    current = store.get(run_item["id"])
    assert pending_ids(current["result"]) == {"BAD1", "BAD2"}
    # 中断后仍可从待定区继续办理。
    resumed = store.correct(current["id"], current["revision"], correction("BAD1"))
    assert pending_ids(resumed["result"]) == {"BAD2"}


def test_repeated_correction_does_not_add_round_or_slot():
    run_item = fresh_run()
    published = store.publish(run_item["id"], run_item["revision"])
    first = store.correct(published["id"], published["revision"], correction("BAD1"))
    repeat = store.correct(first["id"], first["revision"], correction("BAD1"))
    assert repeat["revision"] == first["revision"]
    assert repeat["state"]["correction_round"] == 1


def test_correction_requires_unique_rows():
    run_item = fresh_run()
    text = correction("BAD1") + correction("BAD1", value="8", version="2").split("\n", 1)[1]
    with pytest.raises(BusinessError) as caught:
        store.correct(run_item["id"], run_item["revision"], text)
    assert caught.value.code == "CORRECTION_DUPLICATE"


def test_rerun_same_text_reuses_batch():
    text = unique_text()
    first = store.save(text, run(text))
    second = store.save(text, run(text))
    assert first["id"] == second["id"] and first["revision"] == second["revision"]


def test_rerun_corrected_text_reuses_batch():
    run_item = fresh_run()
    corrected = store.correct(run_item["id"], run_item["revision"], correction("BAD1"))
    again = store.save(corrected["source"], run(corrected["source"]))
    assert again["id"] == run_item["id"]


def test_export_has_destination_and_correction_diff():
    run_item = fresh_run()
    published = store.publish(run_item["id"], run_item["revision"])
    corrected = store.correct(published["id"], published["revision"], correction("BAD1"))
    from app.exporter import evidence_csv
    rows = list(csv.DictReader(io.StringIO(evidence_csv(corrected).lstrip("﻿"))))
    kinds = {row["kind"] for row in rows}
    assert {"manifest", "result", "pending", "correction"} <= kinds
    assert any(row["kind"] == "correction" and '"before"' in row["evidence"] for row in rows)
    assert any(row["kind"] == "pending" and '"reason"' in row["evidence"] for row in rows)


def test_page_shows_pending_and_destination():
    run_item = fresh_run()
    page = client.get("/", params={"run_id": run_item["id"]})
    assert page.status_code == 200
    assert "待定区" in page.text and "BAD1" in page.text and "MISSING" in page.text
    assert "船舶去向" in page.text
    body = client.get(f"/api/runs/{run_item['id']}").json()
    assert body["result"]["pending"]


def test_publish_and_correct_endpoints():
    run_item = fresh_run()
    published = client.post("/api/publish", json={"id": run_item["id"], "revision": run_item["revision"]})
    assert published.status_code == 200
    corrected = client.post("/api/correct", json={"id": run_item["id"], "revision": published.json()["revision"],
                                                  "text": correction("BAD2", unit="m")})
    assert corrected.status_code == 200
    assert corrected.json()["state"]["correction_round"] == 1
    assert client.post("/api/publish", json={"id": run_item["id"], "revision": True}).status_code == 422

def test_rerun_after_publish_keeps_frozen_plan():
    run_item = fresh_run()
    published = store.publish(run_item["id"], run_item["revision"])
    again = store.save(published["source"], run(published["source"]))
    assert again["id"] == published["id"]
    assert again["state"]["published"] is True
    assert again["state"]["frozen"] == published["state"]["frozen"]


def test_publish_is_idempotent():
    run_item = fresh_run()
    first = store.publish(run_item["id"], run_item["revision"])
    second = store.publish(first["id"], first["revision"])
    assert second["revision"] == first["revision"]
    assert len(second["result"]["assigned"]) == len(first["result"]["assigned"])


def test_failed_correction_is_atomic():
    run_item = fresh_run()
    mixed = correction("BAD1") + correction("BAD2", value="N/A").split("\n", 1)[1]
    store.correct(run_item["id"], run_item["revision"], mixed)
    current = store.get(run_item["id"])
    # 补正后 BAD2 仍未核实：它留在待定区，原因更新，不发生半成品写入。
    items = {item["id"]: item for item in current["result"]["pending"]}
    assert set(items) == {"BAD2"}
    assert items["BAD2"]["reason"] == "MISSING"


def test_publish_allowed_with_pending_but_not_with_unplaced(sample):
    run_item = fresh_run()
    assert store.get(run_item["id"])["result"]["pending"]
    published = store.publish(run_item["id"], run_item["revision"])
    assert published["state"]["published"] is True

    text = (sample
            + "DEEP1,ship,2026-11-18T00:00:00Z,2026-11-18T20:00:00Z,30,30,1,m\n")
    deep = store.save(text, run(text))
    with pytest.raises(BusinessError) as caught:
        store.publish(deep["id"], deep["revision"])
    assert caught.value.code == "BLOCKED"


def test_successive_corrections_keep_every_locked_slot():
    run_item = fresh_run()
    published = store.publish(run_item["id"], run_item["revision"])
    slots = {row["id"]: (row["start_s"], row["end_s"]) for row in published["result"]["final"]}
    first = store.correct(published["id"], published["revision"], correction("BAD1"))
    first_slots = {row["id"]: (row["start_s"], row["end_s"]) for row in first["result"]["final"]}
    assert all(first_slots[k] == slots[k] for k in slots)
    second = store.correct(first["id"], first["revision"], correction("BAD2"))
    second_slots = {row["id"]: (row["start_s"], row["end_s"]) for row in second["result"]["final"]}
    for ident, slot in first_slots.items():
        assert second_slots[ident] == slot
    assert second["state"]["correction_round"] == 2


def test_replay_after_pending_cleared_returns_same_batch():
    run_item = fresh_run()
    full = correction("BAD1") + correction("BAD2").split("\n", 1)[1]
    first = store.correct(run_item["id"], run_item["revision"], full)
    assert not first["result"]["pending"]
    replay = store.correct(first["id"], first["revision"], full)
    assert replay["revision"] == first["revision"]
