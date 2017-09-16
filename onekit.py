import sys
import argparse
#from cikit.cmds import all_commands

def _commander(cmdName):
    def runCMD(args):
        cmd = all_commands[cmdName]
        cmd.execute(args)
    
    return runCMD

def _main(argv):
    # python cikit.py
    #
    parser = argparse.ArgumentParser(prog='cikit', 
                                     description="cikit to assist CI/CD construction")

    subparsers = parser.add_subparsers(help='commands')
    
    # python cikit.py <prebuild|postbuild>
    #
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument('--workdir', action='store', 
                              dest='workdir',
                              required=True, 
                              help='Store the local work directory of current build')

    parent_parser.add_argument('--buildname', action='store', 
                              dest='buildname',
                              required=True,
                              help='Store current build name')

    parent_parser.add_argument('--prodversion', action='store', 
                              dest='prodversion',
                              required=True,
                              help='Store the version of current building product or component')

    parent_parser.add_argument('--gitremote', action='store', 
                              dest='gitremote',
                              default='origin',
                              required=True,
                              help='Store git remote name of current building work directory')

    parser_prebuild = subparsers.add_parser('prebuild', 
                                            help='Build supported toolkits for pre-build stage', 
                                            parents=[parent_parser])
    parser_prebuild.add_argument('--savebuildinfo', action='store_true',
                                 dest='savebuildinfo',
                                 default=False,
                                 help='Set savebuildinfo to true to save build info into file')
    parser_prebuild.set_defaults(func=_commander('prebuild'))

    parser_postbuild = subparsers.add_parser('postbuild',
                                            help='Build supported toolkits for post-build stage',
                                            parents=[parent_parser])
    parser_postbuild.set_defaults(func=_commander('postbuild'))
    
    args = parser.parse_args(argv[1:])
    dictargs = vars(args)
    args.func(dictargs)
    
    
if __name__ == "__main__":
    #_main(sys.argv)
    from onekit.cdkits.service import *
    print "hello"