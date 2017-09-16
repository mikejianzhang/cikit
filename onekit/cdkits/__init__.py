#!/usr/bin/env python
import os

all_commands={}

my_dir = os.path.dirname(__file__)
for py in os.listdir(my_dir):
  if py == '__init__.py' or py == 'command.py':
    continue

  if py.endswith('.py'):
    name = py[:-3]
    mod = __import__(__name__,
                     globals(),
                     locals(),
                     ['%s' % name])
    mod = getattr(mod, name)
    try:
        cmdn = getattr(mod, 'cmdName')
        clsn = getattr(mod, 'className')
        cmd = getattr(mod, clsn)()
        all_commands[cmdn] = cmd
    except AttributeError:
      raise SyntaxError('%s/%s does not define class %s' % (
                         __name__, py, clsn))