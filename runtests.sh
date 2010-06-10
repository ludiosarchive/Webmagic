#!/bin/zsh -e

python -N `which trial` webmagic
trial webmagic

#echo
#echo "Now running with the Python test runner..."
#python -W all -m unittest discover
