# cikit - A tool to easy ci/cd setup on top of jenkins, artifactory, git ...

## Build everything needed to install
1. python setup.py build

## Build a source distribution
1. python setup.py sdist

## Setup and configure JFrog CLI
1. Download jfrog cli: https://www.jfrog.com/getcli/;

2. Command to register artifactory server:  
jfrog rt config --url=xxxx --apikey=xxxx --interactive=false <serverid>  
- --url: The url of artifactory url;
- --apikey: The api key of artifactory account which will be used by jfrog cli;
- serverid: Name of the current artifactory server being registerred.

jfrog cli config file is located at "~/.jfrog/jfrog-cli.conf"  

example:  
jfrog rt config --url=http://www.test.com:8080/artifactory --apikey=APtmqnQd2ScqZtSF8z8CoM2eEB34jYX2XisQpG --interactive=false mike-artifactory  

"~/.jfrog/jfrog-cli.conf":  

```
{
  "artifactory": [
    {
      "url": "http://www.test.com:8080/artifactory",
      "apiKey": "APtmqnQd2ScqZtSF8z8CoM2eEB34jYX2XisQpG",
      "serverId": "mike-artifactory",
      "isDefault": true
    }
  ],
  "Version": "1"
}

```

3. Command to show the config of jfrog cli  
jfrog cli config show

# Concept point
## In package.json
- **component**: it should be generated from one git repository with ci build jobs, and it will consist of the final product package.  
  However, the ci builds for one git repoistory may generate many binary files which will be part of the component will be treated  
  as component. Also, some git repository from which the binary was generated was only used by other git repository and will be packaged  
  in one or more real component, those binaries should also not be a component.