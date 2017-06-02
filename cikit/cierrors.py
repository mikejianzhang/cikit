#!/usr/bin/env python

class CIBasicError(Exception):
    def __init__(self, cause=None):
        self._cause = cause
