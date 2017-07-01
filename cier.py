#!/usr/bin/env python

import os
import urllib2
import re
import subprocess
import xml.etree.ElementTree as ET
import argparse
import sys

ALL_REPOS = ['test-repo1', 'test-repo2', 'tests-repo3']

class PathStackMgr(object):
    def __init__(self):
        self.pathStack = list()
        
    def pushd(self, path):
        try:
            currentPath = os.getcwd()
            self.pathStack.append(currentPath)
            os.chdir(path)
        except Exception as err:
            print err
            raise
        
    def popd(self):
        try:
            if(len(self.pathStack) > 0):
                os.chdir(self.pathStack.pop())
        except Exception as err:
            print err
            raise
            

class Repo(object):
    def __init__(self, name, commit, branch):
        self._name = name
        self._commit = commit
        self._branch = branch
        self._buildneeded = False
    
    def __str__(self):
        return "%s.commit=%s\n%s.branch=%s\n%s.buildneeded=%s" % (self._name, self._commit, self._name, self._branch, self._name, self._buildneeded)
    
    @property
    def name(self):
        return self._name
    
    @property
    def commit(self):
        return self._commit
    
    @property    
    def branch(self):
        return self._branch
    
    @property
    def buildneeded(self):
        return self._buildneeded
    
    @buildneeded.setter
    def buildneeded(self,value):
        self._buildneeded = value
        
    

def _get_changed_repos(buildurl):
    '''
    buildurl - Jenkins build url (i.e. http://localhost:8080/jenkins/view/test/job/copd-multi/9/changes)
    return - list of string
    '''
    data = urllib2.urlopen(buildurl).read()
    pattern=r"Project:\s((?!\.repo).*)<br.*>"
    changesre = re.compile(pattern)
    changes = [x.strip() for x in changesre.findall(data)]
    return changes

def _get_repos_buildneeded(buildurl, forcebuilds=None):
    reposneedbuild = [] 
    if(forcebuilds and forcebuilds == "all"):
        reposneedbuild = ALL_REPOS
    elif(forcebuilds):
        reposneedbuild = forcebuilds
    else:  
        changedRepos = _get_changed_repos(buildurl)
        if('copd-repo1' in changedRepos):
            reposneedbuild = ALL_REPOS
        else:
            reposneedbuild = changedRepos
            
    return reposneedbuild

def _gen_prop_file(props, builddir, ofile='build-info.properties'):
    """
    props - Dictionary, {'version.major':'9','version.minor':'50','version.build':'0015', ...}
    """
    if(len(props) > 0):
        f = None
        try:
            f = file(builddir + os.sep + ofile,'w+');
            for (k,v) in props.items():
                f.write(k + '=' + v + '\n')
                
            f.close()
        except  IOError as ioe:
            message = "\nIOError: " + "[Errno " + str(ioe.errno) + "] " + ioe.strerror + ": " + ioe.filename
            raise Exception(message)
        except Exception as e:
            message = "Failed to generate build info property file!\n" + e.message
            raise Exception(message)
        finally:
            if(f):
                f.close()
    else:
        message = "Your should provie an non-empty dict props"
        raise Exception(message)
    
    
def _get_local_builddir_info(builddir, buildurl, forcebuilds=None):
    ps = PathStackMgr()
    output = ""
    repolist = []
    try:
        cmd = "repo manifest -r"
        ps.pushd(builddir)
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
    except Exception as err:
        print err
    finally:
        ps.popd()
        
    root = ET.fromstring(output)
    defaultNode = root.find('default')
    if(defaultNode is None):
        raise("Can't find the default node from manifest")

    for project in root.iter('project'):
        repolist.append(Repo(project.attrib['name'], project.attrib['revision'], project.attrib['upstream']))
    
    buildNeeded = _get_repos_buildneeded(buildurl, forcebuilds)
    for repo in repolist:
        if(repo.name in buildNeeded):
            repo.buildneeded = True
    
    return repolist

def _get_next_buildnumber(productversion, builddir):
    ps = PathStackMgr()
    iBuildNumber = 1
    output = ""
    try:
        cmd = "git tag -l copd-%s-* --sort=-version:refname" % productversion 
        ps.pushd(builddir + os.sep + ".repo" + os.sep + "manifests")
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
    except Exception as err:
        print err
    finally:
        ps.popd()
    
    if(output):
        loutput = output.split('\n')
        pretag = loutput[0]
        m = re.search("^copd-" + productversion + "-b(.*)$", pretag)
        sBuildNumber = m.group(1)
        iBuildNumber = int(sBuildNumber) + 1

    return iBuildNumber

def get_buildinfo(productversion, builddir, buildurl, forcebuilds=None):
    buidnumber = _get_next_buildnumber(productversion, builddir)
    buildtag = "copd-" + productversion + "-b" + str(buidnumber)
    buildversion = productversion + "-b" + str(buidnumber)
    props={}
    props['build.number'] = str(buidnumber)
    props['build.version'] = buildversion
    props['build.tag'] = buildtag
    
    blist = _get_local_builddir_info(builddir, buildurl, forcebuilds)
    for b in blist:
        props[b.name + '.build.needed'] = str(b.buildneeded)
        props[b.name + '.build.commit'] = b.commit
        props[b.name + '.build.branch'] = b.branch
        
    _gen_prop_file(props, builddir)
    
def prebuild(args):
    lforcebuilds = None
    if(args["forcebuilds"]):
        if(args["forcebuilds"] == "all"):
            lforcebuilds = "all"
        else:
            lforcebuilds = args["forcebuilds"].split(',')
    
    print "lforcebuilds = %s" % lforcebuilds
    
    get_buildinfo(args["prodversion"], args["builddir"], args["buildurl"], lforcebuilds)

def postbuild(args):
        pass
    
def main(argv):
    # python cikit.py
    #
    parser = argparse.ArgumentParser(prog='cier', 
                                     description="cier to assist CI/CD construction")

    subparsers = parser.add_subparsers(help='commands')
    
    # python cier.py <prebuild|postbuild>
    #
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument('--builddir', action='store', 
                              dest='builddir',
                              required=True, 
                              help='Store the local work directory of current build')
    
    parent_parser.add_argument('--buildurl', action='store', 
                              dest='buildurl',
                              required=True,
                              help='Store current jenkins build url')

    parent_parser.add_argument('--buildname', action='store', 
                              dest='buildname',
                              help='Store current build name')

    parent_parser.add_argument('--prodversion', action='store', 
                              dest='prodversion',
                              required=True,
                              help='Store the version of current building product or component')
    
    parent_parser.add_argument('--forcebuilds', action='store', 
                              dest='forcebuilds',
                              help='Store the manually kicked off builds')

    parser_prebuild = subparsers.add_parser('prebuild', 
                                            help='Build supported toolkits for pre-build stage', 
                                            parents=[parent_parser])

    parser_prebuild.set_defaults(func=prebuild)

    parser_postbuild = subparsers.add_parser('postbuild',
                                            help='Build supported toolkits for post-build stage',
                                            parents=[parent_parser])
    parser_postbuild.set_defaults(func=postbuild)
    
    args = parser.parse_args(argv[1:])
    dictargs = vars(args)
    args.func(dictargs)
    
if __name__ == "__main__":
    main(sys.argv)
    #build = _get_repos_buildneeded("http://localhost:8080/jenkins/job/copd-multi/11/changes", forcebuilds="all")
    #for x in build:
    #    print x