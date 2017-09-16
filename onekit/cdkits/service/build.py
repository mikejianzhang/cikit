#!/usr/bin/env python
from enum import Enum
from abc import ABCMeta,abstractproperty,abstractmethod

class RepoType(Enum):
    single = 1
    multi_repo = 2
    multi_natural = 3
    
class ProductType(Enum):
    simple = 1
    composite = 2

class BuildActionType(Enum):
    pre_build = 1
    post_build = 2
    
class BuildAction(object):
    __metaclass__ = ABCMeta

    def __init__(self, build_action_type, build = None):
        self._build_action_type = build_action_type
        self._build = build
    
    @property
    def type(self):
        return self._build_action_type
    
    @property
    def build(self):
        return self._build

    @build.setter
    def build(self, build):
        self._build = build

    @abstractmethod
    def run(self):
        pass
        

class Build(object):
    __metaclass__ = ABCMeta
    def __init__(self):
        self._build_actions = {}
        
    def add_build_action(self, build_action):
        if(self._build_actions[str(build_action.type)]):
            self._build_actions[str(build_action.type)] = []
        
        self._build_actions[str(build_action.type)].append(build_action)
        build_action.build = build
        
    def run(self, build_action_type):
        for ba in self._build_actions[str(build_action_type)]:
            ba.run()
            