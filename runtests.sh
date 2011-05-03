#!/bin/sh -e

MYPY_REFBINDER_AUTOENABLE=0 time python     -W all `which trial` webmagic
MYPY_REFBINDER_AUTOENABLE=1 time python     -W all `which trial` webmagic
MYPY_REFBINDER_AUTOENABLE=0 time python -O  -W all `which trial` webmagic
MYPY_REFBINDER_AUTOENABLE=1 time python -O  -W all `which trial` webmagic
MYPY_REFBINDER_AUTOENABLE=0 time python -OO -W all `which trial` webmagic
MYPY_REFBINDER_AUTOENABLE=1 time python -OO -W all `which trial` webmagic

MYPY_REFBINDER_AUTOENABLE=0 time pypy       -W all `which trial` webmagic
MYPY_REFBINDER_AUTOENABLE=1 time pypy       -W all `which trial` webmagic

#MYPY_REFBINDER_AUTOENABLE=0 time jython      `which trial` webmagic
#MYPY_REFBINDER_AUTOENABLE=1 time jython      `which trial` webmagic
