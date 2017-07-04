#!/usr/bin/env python

import os
import urllib2
import re
import subprocess
import xml.etree.ElementTree as ET
import argparse
import sys
import requests
import json

ALL_REPOS = ['copd-repo1', 'copd-repo2', 'copd-repo3']

def _dash_to_underscore(value):
    return value.replace("-", "_")

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
            

class SimpleRestClient:
    @staticmethod
    def getJSONContent(url):
        content = SimpleRestClient.getStringContent(url)
        
        # Loading the response data into a dict variable
        # json.loads takes in only binary or string variables so using content to fetch binary content
        # Loads (Load String) takes a Json file and converts into python data structure (dict or list, depending on JSON)
        jData = json.loads(content)            
        return jData
    
    @staticmethod
    def getStringContent(url):
        myResponse = requests.get(url, verify=False)
        
        if(not myResponse.ok):
            # If response code is not ok (200), print the resulting http error code with description
            myResponse.raise_for_status()

        return myResponse.content

class Repo(object):
    def __init__(self, name, commit, branch):
        self._name = name
        self._commit = commit
        self._branch = branch
        self._buildneeded = False
    
    def __str__(self):
        return "%s_commit=%s\n%s_branch=%s\n%s_buildneeded=%s" % (_dash_to_underscore(self._name), self._commit, _dash_to_underscore(self._name), self._branch, _dash_to_underscore(self._name), self._buildneeded)
    
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
    Get all changed repos since last successful builds which deal with multi builds in parallel.
    buildurl - Jenkins build url (i.e. http://localhost:8080/jenkins/view/test/job/copd-multi/9/)
    return - list of string
    '''
    changedRepos = []
    pattern = "(^http:\/\/.*\/)[1-9][0-9]*\/$"
    joburl = ""
    m = re.search(pattern, buildurl)
    if(m):
        joburl = m.group(1)
        
    jdata = SimpleRestClient.getJSONContent("%sapi/json?pretty=true" % joburl)
    lastSuccessfulBuildNumber = jdata["lastSuccessfulBuild"]["number"]
    for build in jdata["builds"]:
        if(build["number"] > lastSuccessfulBuildNumber):
            crepos = _get_changed_repos_of_build(build["url"])
            for repo in crepos:
                if(repo not in changedRepos):
                    changedRepos.append(repo)
        else:
            break

    return changedRepos

def _get_changed_repos_of_build(buildurl):
    '''
    Get changed repos since last build.
    buildurl - Jenkins build url (i.e. http://localhost:8080/jenkins/view/test/job/copd-multi/9)
    return - list of string
    '''
    changedRepos = []
    buildchangeurl = "%schanges" % buildurl
    data = urllib2.urlopen(buildchangeurl).read()
    pattern=r"Project:\s((?!\.repo).*)<br.*>"
    changesre = re.compile(pattern)
    if(changesre):
        changedRepos = [x.strip() for x in changesre.findall(data)]

    return changedRepos

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

def _get_next_buildnumber(prodname, prodversion, builddir):
    ps = PathStackMgr()
    iBuildNumber = 1
    output = ""
    try:
        cmd = "git tag -l %s_%s_* --sort=-version:refname" % (prodname, prodversion)
        ps.pushd(builddir + os.sep + ".repo" + os.sep + "manifests")
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
        if(output):
            loutput = output.split('\n')
            pretag = loutput[0]
            pattern = "^%s_%s_b(.*)$" % (prodname, prodversion)
            m = re.search(pattern, pretag)
            if(m):
                sBuildNumber = m.group(1)
                iBuildNumber = int(sBuildNumber) + 1
        
    except Exception as err:
        print err
    finally:
        ps.popd()
    
    return iBuildNumber

def _get_manifest_info(builddir):
    ps = PathStackMgr()
    manifestUrl = ""
    manifestBranch = ""
    manifestCommit = ""
    try:
        cmd = "git remote -vv"
        ps.pushd(builddir + os.sep + ".repo" + os.sep + "manifests")
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
        if(output):
            loutput = output.split('\n')
            firstline = loutput[0]
            pattern = ".*(ssh:\/\/.*).*\(fetch\)$"
            m = re.search(pattern, firstline)
            if(m):
                manifestUrl = m.group(1)
        
        cmd = "git branch -vv"
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
        if(output):
            pattern = ".*\[origin\/(.+)\].*"
            m = re.search(pattern, output)
            if(m):
                manifestBranch = m.group(1)
                
        cmd = "git rev-parse HEAD"
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
        if(output):
            manifestCommit = output
                
        
    except Exception as err:
        print err
    finally:
        ps.popd()
    
    return (manifestUrl, manifestBranch, manifestCommit)

def get_buildinfo(prodname, prodversion, builddir, buildurl, forcebuilds=None):
    buidnumber = _get_next_buildnumber(prodname, prodversion, builddir)
    buildversion = "%s_b%s" % (prodversion, str(buidnumber))
    buildtag = "%s_%s_b%s" % (prodname, prodversion, str(buidnumber))
    manifesturl, manifestBranch, manifestCommit = _get_manifest_info(builddir)
    props={}
    props['product_name'] = prodname
    props['product_version'] = prodversion
    props['product_build_tag'] = buildtag
    props['product_manifest_url'] = manifesturl
    props['product_manifest_branch'] = manifestBranch
    props['product_manifest_commit'] = manifestCommit
    blist = _get_local_builddir_info(builddir, buildurl, forcebuilds)
    for b in blist:
        props[_dash_to_underscore(b.name) + '_build_number'] = str(buidnumber)
        props[_dash_to_underscore(b.name) + '_build_version'] = buildversion
        props[_dash_to_underscore(b.name) + '_build_tag'] = buildtag
        props[_dash_to_underscore(b.name) + '_build_needed'] = str(b.buildneeded)
        props[_dash_to_underscore(b.name) + '_build_commit'] = b.commit
        props[_dash_to_underscore(b.name) + '_build_branch'] = b.branch
        
    _gen_prop_file(props, builddir)
    
def prebuild(args):
    lforcebuilds = None
    if(args["forcebuilds"] and args["forcebuilds"] != "none"):
        if(args["forcebuilds"] == "all"):
            lforcebuilds = "all"
        else:
            lforcebuilds = args["forcebuilds"].split(',')
    
    print "lforcebuilds = %s" % lforcebuilds
    
    get_buildinfo(args["prodname"], args["prodversion"], args["builddir"], args["buildurl"], lforcebuilds)

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
    parent_parser.add_argument('--prodname', action='store', 
                              dest='prodname',
                              required=True, 
                              help='Store the product')

    parent_parser.add_argument('--prodversion', action='store', 
                              dest='prodversion',
                              required=True,
                              help='Store the version of current building product or component')

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
    #print _dash_to_underscore("test-repo1-yes")
    #build = _get_repos_buildneeded("http://localhost:8080/jenkins/job/copd-multi/11/changes", forcebuilds="all")
    #for x in build:
    #    print x
    #get_buildinfo("copd", "1.0.0", r"C:\Users\310276411\MyJenkins\local\workspace\copd-cibuild", "http://localhost:8080/jenkins/view/test/job/copd-cibuild/34/changes")
    #changedRepos = _get_changed_repos("http://localhost:8080/jenkins/view/test/job/copd-test-parallel-cibuild/11/")
    #print changedRepos