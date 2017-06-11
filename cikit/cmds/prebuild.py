#!/usr/bin/env python
from command import Command
from ..cibuild import CIBuild

cmdName = 'prebuild'
className = 'PreBuild'

class PreBuild(Command):
    def execute(self, args):
        ciBuild = CIBuild(args['workdir'], args['prodversion'], args['buildname'], args['gitremote'])
        ciBuild.prebuild(args['savebuildinfo'])