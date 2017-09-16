#!/usr/bin/env python
import os
import re
from ciutils.cmdutils import CMDExecutor, CMDExecutorError
from cierrors import CIBasicError
from ciutils.fileutils import FileManager

class CIBuild:
    BUIDINFO_FILENAME = "build-info.properties"

    def __init__(self, workDir, prodVersion, buildName, gitRemote="origin"):
        self._workDir = workDir
        self._prodVersion = prodVersion
        self._buildName = buildName
        self._gitRemote = gitRemote
        
    def _saveBuildInfo(self, buildInfo):
        content = ""
        filepath = self._workDir + os.sep + self.BUIDINFO_FILENAME
        try:
            for key in buildInfo.keys():
                content = content + key + "=" + buildInfo[key] + "\n"

            content.rstrip("\n")
            FileManager.saveTextFile(filepath, content)
        except Exception as err:
            raise CIBuildError("Failed on method _saveBuildInfo!", err)

    def prebuild(self, saveBuildInfo=False):
        try:
            nextBN = self.getNextBuildNumber()
            currentCommit = self.getCurrentCommit()
            buildVersion = self._prodVersion + "_b" + str(nextBN)
            buildLabel = buildVersion
            self.createLabel(buildLabel, currentCommit)
            if(saveBuildInfo):
                buildInfo = {}
                buildInfo['build.name'] = self._buildName
                buildInfo['build.number'] = str(nextBN);
                buildInfo['build.version'] = buildVersion
                buildInfo['build.label'] = buildLabel
                buildInfo['build.commit'] = currentCommit
                self._saveBuildInfo(buildInfo)
            
        except Exception as err:
            raise CIBuildError("Failed on method prebuild!", err)

    def createLabel(self, label, commit):
        try:
            cmdline = "git tag " + label + " " + commit
            cmd = CMDExecutor(cmdline, self._workDir)
            cmd.execute()
            cmdline = "git push " + self._gitRemote + " " + label
            cmd = CMDExecutor(cmdline, self._workDir)
            cmd.execute()
        except Exception as err:
            raise CIBuildError("Failed on method createLabel", err)
    
    def getNextBuildNumber(self):
        iNextBN = 1
        cmdline = "git tag -l " + self._prodVersion + "* --sort=-version:refname"
        cmd = CMDExecutor(cmdline, self._workDir)
        try:
            output = cmd.execute()
            if(output):
                listOutput = output.split("\n")
                sLatestBN =  re.sub(self._prodVersion+'_b', '', listOutput[0], flags=re.IGNORECASE)
                latestBN = int(sLatestBN)
                iNextBN = latestBN + 1
        except Exception as err:
            raise CIBuildError("Failed on method getNextBuildNumber!", err)

        return iNextBN

    def getCurrentCommit(self):
        cmdline = "git rev-parse HEAD"
        cmd = CMDExecutor(cmdline, self._workDir)
        try:
            output = cmd.execute()
            return output.lstrip('\n\s').rstrip('\n\s')
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