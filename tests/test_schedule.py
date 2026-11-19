from app.modules.m5_schedule.rules import *
from app.errors import BusinessError
from app.numbers import number
from decimal import Decimal
import pytest

def test_schedule_exact():
    assert first_fit([(0,100)],[(0,100)],100,[])==(0,100)

def test_schedule_pilot():
    assert first_fit([(0,100)],[(20,60)],30,[])==(20,50)

def test_schedule_short():
    assert first_fit([(0,20)],[(0,100)],30,[]) is None

def test_schedule_occupied():
    assert first_fit([(0,100)],[(0,100)],20,[(0,30)])==(30,50)

def test_schedule_sample(result):
    assert len(result["assigned"])==4

def test_schedule_deterministic(result):
    assert result["assigned"][0]["id"]=="SHIP01"

def test_schedule_no_pilot():
    assert first_fit([(0,100)],[],10,[]) is None