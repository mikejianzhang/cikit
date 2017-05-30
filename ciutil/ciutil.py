#!/usr/bin/env python
import os
import sys

class PathStackMgr:
    def __init__(self):
        self.pathStack = list()
        
    def pushd(self, path):
        self.pathStack.append(path)
        os.chdir(path)
        
    def popd(self):
        if(len(pathStack) > 0):
            os.chdir(self.pathStack.pop())