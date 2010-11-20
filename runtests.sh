#!/bin/sh -e

python -W all -N `which trial` webmagic
python -W all `which trial` webmagic
python -W all -O `which trial` webmagic
