#!/usr/bin/env python
import os

class PathStackMgr:
    def __init__(self):
        self.pathStack = list()
        
    def pushd(self, path):
        self.pathStack.append(path)
        os.chdir(path)
        
    def popd(self):
        if(len(self.pathStack) > 0):
            os.chdir(self.pathStack.pop())