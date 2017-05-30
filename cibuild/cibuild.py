#!/usr/bin/env python
import os
import sys
import subprocess
from ciutil.ciutil import PathStackMgr

class CIBuild:
    def __init__(self, workDir, prodVersion):
        self._workDir = wordDir
        self._prodVersion = prodVersion
        self._pathStack = PathStackMgr()

    def prebuild(self):
        return

    def createLabel(self):
        return
    
    def getNextBuildNumber(self):
        iNextBN = 1
        output1 = subprocess.check_output(['git','tag','-l', tagPrefix_s1 + '_rc_' + '*','--sort=-version:refname'], shell=True)
        return