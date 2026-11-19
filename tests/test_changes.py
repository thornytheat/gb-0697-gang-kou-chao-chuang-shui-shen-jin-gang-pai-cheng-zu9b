# TRAP-25
from app.modules.m7_changes.rules import *
from app.errors import BusinessError
from app.numbers import number
from decimal import Decimal
import pytest

def test_change_revision(sample):
    from app.pipeline import run
    r=run(sample+"SHIP01,ship,2026-11-18T00:00:00Z,2026-11-18T20:00:00Z,8,30,2,m\n")
    change=next(x for x in r["change_log"] if x["id"]=="SHIP01")
    assert change["superseded_versions"]==[1] and change["revision_delta"]==1 and change["status"]=="REPLACED"

def test_change_stale():
    with pytest.raises(ValueError):version_changed(2,2)

def test_change_backward():
    with pytest.raises(ValueError):version_changed(3,2)

def test_change_display():
    assert display(Decimal(0))=="01-01 00:00 UTC"

def test_change_sample_final(result):
    assert len(result["final"])==4

def test_change_utc(result):
    assert all(r["start"]=="未安排" or r["start"].endswith("UTC") for r in result["final"])

def test_change_status(result):
    assert {r["status"] for r in result["final"]} <= {"SCHEDULED","NO_SAFE_SLOT"}