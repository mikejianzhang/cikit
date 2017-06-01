#!/usr/bin/env python
import subprocess
from ciutils.pathmanager import PathStackMgr
from ciutils.cmdutils import CMDExecutor, CMDExecutorError

class CIBuild:
    def __init__(self, workDir, prodVersion):
        self._workDir = workDir
        self._prodVersion = prodVersion
        self._buildInfo = {}
        self._pathStack = PathStackMgr()
        self.generateBuildInfo() # Can support to load build info properties instead of created dynamiclly.

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
        cmdline = "git tag -l " + self._prodVersion + "* --sort=-version:refname"
        self._pathStack.pushd(self._workDir)
        cmd = CMDExecutor(cmdline)
        output = cmd.execute()
        self._pathStack.popd()
        print output
        return iNextBN

    def getCurrentCommit(self):
        return
    
if __name__ == "__main__":
    build = CIBuild("/Users/mike/Documents/MikeWorkspace/FreessureCoffee/service", "1.3.1")
    build.getNextBuildNumber()