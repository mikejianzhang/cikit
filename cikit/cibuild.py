#!/usr/bin/env python
import os
import sys
import subprocess
from ciutil.ciutil import PathStackMgr

class CIBuild:
    def __init__(self, workDir, prodVersion):
        self._workDir = wordDir
        self._prodVersion = prodVersion
        self._buildInfo = {}
        self._pathStack = PathStackMgr()
        self.generateBuildInfo()

    def prebuild(self):
        self.createLabel()
        return (self._buildInfo['build.number'],
                self._buildInfo['build.version'],
                self._buildInfo['build.label'],
                self._buildInfo['build.commit'])

    def generateBuildInfo(self):
        sNextNumber = str(self.getNextBuildNumber())
        sBuildVersion = self._prodVersion + "_b" + sNextNumber
        self._buildInfo['build.number'] = sNextNumber;
        self._buildInfo['build.version'] = sBuildVersion
        self._buildInfo['build.label'] = sBuildVersion
        self._buildInfo['build.commit'] = self.getCurrentCommit()

    def createLabel(self):
        return
    
    def getNextBuildNumber(self):
        iNextBN = 1
        output1 = subprocess.check_output(['git','tag','-l', tagPrefix_s1 + '_rc_' + '*','--sort=-version:refname'], shell=True)
        return iNextBN

    def getCurrentCommit(self):
        return