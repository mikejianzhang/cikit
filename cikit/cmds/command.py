#!/usr/bin/env python
from abc import ABCMeta, abstractmethod

class Command:
    __metaclass__ = ABCMeta

    @abstractmethod
    def execute(self, args):
        pass
        