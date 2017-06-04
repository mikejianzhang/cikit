#!/usr/bin/env python

from ciutils.cmdutils import CMDExecutor, CMDExecutorError
from cierrors import CIBasicError

class CIBuild:
    def __init__(self, workDir, prodVersion, buildName):
        self._workDir = workDir
        self._prodVersion = prodVersion
        self._buildName = buildName
        
    def _saveBuildInfo(self, buildInfo):
        pass

    def prebuild(self, saveBuildInfo=False):
        try:
            nextBN = self.getNextBuildNumber()
            buildVersion = self._prodVersion + "_b" + str(nextBN)
            buildLabel = buildVersion
            self.createLabel(buildLabel)
            if(saveBuildInfo):
                buildInfo = {}
                buildInfo['build.name'] = self._buildName
                buildInfo['build.number'] = str(nextBN);
                buildInfo['build.version'] = buildVersion
                buildInfo['build.label'] = buildLabel
                buildInfo['build.commit'] = self.getCurrentCommit()
                self._saveBuildInfo(buildInfo)
            
        except Exception as err:
            raise CIBuildError("Failed on method prebuild!", err)

    def createLabel(self, label):
        return
    
    def getNextBuildNumber(self):
        iNextBN = 1
        cmdline = "git tag -l " + self._prodVersion + "* --sort=-version:refname"
        cmd = CMDExecutor(cmdline, self._workDir)
        try:
            output = cmd.execute()
            if(output):
                listOutput = output.split("\n")
                latestBN = int(output[0])
                iNextBN = latestBN + 1
        except Exception as err:
            raise CIBuildError("Failed on method getNextBuildNumber!", err)

        return iNextBN

    def getCurrentCommit(self):
        cmdline = "git rev-parse HEAD"
        cmd = CMDExecutor(cmdline, self._workDir)
        try:
            output = cmd.execute()
            return output
        except Exception as err:
            raise CIBuildError("Failed on method getCurrentCommit!", err)
    
class CIBuildError(CIBasicError):
    def __init__(self, errormsg, cause=None):
        CIBasicError.__init__(self, errormsg, cause)
        
    def __str__(self):
        return self.stackError
    
    def __repr__(self):
        return self.stackError
    
if __name__ == "__main__":
    build = CIBuild("/Users/mike/Documents/MikeWorkspace/FreessureCoffee/service", "1.3.1")
    build.getNextBuildNumber()