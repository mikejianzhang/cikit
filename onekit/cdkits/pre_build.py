#!/usr/bin/env python
from enum import Enum
from command import Command

cmdName = 'prebuild'
className = 'PreBuild'

class RepoType(Enum):
    single = 1
    multi_repo = 2
    multi_natural = 3
    
class ProductType(Enum):
    simple = 1
    composite = 2

class PreBuild(Command):
    def execute(self, args):
        pass
        
if __name__ == "__main__":
    from service import *
    print "h"