#!/usr/bin/env python
import sys
import subprocess
from pathmanager import PathStackMgr
from ..cierrors import CIBasicError

class CMDExecutor:
    def __init__(self, cmdline, workdir):
        """
        :param cmdline: string
        :param workdir: string
        """
        assert isinstance(cmdline,(str,unicode)) and len(cmdline) > 0,\
                "cmdline must be type string and not empty"

        assert isinstance(workdir,(str,unicode)) and len(workdir) > 0,\
                "workdir must be type string and not empty"
        
        self._cmdline = cmdline
        self._workdir = workdir
        self._pathStack = PathStackMgr()
        
    def execute(self):
        output=''
        try:
            self._pathStack.pushd(self._workdir)
            output=subprocess.check_output(self._cmdline, stderr=subprocess.STDOUT, shell=True)
            self._pathStack.popd()
        except subprocess.CalledProcessError as cperr:
            raise CMDExecutorError(self._cmdline, cperr.returncode, cperr.output, cperr)
        except Exception as err:
            raise CMDExecutorError(self._cmdline, 1, "Failed on method execute", err)
        else:
            return output
        
class CMDExecutorError(CIBasicError):
    def __init__(self, cmdline, errorcode, errormsg, cause=None):
        CIBasicError.__init__(self, errormsg, cause)
        self._cmdline = cmdline
        self._errorcode = errorcode
        
    def __repr__(self):
        return self.stackError
    
    def __str__(self):
        return self.stackError
    
    @property
    def error(self):
        value = super(self.__class__,self).error
        value += "\n[CMD]: " + self._cmdline + \
                "\n[CMD Error Code]: " + str(self._errorcode)
        return value
    
if __name__ == "__main__":
    try:
        cmd = CMDExecutor("git tag","/Users/mike/Documents/MikeWorkspace/FreessureCoffee/service")
        output = cmd.execute()
    except Exception as err:
        print err
    else:
        print output