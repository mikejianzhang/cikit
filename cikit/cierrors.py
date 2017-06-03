#!/usr/bin/env python

from abc import ABCMeta,abstractproperty,abstractmethod

class CIBasicError(Exception):
    __metaclass__ = ABCMeta
    def __init__(self, errormsg, cause=None):
        self._errormsg = errormsg
        self._cause = cause
    
    def __repr__(self):
        return self.stackError
    
    @property
    def stackError(self):
        stackError = ""
        if(self._cause):
            if(isinstance(self._cause, CIBasicError)):
                stackError = self._cause.stackError
            else:
                stackError = "[Error class]: " + self._cause.__class__.__name__ + \
                            "\n[Error Message]:\n" + str(self._cause)
        
        stackError = self.error + "\n\nCaused by => \n\n" + stackError
        return stackError
         
    @property
    def error(self):
        value = "[Error class]: " + self.__class__.__name__ + \
                "\n[Error Message]:\n" + self._errormsg
        return value
