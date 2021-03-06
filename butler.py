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
import hashlib
import shutil
from requests.auth import HTTPBasicAuth
from properties.p import Property
import platform

def _dash_to_underscore(value):
    return value.replace("-", "_")

class ButlerConfig(object):
    _home = os.path.expanduser("~") + os.path.sep
    _butler_data = os.path.join(_home,".butler","data") + os.path.sep
    _jenkins = {}
    _arts = {}
    _redis = {}
    _all_jenkins = None
    _all_arts = None
    _all_redis = None
    @staticmethod
    def load():
        if(not os.path.exists(os.path.join(ButlerConfig._home,".butler"))):
            os.mkdir(os.path.join(ButlerConfig._home,".butler"))
            
        if(not os.path.exists(os.path.join(ButlerConfig._home,".butler", "butler.conf"))):
            config_template = {}
            jenkins = []
            jenkins.append({"url":"http(s)://xxxx:8080/jenkins/", "user":"<user>", "password":"<password>",
                            "serverId":"<jenkins-id>", "isDefault":"true"})
            config_template["jenkins"] = jenkins
            
            arts = []
            arts.append({"url": "http(s)://xxxx:8080/artifactory/",
                         "apiKey": "<key>",
                         "serverId": "mikepro-artifactory",
                         "isDefault": "true"})
            config_template["artifactory"] = arts
            
            redis = []
            redis.append({"host": "mikepro.local",
                          "port": "6379",
                          "serverId": "mikepro-redis",
                          "downloadRepo":"<downloadrepo>",
                          "uploadRepo":"<uploadrepo",
                          "isDefault": "true"})
            config_template["redis"] = redis
            
            _serialize_jsonobject(config_template, os.path.join(ButlerConfig._home,".butler", "butler.conf.template"))
            raise Exception("You need to modify template configure %s and remove .template from file name before running butler" % (os.path.join(ButlerConfig._home,".butler", "butler.conf.template"),))

        config_obj = _deserialize_jsonobject(os.path.join(ButlerConfig._home,".butler", "butler.conf"))
        ButlerConfig._all_jenkins = config_obj["jenkins"]
        ButlerConfig._all_arts = config_obj["artifactory"]
        ButlerConfig._all_redis = config_obj["redis"]

        for j in config_obj["jenkins"]:
            server_id = j["serverId"]
            ButlerConfig._jenkins[server_id] = j
            if(j["isDefault"] == "true"):
                ButlerConfig._jenkins["default"] = j
                
        for art in config_obj["artifactory"]:
            server_id = art["serverId"]
            ButlerConfig._arts[server_id] = art
            if(art["isDefault"] == "true"):
                ButlerConfig._arts["default"] = art
                
        for r in config_obj["redis"]:
            server_id = r["serverId"]
            ButlerConfig._redis[server_id] = r
            if(r["isDefault"] == "true"):
                ButlerConfig._redis["default"] = r
                
        if(not os.path.exists(ButlerConfig._butler_data)):
            os.mkdir(ButlerConfig._butler_data)
    
    @staticmethod
    def home():
        return ButlerConfig._home
    
    @staticmethod
    def datadir():
        return ButlerConfig._butler_data

    @staticmethod
    def jenkins(server_id):
        j = ButlerConfig._jenkins[server_id]
        if(not j):
            raise Exception("Jenkins %s doesn't exist!" % (server_id,))
        return (j["url"], j["user"], j["password"])
    
    @staticmethod
    def default_jenkins():
        return ButlerConfig.jenkins("default")
    
    @staticmethod
    def all_jenkins():
        return ButlerConfig._all_jenkins
    
    @staticmethod
    def artifactory(server_id):
        art = ButlerConfig._arts[server_id]
        if(not art):
            raise Exception("Artifactory %s doesn't exist!" % (server_id,))
        return (art["url"], art["serverId"], art["downloadRepo"], art["uploadRepo"])
    
    @staticmethod
    def default_artifactory():
        return ButlerConfig.artifactory("default")
    
    @staticmethod
    def all_artifactories():
        return ButlerConfig._all_arts
    
    @staticmethod
    def redis(server_id):
        r = ButlerConfig._redis[server_id]
        if(not r):
            raise Exception("Redis %s doesn't exist!" % (server_id,))
        return (r["host"], r["port"], r["serverId"])
    
    @staticmethod
    def default_redis():
        return ButlerConfig.redis("default")
    
    @staticmethod
    def all_redis():
        return ButlerConfig._all_redis
        

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

class FileManager(object):
    @staticmethod
    def _create_link(src, dest, linktype):
        if(platform.system().upper() == "WINDOWS"):
            import ctypes
            flags = 1 if src is not None and os.path.isdir(src) else 0
            if(linktype == "link"):
                if not ctypes.windll.kernel32.CreateHardLinkA(dest, src, flags):  # @UndefinedVariable
                    raise OSError
            elif(linktype == "symlink"):
                if not ctypes.windll.kernel32.CreateSymbolicLinkA(dest, src, flags):  # @UndefinedVariable
                    raise OSError
        else:
            if(linktype == "link"):
                os.link(src, dest)  # @UndefinedVariable
            elif(linktype == "symlink"):
                os.symlink(src, dest)  # @UndefinedVariable

    @staticmethod
    def saveTextFile(filepath, content):
        try:
            with open(filepath, "w") as f:
                f.write(content)
        except Exception as err:
            print err

    @staticmethod
    def gen_file_md5sum(filepath, save=True):
        target_md5sum_file = filepath + ".md5"
        fchs = hashlib.md5(filepath).hexdigest()
        if(save):
            FileManager.saveTextFile(target_md5sum_file, fchs)
        return fchs
    
    @staticmethod
    def create_symbolic_link(src, dest):
        FileManager._create_link(src, dest, "symlink")
    
    @staticmethod
    def create_hard_link(src, dest):
        FileManager._create_link(src, dest, "link")

class Repo(object):
    def __init__(self, name, commit, abbrev_commit, branch, author, pre_version):
        self._name = name
        self._commit = commit
        self._abbrevcommit = abbrev_commit
        self._author = author
        self._branch = branch
        self._buildneeded = False
        self._pre_version = pre_version
    
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
    def preversion(self):
        return self._pre_version
    
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
        
    (jurl, juname, jpassword) = ButlerConfig.default_jenkins()
        
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
    (jurl, juname, jpassword) = ButlerConfig.default_jenkins()
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
    
    
def _get_local_builddir_info(builddir, buildurl, manifest_branch, forcebuilds=None):
    ps = PathStackMgr()
    output = ""
    repolist = []
    try:
        ps.pushd(builddir + os.sep + ".repo" + os.sep + "manifests")
        cmd = "git --no-pager show %s:%s" % (manifest_branch, "package.json")
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
        pre_packageinfo_s = _deserialize_jsonobject_fromstring(output)
        repo_info = {}
        for r in pre_packageinfo_s["repos"]:
            rname = r["repoName"]
            repo_info[rname] = r["version"]
        ps.popd()

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
                rname  = project.attrib['name']
                repolist.append(Repo(rname, project.attrib['revision'], loutput[0], project.attrib['upstream'], loutput[1], repo_info[rname]))
        
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
    iUniqueBuildNumber = 1
    output = ""
    try:
        cmd = "git tag -l %s_%s_t* --sort=-version:refname" % (prodname, prodversion)
        ucmd = "git tag -l %s_u* --sort=-version:refname" % (prodname)
        ps.pushd(builddir + os.sep + ".repo" + os.sep + "manifests")
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
        uoutput = subprocess.check_output(ucmd, stderr=subprocess.STDOUT, shell=True)
        if(output):
            loutput = output.split('\n')
            pretag = loutput[0]
            pattern = "^%s_%s_t(.*)$" % (prodname, prodversion)
            m = re.search(pattern, pretag)
            if(m):
                sBuildNumber = m.group(1)
                iBuildNumber = int(sBuildNumber) + 1
        
        if(uoutput):
            luoutput = uoutput.split('\n')
            pretag = luoutput[0]
            pattern = "^%s_u(.*)$" % (prodname)
            m = re.search(pattern, pretag)
            if(m):
                sUniqueBuildNumber = m.group(1)
                iUniqueBuildNumber = int(sUniqueBuildNumber) + 1
        
    except Exception as err:
        print err
    finally:
        ps.popd()
    
    return (iBuildNumber, iUniqueBuildNumber)

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
    (buildnumber, uniquebuildnumber) = _get_next_buildnumber(prodname, prodversion, builddir)
    buildversion = "%s_b%s" % (prodversion, str(buildnumber))
    buildtag = "%s_%s_t%s" % (prodname, prodversion, str(buildnumber))
    ubuildtag = "%s_u%s" % (prodname, str(uniquebuildnumber))
    manifesturl, manifestBranch, manifestRemoteBranch, manifestCommit = _get_manifest_info(builddir)
    props={}
    props['product_name'] = prodname
    props['product_version'] = prodversion
    props['product_build_needed'] = "false"
    props['build_type'] = "CI"
    props['product_build_number'] = str(buildnumber)
    props['product_u_build_number'] = str(uniquebuildnumber)
    props['product_build_version'] = buildversion
    props['product_build_tag'] = buildtag
    props['product_u_build_tag'] = ubuildtag
    props['product_manifest_url'] = manifesturl
    props['product_manifest_branch'] = manifestBranch
    props['product_manifest_remote_branch'] = manifestRemoteBranch
    props['product_manifest_commit'] = manifestCommit
    blist = _get_local_builddir_info(builddir, buildurl, manifestBranch, forcebuilds)
    for b in blist:
        props[_dash_to_underscore(b.name) + '_build_number'] = str(buildnumber)
        props[_dash_to_underscore(b.name) + '_u_build_number'] = str(uniquebuildnumber)
        props[_dash_to_underscore(b.name) + '_build_version'] = buildversion
        props[_dash_to_underscore(b.name) + '_build_tag'] = buildtag
        props[_dash_to_underscore(b.name) + '_u_build_tag'] = ubuildtag
        props[_dash_to_underscore(b.name) + '_build_needed'] = str(b.buildneeded)
        props[_dash_to_underscore(b.name) + '_build_commit'] = b.commit
        props[_dash_to_underscore(b.name) + '_build_abbrevcommit'] = b.abbrevcommit
        props[_dash_to_underscore(b.name) + '_build_commit_author'] = b.author
        props[_dash_to_underscore(b.name) + '_build_branch'] = b.branch
        if(b.buildneeded):
            props[_dash_to_underscore(b.name) + '_build_current_version'] = buildversion
            props['product_build_needed'] = "true"
        else:
            props[_dash_to_underscore(b.name) + '_build_current_version'] = b.preversion
        
    _gen_prop_file(props, builddir)
    
    return props

def create_pre_build_tag(builddir, props):
    ps = PathStackMgr()
    try:
        ps.pushd(builddir + os.sep + ".repo" + os.sep + "manifests")
        cmd_tag1 = "git tag %s %s" % (props["product_build_tag"], props["product_manifest_commit"])
        cmd_tag2 = "git tag %s %s" % (props["product_u_build_tag"], props["product_manifest_commit"])
        subprocess.check_output(cmd_tag1, stderr=subprocess.STDOUT, shell=True)
        subprocess.check_output(cmd_tag2, stderr=subprocess.STDOUT, shell=True)
        cmd_push1 = "git push origin %s" % props["product_build_tag"]
        cmd_push2 = "git push origin %s" % props["product_u_build_tag"]
        subprocess.check_output(cmd_push1, stderr=subprocess.STDOUT, shell=True)
        subprocess.check_output(cmd_push2, stderr=subprocess.STDOUT, shell=True)
        ps.popd()
    except Exception as err:
        print err
    finally:
        ps.popd()
        
def create_post_build_tag(builddir, full_packageinfo_fn):
    ps = PathStackMgr()
    try:
        props = _load_buildproperties(builddir + os.path.sep + "build-info.properties")
        ps.pushd(builddir + os.path.sep + ".repo")

        if(os.path.exists("lmanifest")):
            shutil.rmtree("lmanifest")

        cmd_clone = "git clone -b %s %s lmanifest" % (props['product_manifest_remote_branch'], props['product_manifest_url'])
        subprocess.check_output(cmd_clone, stderr=subprocess.STDOUT, shell=True)
        latest_packageinfo = _deserialize_jsonobject("lmanifest" + os.path.sep + "package.json")
        full_packageinfo = _deserialize_jsonobject(builddir + os.path.sep + full_packageinfo_fn)
        if(_compare_packageinfo(full_packageinfo, latest_packageinfo) == 1):
            shutil.copyfile(builddir + os.path.sep + full_packageinfo_fn, builddir + os.sep + ".repo" + os.path.sep + "lmanifest" + os.path.sep + "package.json")
            cmd_commit = "git -C lmanifest commit -a -m \"%s\"" % ("Update package.json with latest build " + props['product_name'] + "_" + props['product_build_version'])
            cmd_tag = "git -C lmanifest tag %s" % (props['product_name'] + "_" + props['product_build_version'])
            cmd_push_commit = "git -C lmanifest push"
            cmd_push_tag = "git -C lmanifest push origin %s" % (props['product_name'] + "_" + props['product_build_version'])
            subprocess.check_output(cmd_commit, stderr=subprocess.STDOUT, shell=True)
            subprocess.check_output(cmd_tag, stderr=subprocess.STDOUT, shell=True)
            subprocess.check_output(cmd_push_commit, stderr=subprocess.STDOUT, shell=True)
            subprocess.check_output(cmd_push_tag, stderr=subprocess.STDOUT, shell=True)

        ps.popd()
    except Exception as err:
        print err
    finally:
        ps.popd()

def _serialize_jsonobject(jobject, outfile):
    try:
        f = open(outfile, 'w')
        json.dump(jobject, f)
    except IOError as ioe:
        emsg = "I/O error({0}): {1}: file({2})".format(ioe.errno, ioe.strerror, ioe.filename)
        print emsg
    except:
        emsg = "Failed to serialize json object:{0}".format(sys.exc_info()[0])
        print emsg
    finally:
        if(f):
            f.close()

def _deserialize_jsonobject(infile):
    f = None
    try:
        f = file(infile,'r+');
        s = json.load(f)
        return s
    except IOError as ioe:
        emsg = "I/O error({0}): {1}: file({2})".format(ioe.errno, ioe.strerror, ioe.filename)
        print emsg
    except:
        emsg = "Failed to deserialize json object:{0}".format(sys.exc_info()[0])
        print emsg
    finally:
        if(f):
            f.close()
            
def _deserialize_jsonobject_fromstring(invalue):
    try:
        s = json.loads(invalue)
        return s
    except Exception as e:
        message = "Failed to generate build info property file!\n" + e.message
        print message
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
        iBN1 = int(packageinfo1["buildNumber"])
        iBN2 = int(packageinfo2["buildNumber"])
        if(iBN1 > iBN2):
            result = 1
        elif(iBN1 < iBN2):
            result = -1
        else:
            result = 0
            
    return result
        
def _gen_new_packageinfo(pre_released_packageinfo, pre_build_packageinfo, current_buildprops):
    def _str_component(component):
        component_s = "%s_%s_%s_%s_%s_%s_%s" % (component["name"],
                                                component["storage"]["groupId"],
                                                component["storage"]["artifactId"],
                                                component["storage"]["packaging"],
                                                component["storage"]["version"],
                                                component["storage"]["classifier"],
                                                component["packageLayout"])
        return component_s

    def _is_equal(component1, component2):
        result = False
        component1_s = _str_component(component1)
        component2_s = _str_component(component2)
        result = (component1_s == component2_s)

        return result

    def _get_new_reposinfo(repo):
        # One git repository can generate one or more components, here we assume that once there is a change in
        # the git repository, all the components will be generated a new version (current build version), so we should
        # update all the components' version if the repository need to build (changes happened since last successful build).
        # However, there is one situation that a git repository can be used to generate different components that have different
        # version mechanism, for this kind of situation, usually different components are different software products.
        #
        propname_prefix = _dash_to_underscore(repo["repoName"])
        if(current_buildprops["%s_build_needed" % propname_prefix] == "True"):
            repo["commit"] = current_buildprops["%s_build_commit" % propname_prefix]
            repo["author"] = current_buildprops["%s_build_commit_author" % propname_prefix]
            repo["version"] = current_buildprops["%s_build_version" % propname_prefix]
            for component in repo["components"]:
                component["storage"]["version"] = current_buildprops["%s_build_version" % propname_prefix]

        return repo
    
    def _filter_incremental_repo(repo):
        result = False
        propname_prefix = _dash_to_underscore(repo["repoName"])
        if(current_buildprops["%s_build_needed" % propname_prefix] == "True"):
            result = True
        return result
    
    def _get_patch_repos(full_build_packageinfo_repos):
        patch_repos = []
        pre_released_packageinfo_len = len(pre_released_packageinfo["repos"])
        pre_released_packageinfo_index = 0
        for repo in full_build_packageinfo_repos:
            while(pre_released_packageinfo_index < pre_released_packageinfo_len):
                # This git repo exists in both this version and previous version of software, so we check the components.
                #
                if(repo["repoName"] == pre_released_packageinfo["repos"][pre_released_packageinfo_index]["repoName"]):
                    patch_components = []
                    pre_released_components_len = len(pre_released_packageinfo["repos"][pre_released_packageinfo_index]["components"])
                    pre_com_index = 0
                    for com in repo["components"]:
                        while (pre_com_index < pre_released_components_len):
                            # If the component was the same, it shouldn't be included in the patch package info.
                            #
                            if(_is_equal(com, pre_released_packageinfo["repos"][pre_released_packageinfo_index]["components"][pre_com_index])):
                                break
                            pre_com_index += 1

                        # If the component is different from previous components, it should be included included in the patch package info.
                        #
                        if(pre_com_index > pre_released_components_len - 1):
                            patch_components.append(com)

                        pre_com_index = 0
                    if(len(patch_components) > 0):
                        patch_repos.append({"repoName":repo["repoName"], "components":patch_components})

                    break

                pre_released_packageinfo_index += 1

            # A new git repo has been added in this version of software, so all the components should be included in current patch package info.
            #
            if(pre_released_packageinfo_index > pre_released_packageinfo_len -1):
                patch_repos.append(repo)

            pre_released_packageinfo_index = 0

        return patch_repos

    def _gen_filter_patch_repo(pre_released_repoinfo):
        def _filter_patch_repo(repo):
            result = False
            repoName = repo["repoName"]
            if(repoName not in pre_released_repoinfo.keys()):
                result = True
            else:
                for c in repo["components"]:
                    cname = c["name"]
                    if(cname not in pre_released_repoinfo[repoName].keys()):
                        result = True
                        break
                    else:
                        if(c["storage"]["version"] != pre_released_repoinfo[repoName][cname]["storage"]["version"]):
                            result = True
                            break
            return result
        return _filter_patch_repo

    # return (full package info, patch package info, incremental package info)
    full_build_packageinfo = copy.deepcopy(pre_build_packageinfo)
    full_build_packageinfo["version"] = current_buildprops["product_version"]
    full_build_packageinfo["buildNumber"] = current_buildprops["product_build_number"]
    full_build_packageinfo["storage"]["version"] = current_buildprops["product_build_version"]
    full_build_packageinfo["storage"]["classifier"] = "full"
    full_build_packageinfo["repos"] = map(_get_new_reposinfo, full_build_packageinfo["repos"])
    
    incremental_packageinfo = {}
    incremental_packageinfo["product"] = full_build_packageinfo["product"]
    incremental_packageinfo["version"] = full_build_packageinfo["version"]
    incremental_packageinfo["buildNumber"] = full_build_packageinfo["buildNumber"]
    incremental_packageinfo["storage"] = copy.deepcopy(full_build_packageinfo["storage"])
    incremental_packageinfo["storage"]["classifier"] = "increment"
    incremental_packageinfo["repos"] = filter(_filter_incremental_repo, full_build_packageinfo["repos"])
    
    patch_packageinfo = copy.deepcopy(full_build_packageinfo)
    patch_packageinfo["storage"]["classifier"] = "patch"
    if(pre_released_packageinfo):
        patch_packageinfo = {}
        patch_packageinfo["product"] = full_build_packageinfo["product"]
        patch_packageinfo["version"] = full_build_packageinfo["version"]
        patch_packageinfo["buildNumber"] = full_build_packageinfo["buildNumber"]
        patch_packageinfo["storage"] = copy.deepcopy(full_build_packageinfo["storage"])
        patch_packageinfo["storage"]["classifier"] = "patch"
        patch_packageinfo["repos"] = _get_patch_repos(full_build_packageinfo["repos"])
    
    return (full_build_packageinfo, incremental_packageinfo, patch_packageinfo)

def upload_artifact_byspec(builddir, art_server_id, art_upload_spec_file):
    ps = PathStackMgr()
    try:
        ps.pushd(builddir)
        cmd = "jfrog rt upload --flat=true --server-id=%s --spec=%s" % (art_server_id, art_upload_spec_file)
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
        ps.popd()
    except Exception as err:
        print err
    finally:
        ps.popd()
        
def upload_artifact_byfile(builddir, art_server_id, local_source_file, art_target_file):
    ps = PathStackMgr()
    try:
        ps.pushd(builddir)
        cmd = "jfrog rt upload --flat=true --server-id=%s %s %s" % (art_server_id, local_source_file, art_target_file)
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
        ps.popd()
    except Exception as err:
        print err
    finally:
        ps.popd()
        
def download_artifact_byspec(builddir, art_server_id, art_download_spec_file):
    ps = PathStackMgr()
    try:
        ps.pushd(builddir)
        cmd = "jfrog rt download --flat=false --server-id=%s --spec=%s" % (art_server_id, art_download_spec_file)
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
        pattern = "^.+?\/(.+)$"
        dobject = _deserialize_jsonobject(art_download_spec_file)
        for file in dobject["files"]:
            m = re.search(pattern, file["pattern"])
            partial_target_fp = ""
            if(m):
                partial_target_fp = m.group(1)
            else:
                raise Exception("Can't find art source file!")

            target_fp = file["target"] + partial_target_fp
            FileManager.gen_file_md5sum(target_fp)
        ps.popd()
    except Exception as err:
        print err
    finally:
        ps.popd()
        
def download_artifact_byfile(builddir, art_server_id, art_source_file, local_target_dir):
    ps = PathStackMgr()
    try:
        if(not os.path.isdir(local_target_dir)):
            raise Exception("%s is not a directory" % local_target_dir)

        if(local_target_dir.rfind("/") != len(local_target_dir)-1 and local_target_dir.rfind("\\") != len(local_target_dir)-1):
            local_target_dir = local_target_dir + os.path.sep

        ps.pushd(builddir)
        cmd = "jfrog rt download --flat=false --server-id=%s %s %s" % (art_server_id, art_source_file, local_target_dir)
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
        ps.popd()
        pattern = "^.+?\/(.+)$"
        m = re.search(pattern, art_source_file)
        partial_target_fp = ""
        if(m):
            partial_target_fp = m.group(1)
        else:
            raise Exception("Can't find art source file!")

        target_fp = local_target_dir + os.sep + partial_target_fp
        FileManager.gen_file_md5sum(target_fp)
    except Exception as err:
        print err
    finally:
        ps.popd()

def pack_composite_product(builddir, base_prodtag):
    ps = PathStackMgr()
    try:
        current_buildprops = _load_buildproperties(builddir + os.sep + "build-info.properties")
        ps.pushd(builddir + os.sep + ".repo" + os.sep + "manifests")
        cmd = "git --no-pager show %s:%s" % (current_buildprops["product_manifest_branch"], "package.json")
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
        pre_packageinfo_s = _deserialize_jsonobject_fromstring(output)
        
        base_packageinfo_s = None
        if(base_prodtag):
            cmd = "git --no-pager show %s:%s" % (base_prodtag, "package.json")
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
            base_packageinfo_s = _deserialize_jsonobject_fromstring(output)
        
        ps.popd()

        (full_packageinfo, increment_packageinfo, patch_packageinfo) = _gen_new_packageinfo(base_packageinfo_s, pre_packageinfo_s, current_buildprops)

        full_packageinfo_fn = "%s-%s-%s.%s" % (full_packageinfo["storage"]["artifactId"],
                                               full_packageinfo["storage"]["version"],
                                               full_packageinfo["storage"]["classifier"],
                                               full_packageinfo["storage"]["packaging"])


        increment_packageinfo_fn = "%s-%s-%s.%s" % (increment_packageinfo["storage"]["artifactId"],
                                                    increment_packageinfo["storage"]["version"],
                                                    increment_packageinfo["storage"]["classifier"],
                                                    increment_packageinfo["storage"]["packaging"])


        patch_packageinfo_fn = "%s-%s-%s.%s" % (patch_packageinfo["storage"]["artifactId"],
                                               patch_packageinfo["storage"]["version"],
                                               patch_packageinfo["storage"]["classifier"],
                                               patch_packageinfo["storage"]["packaging"])

        ps.pushd(builddir)
        _serialize_jsonobject(full_packageinfo, full_packageinfo_fn)
        _serialize_jsonobject(increment_packageinfo, increment_packageinfo_fn)
        _serialize_jsonobject(patch_packageinfo, patch_packageinfo_fn)
        ps.popd()
        return (full_packageinfo_fn, increment_packageinfo_fn, patch_packageinfo_fn)
    except Exception as err:
        print err
    finally:
        ps.popd()
        
def upload_composite_product(builddir, full_packageinfo_fn, increment_packageinfo_fn, patch_packageinfo_fn):
    ps = PathStackMgr()
    try:
        ps.pushd(builddir)

        (repourl, art_server_id, art_download_repo, art_upload_repo) = ButlerConfig.default_artifactory()
        full_packageinfo = _deserialize_jsonobject(full_packageinfo_fn)
        increment_packageinfo = _deserialize_jsonobject(increment_packageinfo_fn)
        patch_packageinfo = _deserialize_jsonobject(patch_packageinfo_fn)

        full_packageinfo_grouppath = full_packageinfo["storage"]["groupId"].replace(".", "/")
        full_packageinfo_artpath = "%s/%s/%s/%s/%s" % (art_upload_repo, 
                                                       full_packageinfo_grouppath, 
                                                       full_packageinfo["storage"]["artifactId"],
                                                       full_packageinfo["storage"]["version"],
                                                       full_packageinfo_fn)
        spec_f1 = {"pattern":full_packageinfo_fn, "target":full_packageinfo_artpath}
        
        increment_packageinfo_grouppath = increment_packageinfo["storage"]["groupId"].replace(".", "/")
        increment_packageinfo_artpath = "%s/%s/%s/%s/%s" % (art_upload_repo, 
                                                       increment_packageinfo_grouppath, 
                                                       increment_packageinfo["storage"]["artifactId"],
                                                       increment_packageinfo["storage"]["version"],
                                                       increment_packageinfo_fn)
        spec_f2 = {"pattern":increment_packageinfo_fn, "target":increment_packageinfo_artpath}
        
        patch_packageinfo_grouppath = increment_packageinfo["storage"]["groupId"].replace(".", "/")
        patch_packageinfo_artpath = "%s/%s/%s/%s/%s" % (art_upload_repo, 
                                                       patch_packageinfo_grouppath, 
                                                       patch_packageinfo["storage"]["artifactId"],
                                                       patch_packageinfo["storage"]["version"],
                                                       patch_packageinfo_fn)
        spec_f3 = {"pattern":patch_packageinfo_fn, "target":patch_packageinfo_artpath}
        art_upload_filespec = {"files":[spec_f1, spec_f2, spec_f3]}
        _serialize_jsonobject(art_upload_filespec, "art_upload.spec")
        upload_artifact_byspec(builddir, art_server_id, "art_upload.spec")

        ps.popd()
    except Exception as err:
        raise
    finally:
        ps.popd()

def pre_build_multi_repo(args):
    lforcebuilds = None
    if(args["forcebuilds"] and args["forcebuilds"] != "none"):
        if(args["forcebuilds"] == "all"):
            lforcebuilds = "all"
        else:
            lforcebuilds = args["forcebuilds"].split(',')
            
    prodname = args["prodname"]
    prodversion = args["prodversion"]
    builddir = args["builddir"]
    buildurl = args["buildurl"]
    
    #
    # Need to be process safe.
    #
    props = get_buildinfo(prodname, prodversion, builddir, buildurl, lforcebuilds)
    create_pre_build_tag(builddir, props)
    #
    # 

def post_build_composite_product(args):
    builddir = args["builddir"]
    base_prodtag = args["prereleasedtag"]
    (full_packageinfo_fn, increment_packageinfo_fn, patch_packageinfo_fn) = pack_composite_product(builddir, base_prodtag)
    upload_composite_product(builddir, full_packageinfo_fn, increment_packageinfo_fn, patch_packageinfo_fn)
    #
    # Need to be process safe.
    #
    create_post_build_tag(builddir, full_packageinfo_fn)
    #
    #
    
def download_composite_product(args):
    """
    :param builddir: string, build directory
    :param art_source_file: string, ${groupId}/${artifactId}/${version}/${artifactId}-${version}-${classifier}.${packaging}
    :param local_target_dir: string, the directory path should have "/" at end.
    """
    builddir = args["workdir"] if args["workdir"] else  ButlerConfig.datadir()
    art_source_file = args["rpath"]
    local_target_dir = args["tdir"] if args["tdir"] else  ButlerConfig.datadir()

    if(not os.path.isdir(local_target_dir)):
        raise Exception("%s is not a directory" % local_target_dir)

    if(local_target_dir.rfind("/") != len(local_target_dir)-1 and local_target_dir.rfind("\\") != len(local_target_dir)-1):
        local_target_dir = local_target_dir + os.path.sep

    ps = PathStackMgr()
    try:
        (repourl, art_server_id, art_download_repo, art_upload_repo) = ButlerConfig.default_artifactory()

        ps.pushd(builddir)
        # No matter it is single or composite product, we need to download it firstly!
        # The source file path of product artifact or the in artifactory started from artifactory download
        # repo which we think it as the full path, because jfrog cli treat it like this way.
        #
        art_full_source_file = art_download_repo + "/" + art_source_file

        # Download the product's artifact from artifactory
        #
        download_artifact_byfile(builddir, art_server_id, art_full_source_file, local_target_dir)
        
        # Well it is a composite product, the downloaded artifact above is just the product's package info file(json)
        #
        # After downloaded the product's package info file (json) from artifactory, local_full_target_file was calculated
        # to be its local full path on current runninng operation system which we need to convert the path's seperation.
        #
        local_full_target_file = local_target_dir + art_source_file.replace("/", os.path.sep)

        # Load the product's pacakge info file(json) to generate artifactory download spec file to download real components
        # included in this package info file.
        #
        art_product_jobject = _deserialize_jsonobject(local_full_target_file)
        # This dictionary will store the real download spec info
        #
        art_download_spec = {}
        art_download_spec["files"] = []
        # An extended one of the download spec file to record more info in order to create symbolic link of the real
        # component file from product folder
        #
        art_download_spec_ext = {}
        art_download_spec_ext["files"] = []
        # Go through the product package info(json) to fill the download spec objects
        #
        for repo in art_product_jobject["repos"]:
            for component in repo["components"]:
                # N/A means this option doesn't exist. If there was no package layout, that means this component
                # of this product will be not included in the final product package. This component maybe a component
                # that will be packaged in other components.
                #
                if(component["packageLayout"] == "N/A"):
                    continue

                component_file_name = "{artifactId}-{version}{classifier}.{packaging}".format(artifactId = component["storage"]["artifactId"],
                                                                                              version = component["storage"]["version"],
                                                                                              classifier = "" if(component["storage"]["classifier"] == "N/A") else "-" + component["classifier"],
                                                                                              packaging = component["storage"]["packaging"])
                art_component_file = component["storage"]["groupId"].replace(".", "/") + "/" \
                                    + component["storage"]["artifactId"] + "/" \
                                    + component["storage"]["version"] + "/" \
                                    + component_file_name

                art_full_component_file =  art_download_repo + "/" + art_component_file
                local_component_file = art_component_file.replace("/", os.path.sep)
                local_full_component_file = local_target_dir + local_component_file
                art_download_spec["files"].append({"pattern":art_full_component_file, "target":local_target_dir})
                art_download_spec_ext["files"].append({"pattern":art_full_component_file, 
                                                       "target":local_target_dir, 
                                                       "target_full_component_file":local_full_component_file, 
                                                       "target_component_file":local_component_file, 
                                                       "product_component_layout":component["packageLayout"]})
        
        # Now let's create the product folder in which we will create all the package layouts and make symbolic links
        # to each real components, so that we won't keep double component artifacts in local cached folder unless we
        # call another commands to make the real product package.
        
        # If the product folder doens't exist, create it!
        #        
        _serialize_jsonobject(art_download_spec, "product_download.spec")
        download_artifact_byspec(builddir, art_server_id, "product_download.spec")
        local_full_product_dir = local_target_dir \
                                + art_product_jobject["storage"]["groupId"].replace(".", os.path.sep) \
                                + os.path.sep \
                                + art_product_jobject["storage"]["artifactId"] + os.path.sep + art_product_jobject["storage"]["version"] + os.path.sep \
                                + "{artifactId}-{version}{classifier}.dir".format(artifactId = art_product_jobject["storage"]["artifactId"],
                                                                                                version = art_product_jobject["storage"]["version"],
                                                                                                classifier = "" if(art_product_jobject["storage"]["classifier"] == "N/A") else "-" + art_product_jobject["storage"]["classifier"])
        if(not os.path.exists(local_full_product_dir)):
            os.mkdir(local_full_product_dir)
            for f in art_download_spec_ext["files"]:
                # The component is at root path under product folder
                #
                if(f["product_component_layout"] == "None"):
                    local_full_product_component_file = local_full_product_dir + os.path.sep \
                                                        + os.path.basename(f["target_component_file"])
                else:
                    local_full_product_component_file = local_full_product_dir + os.path.sep \
                                                        + f["product_component_layout"].replace(",", os.path.sep) + os.path.sep \
                                                        + os.path.basename(f["target_component_file"])

                if(not os.path.exists(os.path.dirname(local_full_product_component_file))):
                    os.mkdir(os.path.dirname(local_full_product_component_file))
                    
                FileManager.create_hard_link(f["target_full_component_file"], local_full_product_component_file)

        ps.popd()
    except Exception as err:
        print err
    finally:
        ps.popd()

def download_single_product(args):
    """
    :param builddir: string, build directory
    :param art_source_file: string, ${groupId}/${artifactId}/${version}/${artifactId}-${version}-${classifier}.${packaging}
    :param local_target_dir: string, the directory path should have "/" at end.
    """
    builddir = args["workdir"] if args["workdir"] else  ButlerConfig.datadir()
    art_source_file = args["rpath"]
    local_target_dir = args["tdir"] if args["tdir"] else  ButlerConfig.datadir()

    if(not os.path.isdir(local_target_dir)):
        raise Exception("%s is not a directory" % local_target_dir)

    if(local_target_dir.rfind("/") != len(local_target_dir)-1 and local_target_dir.rfind("\\") != len(local_target_dir)-1):
        local_target_dir = local_target_dir + os.path.sep

    ps = PathStackMgr()
    try:
        (repourl, art_server_id, art_download_repo, art_upload_repo) = ButlerConfig.default_artifactory()

        ps.pushd(builddir)
        # No matter it is single or composite product, we need to download it firstly!
        # The source file path of product artifact or the in artifactory started from artifactory download
        # repo which we think it as the full path, because jfrog cli treat it like this way.
        #
        art_full_source_file = art_download_repo + "/" + art_source_file

        # Download the product's artifact from artifactory
        #
        download_artifact_byfile(builddir, art_server_id, art_full_source_file, local_target_dir)

        ps.popd()
    except Exception as err:
        print err
    finally:
        ps.popd()

def main(argv):
    # python butler.py
    #
    ButlerConfig.load()
    parser = argparse.ArgumentParser(prog='butler', 
                                     description="butler to assist CI/CD construction")
    subparsers = parser.add_subparsers(dest = 'command')
    # Add sub-commands: ci|cd
    #
    parsers_ci = subparsers.add_parser('ci', help='commands to support ci setup')
    parsers_cd = subparsers.add_parser('cd', help='commands to support cd setup')
    
    parent_parser_ci = argparse.ArgumentParser(add_help=False)
    parent_parser_ci.add_argument('--prodname', action='store', 
                                    dest='prodname',
                                    required=True, 
                                    help='Store the product')

    parent_parser_ci.add_argument('--prodversion', action='store', 
                                    dest='prodversion',
                                    required=True,
                                    help='Store the version of current building product or component')

    parent_parser_ci.add_argument('--builddir', action='store',
                                    dest='builddir',
                                    required=True, 
                                    help='Store the local work directory of current build')
    
    parent_parser_ci.add_argument('--buildurl', action='store', 
                                    dest='buildurl',
                                    required=True,
                                    help='Store current jenkins build url')

    parent_parser_ci.add_argument('--forcebuilds', action='store', 
                                    dest='forcebuilds',
                                    help='Store the manually kicked off builds')

    # Add sub-commands: pre_build_multi_repo|post_build_composite_product
    #
    subparsers_ci = parsers_ci.add_subparsers(dest = 'sub_command')
    parser_prebuild_multi_repo = subparsers_ci.add_parser('pre_build_multi_repo', 
                                                        help='Support multiple repositories at pre-build stage', 
                                                        parents=[parent_parser_ci])
    parser_prebuild_multi_repo.set_defaults(func=pre_build_multi_repo)

    parser_postbuild_composite_product = subparsers_ci.add_parser('post_build_composite_product',
                                                                help='Support composite product at post-build stage')
    parser_postbuild_composite_product.add_argument('--builddir',
                                                    action='store',
                                                    dest='builddir',
                                                    required=True, 
                                                    help='Store the local work directory of current build')
    parser_postbuild_composite_product.add_argument('--prereleasedtag', action='store', 
                                                    dest='prereleasedtag',
                                                    default=None,
                                                    help='Store pre released version')
    parser_postbuild_composite_product.set_defaults(func=post_build_composite_product)
    
    # Add sub-commands: download_composite_product|download_single_product|post_build_composite_product
    #
    subparsers_cd = parsers_cd.add_subparsers(dest = 'sub_command')
    parser_download_composite_product = subparsers_cd.add_parser('download_composite_product',
                                            help='Download composite products')
    parser_download_composite_product.add_argument('--workdir', action='store',
                                                   dest='workdir',
                                                   default=None,
                                                   help='Store the command running directory')
    parser_download_composite_product.add_argument('--rpath', action='store',
                                                   dest='rpath',
                                                   required=True,
                                                   help='Store the remote source file in artifactory')
    parser_download_composite_product.add_argument('--tdir', action='store',
                                                   dest='tdir',
                                                   default=None,
                                                   help='Store the product download directory')
    parser_download_composite_product.set_defaults(func=download_composite_product)
    
    parser_download_single_product = subparsers_cd.add_parser('download_single_product',
                                            help='Download single products')
    parser_download_single_product.add_argument('--workdir', action='store',
                                                   dest='workdir',
                                                   default=None,
                                                   help='Store the command running directory')
    parser_download_single_product.add_argument('--rpath', action='store',
                                                   dest='rpath',
                                                   required=True,
                                                   help='Store the remote source file in artifactory')
    parser_download_single_product.add_argument('--tdir', action='store',
                                                   dest='tdir',
                                                   default=None,
                                                   help='Store the product download directory')
    parser_download_single_product.set_defaults(func=download_single_product)

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
    #print _calculate_repos_buildneeded("/Users/mike/Documents/MikeWorkspace/Philips/workspace/test", 'all')
    #print _get_manifest_info("/Users/mike/Documents/MikeWorkspace/Philips/workspace/test")
    #_test_package("mikepro-artifactory", "tfstest-dev-local")
    #postbuild(None)
    #download_artifact_byfile("/Users/mike/Documents/MikeWorkspace/cikit/test", "mikepro-artifactory", "tfstest-group/com/free/freedivision/test/test/1.0.0_b14/test-1.0.0_b14-full.json", "/Users/mike/.butler/data/")
    #upload_artifact_byfile("/Users/mike/Documents/MikeWorkspace/cikit/test", "mikepro-artifactory", "build-info.properties", "tfstest-group/com/free/freedivision/test/test/1.0.0_b14/build-info.properties")
    #download_artifact_byfile("/Users/mike/Documents/MikeWorkspace/cikit/test", "mikepro-artifactory", "tfstest-group/com/freessure/coffee/mikeapp1/service/1.0_b41/service-1.0_b41.jar", "/Users/mike/.butler/data/")
    #download_artifact_byfile("/Users/mike/Documents/MikeWorkspace/cikit/test", "mikepro-artifactory", "tfstest-group/com/freessure/coffee/mikeapp1/service/1.0_b37/service-1.0_b37.jar", "/Users/mike/.butler/data/")
    #download_artifact_byfile("/Users/mike/Documents/MikeWorkspace/cikit/test", "mikepro-artifactory", "tfstest-group/com/freessure/coffee/mikeapp1/service/1.0_b36/service-1.0_b36.jar", "/Users/mike/.butler/data/")
    #upload_artifact_byfile("/Users/mike/Documents/MikeWorkspace/cikit/test", "mikepro-artifactory", "test-repo1-1.0.0_b14.jar", "tfstest-group/com/free/freedivision/test/test-repo1/1.0.0_b14/test-repo1-1.0.0_b14.jar")
    #upload_artifact_byfile("/Users/mike/Documents/MikeWorkspace/cikit/test", "mikepro-artifactory", "test-repo2-1.0.0_b14.jar", "tfstest-group/com/free/freedivision/test/test-repo2/1.0.0_b14/test-repo2-1.0.0_b14.jar")
    #upload_artifact_byfile("/Users/mike/Documents/MikeWorkspace/cikit/test", "mikepro-artifactory", "test-repo3-0.0.1_b66.jar", "tfstest-group/com/free/freedivision/test/test-repo3/0.0.1_b66/test-repo3-0.0.1_b66.jar")
    #download_artifact_byspec("/Users/mike/Documents/MikeWorkspace/cikit/test", "mikepro-artifactory", "art_download.json")
    #download_product("/Users/mike/Documents/MikeWorkspace/cikit/test", "mikepro-artifactory", "tfstest-group", "com/free/freedivision/test/test/1.0.0_b14/test-1.0.0_b14-full.json", product_type="composite", local_target_dir=None)
    #ButlerConfig.load()
    #print ButlerConfig.home()
    #print ButlerConfig.datadir()
    #print ButlerConfig.default_jenkins()
    #pass
    #FileManager.create_symbolic_link(r"C:\Users\310276411\MyWork\CITest\copd-repo1\readme.txt", r"C:\Users\310276411\MyWork\CITest\copd-repo1\readme.txt.1")
    #args = {}
    #args["prodname"] = "test"
    #args["prodversion"] = "1.0.0"
    #args["builddir"] = "/Users/mike/Documents/MikeWorkspace/cikit/test"
    #args["buildurl"] = "http://mikepro.local:8080/jenkins/job/test-muti-cibuild/88/"
    #args["forcebuilds"] = "all"
    
    #pre_build_multi_repo(args)
    #ButlerConfig.load()
    #args = {}
    #args["builddir"] = "/Users/mike/Documents/MikeWorkspace/cikit/test"
    #args["prereleasedtag"] = "test_0.0.1_b66"
    #post_build_composite_product(args)