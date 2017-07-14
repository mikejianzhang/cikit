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
import copy
from requests.auth import HTTPBasicAuth
from properties.p import Property
from errno import EMSGSIZE

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
    def getJSONContent(url, username=None, password=None):
        content = SimpleRestClient.getStringContent(url, username, password)
        
        # Loading the response data into a dict variable
        # json.loads takes in only binary or string variables so using content to fetch binary content
        # Loads (Load String) takes a Json file and converts into python data structure (dict or list, depending on JSON)
        jData = json.loads(content)            
        return jData
    
    @staticmethod
    def getStringContent(url, username=None, password=None):
        jauth = HTTPBasicAuth(username,password) if (username and password) else None
        myResponse = requests.get(url, verify=False, auth=jauth)
        
        if(not myResponse.ok):
            # If response code is not ok (200), print the resulting http error code with description
            myResponse.raise_for_status()

        return myResponse.content

class Repo(object):
    def __init__(self, name, commit, abbrev_commit, branch, author):
        self._name = name
        self._commit = commit
        self._abbrevcommit = abbrev_commit
        self._author = author
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
    def abbrevcommit(self):
        return self._abbrevcommit
    
    @property
    def author(self):
        return self._author
    
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
        
    juname = os.getenv("jenkins_user")
    jpassword = os.getenv("jenkins_user_password")
        
    jdata = SimpleRestClient.getJSONContent("%sapi/json?pretty=true" % joburl, juname, jpassword)
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
    juname = os.getenv("jenkins_user")
    jpassword = os.getenv("jenkins_user_password")
    data = SimpleRestClient.getStringContent(buildchangeurl, juname, jpassword)
    pattern=r"Project:\s((?!\.repo).*)<br.*>"
    changesre = re.compile(pattern)
    if(changesre):
        changedRepos = [x.strip() for x in changesre.findall(data)]

    return changedRepos

def _calculate_repos_buildneeded(builddir, currentRepos):
    reposBuildNeeded = []
    try:
        repoGraphFile = builddir + os.sep + ".repo" + os.sep + "manifests" + os.sep + "repo_graph.json"
        f = file(repoGraphFile,'r+');
        s = json.load(f)
        repoGraph = {}
        for i in range(len(s)):
            repoGraph["%s" % s[i]['name']] = s[i]['impact']
            
        if(currentRepos == "all"):
            reposBuildNeeded = repoGraph.keys()
        else:
            reposBuildNeeded = copy.deepcopy(currentRepos)
            for r in reposBuildNeeded:
                impactRepos = repoGraph[r]
                if(impactRepos and len(impactRepos) > 0):
                    for ir in impactRepos:
                        if ir not in reposBuildNeeded:
                            reposBuildNeeded.append(ir)
    except  IOError as ioe:
        message = "\nIOError: " + "[Errno " + str(ioe.errno) + "] " + ioe.strerror + ": " + ioe.filename
        raise ioe
    except Exception as e:
        message = "Failed to generate build info property file!\n" + e.message
        raise e
    finally:
        if(f):
            f.close()
            
    return reposBuildNeeded

def _get_repos_buildneeded(builddir, buildurl, forcebuilds=None):
    reposneedbuild = [] 
    if(forcebuilds):
        reposneedbuild = _calculate_repos_buildneeded(builddir, forcebuilds)
    else:  
        changedRepos = _get_changed_repos(buildurl)
        if(changedRepos):
            reposneedbuild = _calculate_repos_buildneeded(builddir, changedRepos)
            
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
        
        root = ET.fromstring(output)
        defaultNode = root.find('default')
        if(defaultNode is None):
            raise("Can't find the default node from manifest")
    
        for project in root.iter('project'):
            cmd = "git -C %s show -s --pretty=format:%%h_%%ae %s" % (project.attrib['name'], project.attrib['revision'])
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
            if(output):
                output = output.strip()
                loutput = output.split('_')
                repolist.append(Repo(project.attrib['name'], project.attrib['revision'], loutput[0], project.attrib['upstream'], loutput[1]))
        
    except Exception as err:
        print err
        raise err
    finally:
        ps.popd()
        
    buildNeeded = _get_repos_buildneeded(builddir, buildurl, forcebuilds)
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
    manifestRemoteBranch = ""
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
            pattern = "^\*\s(.+?)\s.*\[origin\/(.+)\]"
            m = re.search(pattern, output)
            if(m):
                manifestBranch = m.group(1)
                manifestRemoteBranch = m.group(2)
                
        cmd = "git rev-parse HEAD"
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
        if(output):
            manifestCommit = output.strip()
                
        
    except Exception as err:
        print err
    finally:
        ps.popd()
    
    return (manifestUrl, manifestBranch, manifestRemoteBranch, manifestCommit)

def get_buildinfo(prodname, prodversion, builddir, buildurl, forcebuilds=None):
    buildnumber = _get_next_buildnumber(prodname, prodversion, builddir)
    buildversion = "%s_b%s" % (prodversion, str(buildnumber))
    buildtag = "%s_%s_b%s" % (prodname, prodversion, str(buildnumber))
    manifesturl, manifestBranch, manifestRemoteBranch, manifestCommit = _get_manifest_info(builddir)
    props={}
    props['product_name'] = prodname
    props['product_version'] = prodversion
    props['product_build_number'] = str(buildnumber)
    props['product_build_version'] = buildversion
    props['product_build_tag'] = buildtag
    props['product_manifest_url'] = manifesturl
    props['product_manifest_branch'] = manifestBranch
    props['product_manifest_remote_branch'] = manifestRemoteBranch
    props['product_manifest_commit'] = manifestCommit
    blist = _get_local_builddir_info(builddir, buildurl, forcebuilds)
    for b in blist:
        props[_dash_to_underscore(b.name) + '_build_number'] = str(buildnumber)
        props[_dash_to_underscore(b.name) + '_build_version'] = buildversion
        props[_dash_to_underscore(b.name) + '_build_tag'] = buildtag
        props[_dash_to_underscore(b.name) + '_build_needed'] = str(b.buildneeded)
        props[_dash_to_underscore(b.name) + '_build_commit'] = b.commit
        props[_dash_to_underscore(b.name) + '_build_abbrevcommit'] = b.abbrevcommit
        props[_dash_to_underscore(b.name) + '_build_commit_author'] = b.author
        props[_dash_to_underscore(b.name) + '_build_branch'] = b.branch
        
    _gen_prop_file(props, builddir)
    
    return props

def tag_current_build(builddir, props):
    ps = PathStackMgr()
    try:
        cmd = "git tag %s %s" % (props["product_build_tag"], props["product_manifest_commit"])
        ps.pushd(builddir + os.sep + ".repo" + os.sep + "manifests")
        subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
        cmd = "git push origin %s" % props["product_build_tag"]
        subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
    except Exception as err:
        print err
    finally:
        ps.popd()
        
def _gen_new_packageinfo(pre_released_packageinfo, pre_build_packageinfo, current_buildprops):
    def _get_new_reposinfo(repo):
        propname_prefix = _dash_to_underscore(repo["repoName"])
        for component in repo["componets"]:
            component["storage"]["version"] = current_buildprops["%s_build_version" % propname_prefix]
        return repo
    
    def _filter_incremental_repo(repo):
        result = False
        propname_prefix = _dash_to_underscore(repo["repoName"])
        if(current_buildprops["%s_build_needed" % propname_prefix] == "True"):
            result = True
        return result

    # return (full package info, patch package info, incremental package info)
    full_build_packageinfo = copy.deepcopy(pre_build_packageinfo)
    full_build_packageinfo["version"] = current_buildprops["product_version"]
    full_build_packageinfo["buildNumber"] = current_buildprops["product_build_number"]
    full_build_packageinfo["storage"]["version"] = current_buildprops["product_build_version"]
    full_build_packageinfo["repos"] = map(_get_new_reposinfo, full_build_packageinfo["repos"])
    
    incremental_packageinfo = {}
    incremental_packageinfo["product"] = full_build_packageinfo["product"]
    incremental_packageinfo["version"] = full_build_packageinfo["version"]
    incremental_packageinfo["buildNumber"] = full_build_packageinfo["buildNumber"]
    incremental_packageinfo["storage"] = copy.deepcopy(full_build_packageinfo["storage"])
    incremental_packageinfo["storage"]["classifier"] = "increment"
    incremental_packageinfo["repos"] = filter(_filter_incremental_repo, full_build_packageinfo["repos"])
    
    return (full_build_packageinfo, incremental_packageinfo)


def _save_packageinfo(packageinfo, outfile):
    try:
        f = open(outfile, 'w')
        json.dump(packageinfo, f)
    except IOError as ioe:
        emsg = "I/O error({0}): {1}: file({2})".format(ioe.errno, ioe.strerror, ioe.filename)
        print emsg
    except Exception as e:
        emsg = "Failed to serialize json object:{0}".format(sys.exc_info()[0])
        print emsg
    finally:
        if(f):
            f.close()

def _load_packageinfo_fromfile(infile):
    try:
        f = file(infile,'r+');
        s = json.load(f)
        return s
    except IOError as ioe:
        emsg = "I/O error({0}): {1}: file({2})".format(ioe.errno, ioe.strerror, ioe.filename)
        print emsg
    except Exception as e:
        emsg = "Failed to deserialize json object:{0}".format(sys.exc_info()[0])
        print emsg
    finally:
        if(f):
            f.close()
            
def _load_packageinfo_fromstring(invalue):
    try:
        s = json.loads(invalue)
        return s
    except Exception as e:
        message = "Failed to generate build info property file!\n" + e.message
        raise e
            
def _load_buildproperties(inpropfile):
    prop = Property()
    dict_prop = prop.load_property_files(inpropfile)
    return dict_prop

def _compare_packageinfo(packageinfo1, packageinfo2):
    # 1: greater than; 0: equal; -1: less than
    result = None
    if(packageinfo1["version"] > packageinfo2["version"]):
        result = 1
    elif(packageinfo1["version"] < packageinfo2["version"]):
        result = -1
    else:
        if(packageinfo1["buildNumber"] > packageinfo2["buildNumber"]):
            result = 1
        elif(packageinfo1["buildNumber"] < packageinfo2["buildNumber"]):
            result = -1
        else:
            result = 0
            
    return result

def prebuild(args):
    lforcebuilds = None
    if(args["forcebuilds"] and args["forcebuilds"] != "none"):
        if(args["forcebuilds"] == "all"):
            lforcebuilds = "all"
        else:
            lforcebuilds = args["forcebuilds"].split(',')
    
    props = get_buildinfo(args["prodname"], args["prodversion"], args["builddir"], args["buildurl"], lforcebuilds)
    tag_current_build(args["builddir"], props)

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
    #main(sys.argv)
    #print _dash_to_underscore("test-repo1-yes")
    #build = _get_repos_buildneeded("http://localhost:8080/jenkins/job/copd-multi/11/changes", forcebuilds="all")
    #for x in build:
    #    print x
    #get_buildinfo("copd", "1.0.0", r"C:\Users\310276411\MyJenkins\local\workspace\copd-cibuild", "http://localhost:8080/jenkins/view/test/job/copd-cibuild/34/changes")
    #changedRepos = _get_changed_repos("http://localhost:8080/jenkins/view/test/job/copd-test-parallel-cibuild/11/")
    #print changedRepos
    #print _calculate_repos_buildneeded("/Users/mike/Documents/MikeWorkspace/Philips/workspace/test", 'all')
    #print _get_manifest_info("/Users/mike/Documents/MikeWorkspace/Philips/workspace/test")
    ps = PathStackMgr()
    try:
        cmd = "git --no-pager show %s:%s" % ("master", "sample/package.json")
        ps.pushd(r"C:\Users\310276411\MyWork\GitHub\cikit")
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
        s = _load_packageinfo_fromstring(output)
        current_buildprops = _load_buildproperties(r"C:\Users\310276411\MyWork\GitHub\cikit\sample\build-info.properties")
        (full_packageinfo, increment_packageinfo) = _gen_new_packageinfo(s, s, current_buildprops)
        print full_packageinfo
        print increment_packageinfo
    except Exception as err:
        print err
    finally:
        ps.popd()