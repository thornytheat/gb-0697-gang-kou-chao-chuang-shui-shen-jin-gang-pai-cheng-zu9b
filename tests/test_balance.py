from app.modules.m6_balance.rules import *
from app.errors import BusinessError
from app.numbers import number
from decimal import Decimal
import pytest

def test_balance_no_overlap():
    assert overlaps([{"id":"a","start_s":0,"end_s":10,"status":"SCHEDULED"},{"id":"b","start_s":10,"end_s":20,"status":"SCHEDULED"}])==[]

def test_balance_overlap():
    assert overlaps([{"id":"a","start_s":0,"end_s":11,"status":"SCHEDULED"},{"id":"b","start_s":10,"end_s":20,"status":"SCHEDULED"}])==[("a","b")]

def test_balance_empty():
    assert overlaps([])==[]

def test_balance_sample(result):
    assert result["balance"]["input"]==60

def test_balance_reason(result):
    assert result["balance"]["quarantined"]==4

def test_balance_slots(result):
    assert result["conflicts"]==[]

def test_balance_ship_count(result):
    assert len(result["checked"])==4