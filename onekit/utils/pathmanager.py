#!/usr/bin/env python
import os
import sys
from ..cierrors import CIBasicError

class PathStackMgr:
    def __init__(self):
        self.pathStack = list()
        
    def pushd(self, path):
        try:
            self.pathStack.append(path)
            os.chdir(path)
        except Exception as err:
            raise PathStackError("Failed on method pushd", err)
        
    def popd(self):
        try:
            if(len(self.pathStack) > 0):
                os.chdir(self.pathStack.pop())
        except Exception as err:
            raise PathStackError("Failed on method popd", err)
            
class PathStackError(CIBasicError):
    def __init__(self, errormsg, cause=None):
        CIBasicError.__init__(self, errormsg, cause)
    
    def __repr__(self):
        return self.stackError
    
    def __str__(self):
        return self.stackError