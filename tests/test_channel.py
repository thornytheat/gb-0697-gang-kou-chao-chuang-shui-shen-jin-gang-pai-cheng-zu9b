# TRAP-23
from app.modules.m4_channel.rules import *
from app.errors import BusinessError
from app.numbers import number
from decimal import Decimal
import pytest

def test_channel_split():
    assert subtract((0,100),[(20,40)])==[(0,20),(40,100)]

def test_channel_end():
    assert subtract((0,100),[(100,120)])==[(0,100)]

def test_channel_full():
    assert subtract((0,100),[(-10,110)])==[]

def test_channel_nested():
    assert subtract((0,100),[(20,60),(30,40)])==[(0,20),(60,100)]

def test_channel_conserve():
    assert sum(b-a for a,b in subtract((0,100),[(20,40)]))==80

def test_channel_sample(result):
    assert len(result["channel_windows"])>=4

def test_channel_order():
    assert subtract((0,100),[(20,40),(60,80)])==subtract((0,100),[(60,80),(20,40)])