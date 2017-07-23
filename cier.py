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
from requests.auth import HTTPBasicAuth
from properties.p import Property
import platform
from _threading_local import local

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

class FileManager(object):
    @staticmethod
    def _create_link(src, dest, type):
        if(platform.system() == "windows"):
            import ctypes
            flags = 1 if src is not None and os.path.isdir(src) else 0
            if(type == "link"):
                if not ctypes.windll.kernel32.CreateHardLinkA(dest, src, flags):
                    raise OSError
            elif(type == "symlink"):
                if not ctypes.windll.kernel32.CreateSymbolicLinkA(dest, src, flogs):
                    raise OSError
        else:
            if(type == "link"):
                os.link(src, dest)
            elif(type == "symlink"):
                os.symlink(src, dest)

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
        _create_link(src, dest, "link")
    
    @staticmethod
    def create_hard_link(src, dest):
        _create_link(src, dest, "symlink")

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
        if(packageinfo1["buildNumber"] > packageinfo2["buildNumber"]):
            result = 1
        elif(packageinfo1["buildNumber"] < packageinfo2["buildNumber"]):
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
    full_build_packageinfo["repos"] = map(_get_new_reposinfo, full_build_packageinfo["repos"])
    
    incremental_packageinfo = {}
    incremental_packageinfo["product"] = full_build_packageinfo["product"]
    incremental_packageinfo["version"] = full_build_packageinfo["version"]
    incremental_packageinfo["buildNumber"] = full_build_packageinfo["buildNumber"]
    incremental_packageinfo["storage"] = copy.deepcopy(full_build_packageinfo["storage"])
    incremental_packageinfo["storage"]["classifier"] = "increment"
    incremental_packageinfo["repos"] = filter(_filter_incremental_repo, full_build_packageinfo["repos"])
    
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

            target_fp = file["target"] + os.sep + partial_target_fp
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

def pack_product(builddir, base_prodtag, art_repo):
    ps = PathStackMgr()
    try:
        current_buildprops = _load_buildproperties(builddir + os.sep + "build-info.properties")
        ps.pushd(builddir + os.sep + ".repo" + os.sep + "manifests")
        cmd = "git --no-pager show %s:%s" % (current_buildprops["product_manifest_branch"], "package.json")
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
        pre_packageinfo_s = _deserialize_jsonobject_fromstring(output)
        
        cmd = "git --no-pager show %s:%s" % (base_prodtag, "package.json")
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
        base_packageinfo_s = _deserialize_jsonobject_fromstring(output)
        ps.popd()

        (full_packageinfo, increment_packageinfo, patch_packageinfo) = _gen_new_packageinfo(base_packageinfo_s, pre_packageinfo_s, current_buildprops)

        full_packageinfo_fn = "%s-%s-%s.%s" % (full_packageinfo["storage"]["artifactId"],
                                               full_packageinfo["storage"]["version"],
                                               full_packageinfo["storage"]["classifier"],
                                               full_packageinfo["storage"]["packaging"])
        full_packageinfo_grouppath = full_packageinfo["storage"]["groupId"].replace(".", "/")
        full_packageinfo_artpath = "%s/%s/%s/%s/%s" % (art_repo, 
                                                       full_packageinfo_grouppath, 
                                                       full_packageinfo["storage"]["artifactId"],
                                                       full_packageinfo["storage"]["version"],
                                                       full_packageinfo_fn)
        spec_f1 = {"pattern":full_packageinfo_fn, "target":full_packageinfo_artpath}

        increment_packageinfo_fn = "%s-%s-%s.%s" % (increment_packageinfo["storage"]["artifactId"],
                                                    increment_packageinfo["storage"]["version"],
                                                    increment_packageinfo["storage"]["classifier"],
                                                    increment_packageinfo["storage"]["packaging"])
        increment_packageinfo_grouppath = increment_packageinfo["storage"]["groupId"].replace(".", "/")
        increment_packageinfo_artpath = "%s/%s/%s/%s/%s" % (art_repo, 
                                                       increment_packageinfo_grouppath, 
                                                       increment_packageinfo["storage"]["artifactId"],
                                                       increment_packageinfo["storage"]["version"],
                                                       increment_packageinfo_fn)
        spec_f2 = {"pattern":increment_packageinfo_fn, "target":increment_packageinfo_artpath}

        patch_packageinfo_fn = "%s-%s-%s.%s" % (patch_packageinfo["storage"]["artifactId"],
                                               patch_packageinfo["storage"]["version"],
                                               patch_packageinfo["storage"]["classifier"],
                                               patch_packageinfo["storage"]["packaging"])
        patch_packageinfo_grouppath = increment_packageinfo["storage"]["groupId"].replace(".", "/")
        patch_packageinfo_artpath = "%s/%s/%s/%s/%s" % (art_repo, 
                                                       patch_packageinfo_grouppath, 
                                                       patch_packageinfo["storage"]["artifactId"],
                                                       patch_packageinfo["storage"]["version"],
                                                       patch_packageinfo_fn)
        spec_f3 = {"pattern":patch_packageinfo_fn, "target":patch_packageinfo_artpath}
        
        art_upload_filespec = {"files":[spec_f1, spec_f2, spec_f3]}

        ps.pushd(builddir)
        _serialize_jsonobject(full_packageinfo, full_packageinfo_fn)
        _serialize_jsonobject(increment_packageinfo, increment_packageinfo_fn)
        _serialize_jsonobject(patch_packageinfo, patch_packageinfo_fn)
        _serialize_jsonobject(art_upload_filespec, "art_upload.spec")
        ps.popd()
    except Exception as err:
        print err
    finally:
        ps.popd()

def prebuild(args):
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
    
    props = get_buildinfo(prodname, prodversion, builddir, buildurl, lforcebuilds)
    tag_current_build(buildurl, props)

def postbuild(args):
    builddir = "/Users/mike/Documents/MikeWorkspace/cikit/test"
    base_prodtag = "product_test_0.0.1_b66"
    art_server_id = "mikepro-artifactory"
    art_repo = "tfstest-group"
    pack_product(builddir, base_prodtag, art_repo)
    upload_artifact_byspec(builddir, art_server_id, "art_upload.spec")
    
def download_product(builddir, art_server_id, art_download_repo, art_source_file, product_type="composite", local_target_dir=None):
    """
    :param art_server_id: string, in ~/.jfrog/jfrog-cli.conf, mikepro-artifactory
    :param art_download_repo: string, tfstest-group
    :param art_source_file: string, ${groupId}/${artifactId}/${version}/${artifactId}-${version}-${classifier}.${packaging}
    :param product_type: string, composite|single
    """
    assert product_type in ["single", "composite"], "product_type supports 'single' and 'composite' now"
    ps = PathStackMgr()
    try:
        if(not local_target_dir):
            local_target_dir = "/Users/mike/.butler/data/"
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
        if(product_type == "composite"):
            # After downloaded the product's package info file (json) from artifactory, local_full_target_file was calculated
            # to be its local full path on current runninng operation system which we need to convert the path's seperation.
            #
            local_full_target_file = local_target_dir + os.path.sep + art_source_file.replace("/", os.path.sep)

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
                    component_file_name = "{artifactId}-{version}{classifier}.{packaging}".format(artifactId = component["artifactId"],
                                                                                                  version = component["version"],
                                                                                                  classifier = "" if(component["classifier"] == "N/A") else "-" + component["classifier"],
                                                                                                  packaging = component["packaging"])
                    art_component_file = component["groupId"].replace(".", "/") + "/" + component_file_name
                    art_full_component_file =  art_download_repo + "/" + art_component_file
                    local_component_file = art_component_file.replace("/", os.path.sep)
                    local_full_component_file = local_target_dir + os.sep + local_component_file
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
            _deserialize_jsonobject("product_download.spec")
            download_artifact_byspec(builddir, art_server_id, "product_download.spec")
            local_full_product_dir = local_target_dir + os.path.sep \
                                    + art_product_jobject["storage"]["groupId"].replace(".", os.path.sep) \
                                    + os.path.sep \
                                    + art_product_jobject["storage"]["artifactId"] + os.path.sep + art_product_jobject["storage"]["version"] + os.path.sep \
                                    + "{artifactId}-{version}{classifier}.dir".format(artifactId = art_product_jobject["storage"]["artifactId"],
                                                                                                    version = art_product_jobject["storage"]["version"],
                                                                                                    classifier = "" if(art_product_jobject["storage"]["classifier"] == "N/A") else "-" + art_product_jobject["storage"]["classifier"])
            if(not os.path.exists(local_full_product_dir)):
                os.mkdir(local_full_product_dir)
                for f in art_download_spec_ext["files"]:
                    if(f["product_component_layout"] == "None"):
                        local_full_product_component_file = local_full_product_dir + os.path.sep \
                                                            + os.path.basename(f["target_component_file"])
                    else:
                        local_full_product_component_file = local_full_product_dir + os.path.sep \
                                                            + f["product_component_layout"].replace(",", os.path.sep) + os.path.sep \
                                                            + os.path.basename(f["target_component_file"])
    
                    if(not os.path.exists(os.path.dirname(local_full_product_component_file))):
                        os.mkdir(os.path.dirname(local_full_product_component_file))
                        
                    FileManager.create_symbolic_link(f["target_full_component_file"], local_full_product_component_file)
                
        ps.popd()
    except Exception as err:
        print err
    finally:
        ps.popd()

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
    
    
def _test_package(art_server_id, art_upload_repo):
    ps = PathStackMgr()
    try:
        cmd = "git --no-pager show %s:%s" % ("master", "sample/package.json")
        ps.pushd(r"/Users/mike/Documents/MikeWorkspace/cikit")
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
        s = _deserialize_jsonobject_fromstring(output)
        cmd = "git --no-pager show %s:%s" % ("master", "sample/basepackage.json")
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
        bases = _deserialize_jsonobject_fromstring(output)
        current_buildprops = _load_buildproperties(r"sample/build-info.properties")
        (full_packageinfo, increment_packageinfo, patch_packageinfo) = _gen_new_packageinfo(bases, s, current_buildprops)
        #print full_packageinfo
        #print increment_packageinfo
        #print patch_packageinfo
        full_packageinfo_fn = "%s-%s-%s.%s" % (full_packageinfo["storage"]["artifactId"],
                                               full_packageinfo["storage"]["version"],
                                               full_packageinfo["storage"]["classifier"],
                                               full_packageinfo["storage"]["packaging"])
        full_packageinfo_grouppath = full_packageinfo["storage"]["groupId"].replace(".", "/")
        full_packageinfo_artpath = "%s/%s/%s/%s/%s" % (art_upload_repo, 
                                                       full_packageinfo_grouppath, 
                                                       full_packageinfo["storage"]["artifactId"],
                                                       full_packageinfo["storage"]["version"],
                                                       full_packageinfo_fn)
        spec_f1 = {"pattern":full_packageinfo_fn, "target":full_packageinfo_artpath}

        increment_packageinfo_fn = "%s-%s-%s.%s" % (increment_packageinfo["storage"]["artifactId"],
                                                    increment_packageinfo["storage"]["version"],
                                                    increment_packageinfo["storage"]["classifier"],
                                                    increment_packageinfo["storage"]["packaging"])
        increment_packageinfo_grouppath = increment_packageinfo["storage"]["groupId"].replace(".", "/")
        increment_packageinfo_artpath = "%s/%s/%s/%s/%s" % (art_upload_repo, 
                                                       increment_packageinfo_grouppath, 
                                                       increment_packageinfo["storage"]["artifactId"],
                                                       increment_packageinfo["storage"]["version"],
                                                       increment_packageinfo_fn)
        spec_f2 = {"pattern":increment_packageinfo_fn, "target":increment_packageinfo_artpath}

        patch_packageinfo_fn = "%s-%s-%s.%s" % (patch_packageinfo["storage"]["artifactId"],
                                               patch_packageinfo["storage"]["version"],
                                               patch_packageinfo["storage"]["classifier"],
                                               patch_packageinfo["storage"]["packaging"])
        patch_packageinfo_grouppath = increment_packageinfo["storage"]["groupId"].replace(".", "/")
        patch_packageinfo_artpath = "%s/%s/%s/%s/%s" % (art_upload_repo, 
                                                       patch_packageinfo_grouppath, 
                                                       patch_packageinfo["storage"]["artifactId"],
                                                       patch_packageinfo["storage"]["version"],
                                                       patch_packageinfo_fn)
        spec_f3 = {"pattern":patch_packageinfo_fn, "target":patch_packageinfo_artpath}
        
        art_upload_filespec = {"files":[spec_f1, spec_f2, spec_f3]}

        _serialize_jsonobject(full_packageinfo, full_packageinfo_fn)
        _serialize_jsonobject(increment_packageinfo, increment_packageinfo_fn)
        _serialize_jsonobject(patch_packageinfo, patch_packageinfo_fn)
        
        _serialize_jsonobject(art_upload_filespec, "art_upload.spec")

        cmd = "jfrog rt upload --server-id=%s --spec=%s" % (art_server_id, "art_upload.spec")
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
        print output
    except Exception as err:
        print err
    finally:
        ps.popd()

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
    download_artifact_byspec("/Users/mike/Documents/MikeWorkspace/cikit/test", "mikepro-artifactory", "art_download.json")
    #pass