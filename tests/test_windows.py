# TRAP-13
from app.modules.m3_windows.rules import *
from app.errors import BusinessError
from app.numbers import number
from decimal import Decimal
import pytest

def test_window_crossing():
    assert safe_segment(Decimal(0),Decimal(100),Decimal(0),Decimal(2),Decimal(1))==(50,100)

def test_window_falling():
    assert safe_segment(Decimal(0),Decimal(100),Decimal(2),Decimal(0),Decimal(1))==(0,50)

def test_window_gap():
    assert safe_segment(Decimal(0),Decimal(20000),Decimal(2),Decimal(2),Decimal(1)) is None

def test_window_below():
    assert safe_segment(Decimal(0),Decimal(100),Decimal(0),Decimal(0),Decimal(1)) is None

def test_window_adjacent():
    assert windows([(Decimal(0),Decimal(2)),(Decimal(100),Decimal(2)),(Decimal(200),Decimal(2))],Decimal(1))==[(0,200)]

def test_window_sample(result):
    assert len(result["tide_windows"])>=4

def test_window_threshold(result):
    assert all(Decimal(r["threshold_m"])>0 for r in result["tide_windows"])
def test_window_never_interpolates_across_conflicting_time():
    points=[(Decimal(0),Decimal(3)),(Decimal(3600),Decimal(3))]
    assert windows(points,Decimal(2),[Decimal(1800)])==[]
