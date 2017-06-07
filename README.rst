Lago Workshop
===============

About
------
In this workshop you will learn how to create system tests
for your application using Lago and Pytest.

Prerequisite
--------------
- `Install Lago <https://github.com/lago-project/lago-demo/blob/master/install_scripts/install_lago.sh?>`_
- Create a virtual env which includes the system's libraries and the deps in requirements.txt,
  this can be done using the following commands::

     su - <user>
     git clone https://github.com/lago-project/lago-workshop
     virtualenv --system-site-packages lago_venv
     source lago_venv/bin/activate
     pip install -I -r requirements.txt


About the environment
----------------------
- VMs:
    - jenkins-master
    - jenkins-slave-0
    - jenkins-slave-1
    - file-server
- Networks:
    - management-net (All the vms are connected)
    - jenkins-internal-net (Only jenkins-* vms are connected)

Running the env and installing jenkins with ansible (will be replaced by lago sdk)
-----------------------------------------------------------------------------------
Run the following commands::

    lago init
     lago start
     python -m pytest -s -v -x test_jenkins.py
#    lago ansible_hosts > ansible_hosts
#     ansible-playbook ansible/jenkins_playbook.yaml -i ansible_hosts  -u root

| At the end of this process you can access jenkins from your browser.
| The deployment takes about 10 minutes.

Resources
------------
- Ansible role for installing jenkins: https://galaxy.ansible.com/geerlingguy/jenkins/
