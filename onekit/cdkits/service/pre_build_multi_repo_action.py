#!/usr/bin/env python
from build import BuildAction, BuildActionType

class PreBuildMultiRepoAction(BuildAction):
    def __init__(self, *args, **kargs):
        BuildAction.__init__(BuildActionType.pre_build)
        
    def run(self):
        pass