#!/usr/bin/env python
import subprocess
from pathmanager import PathStackMgr

class CMDExecutor:
    def __init__(self, cmdline, workDir):
        self._cmdline = cmdline
        self._workDir = workDir
        self._pathStack = PathStackMgr()
        
    def execute(self):
        output=''
        try:
            self._pathStack.pushd(self._workDir)
            output=subprocess.check_output(self._cmdline, stderr=subprocess.STDOUT, shell=True)
            self._pathStack.popd()
        except subprocess.CalledProcessError as err:
            raise CMDExecutorError(self._cmdline, err.returncode, err.output)
        else:
            return output
        
class CMDExecutorError(Exception):
    def __init__(self, cmdline, errorcode, errormsg):
        self._cmdline = cmdline
        self._errorcode = errorcode
        self._errormsg = errormsg
        
    def __repr__(self):
        strValue = "[Error class]: CMDExecutorError" + "\n[Command]: " + self._cmdline + "\n[Error Message]:\n" + self._errormsg
        return strValue
    
if __name__ == "__main__":
    cmd = CMDExecutor("git branch1")
    try:
        output = cmd.execute()
    except CMDExecutorError as cmderr:
        print cmderr
    else:
        print output