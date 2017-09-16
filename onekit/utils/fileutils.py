#!/usr/bin/env python
from ..cierrors import CIBasicError

class FileManager:
    @staticmethod
    def saveTextFile(filepath, content):
        try:
            with open(filepath, "w") as f:
                f.write(content)
        except Exception as err:
            raise FileManagerError("Failed on method saveTextFile", err)

class FileManagerError(CIBasicError):
    def __init__(self, errormsg, cause=None):
        CIBasicError.__init__(self, errormsg, cause)

    def __str__(self):
        return self.stackError

    def __repr__(self):
        return self.stackError