About
-----
This is an example of how to write system tests using Lago and Pytest.
Tests are located in test_jenkins.yaml.
Helper functions are located in testlib.py.
The deployment of the env will be done using Ansible (it will be called as part of the tests),
The playbook location is../ansible/jenkins_playbook.yaml.


The environment
---------------
- VMs:
    - jenkins-master
    - jenkins-slave-0
    - jenkins-slave-1
- Networks:
    - management-net (All the vms are connected)

Running the tests
-----------------
Run the following commands from ../jenkins-system-tests::

    python -m pytest -v -s -x test_jenkins.py

Resources
---------

- Ansible role for installing jenkins: https://galaxy.ansible.com/geerlingguy/jenkins/
