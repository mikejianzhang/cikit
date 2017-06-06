import sys
import argparse
from cikit.cibuild import CIBuild

def _main(argv):
    parser = argparse.ArgumentParser(prog='cikit', usage="cikit command")
    subparsers = parser.add_subparsers(help='sub-command help')
    parser_build = subparsers.add_parser('build')
    parser_build.add_argument('--workdir', action='store', dest='workdir')
    parser_build.add_argument('--buildname', action='store', dest='buildname')
    parser_build.add_argument('--prodversion', action='store', dest='prodversion')
    parser_build.add_argument('--gitremote', action='store', dest='gitremote')
    subparsers_build = parser_build.add_subparsers(help='sub-command help')
    parser_prebuild = subparsers_build.add_parser('prebuild')
    
    print parser.parse_args(["build", "--workdir='???'", "--buildname='???'", "--prodversion='???'", "--gitremote='???'", "prebuild"])
    
    
if __name__ == "__main__":
    _main(sys.argv[1:])