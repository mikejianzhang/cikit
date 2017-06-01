#!/usr/bin/env python
import subprocess

class CMDExecutor:
    def __init__(self, cmdline):
        self._cmdline = cmdline
        
    def execute(self):
        output=''
        try:
            output=subprocess.check_output(self._cmdline, stderr=subprocess.STDOUT, shell=True)
        except subprocess.CalledProcessError as err:
            raise CMDExecutorError(self._cmdline, err.returncode, err.output)
        else:
            return output
        
class CMDExecutorError(Exception):
    def __init__(self, cmdline, errorcode, errormsg):
        self._cmdline = cmdline
        self._errorcode = errorcode
        self._errormsg = errormsg
        
    def __str__(self):
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