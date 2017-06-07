import pytest
import jenkins
import lago.utils
from lago.workdir import PrefixAlreadyExists
from lago import sdk
import os
import testlib
import functools
import scp
import logging


class Job:
    def __init__(self, name, label=None, xml_path=None):
        self.name = name
        self.label = label
        self.xml_path = xml_path

    @property
    def latest_art_path(self):
        return '/var/lib/jenkins/jobs/{}/lastSuccessful/archive/'.format(self.name)


@pytest.fixture(scope='module')
def jenkins_info():
    return {
        'port': 8080,
        'username': 'admin',
        'password': 'admin'
    }


@pytest.fixture(scope='class')
def env(cls_results_path):
    config = 'init-jenkins.yaml'
    workdir = '/tmp/lago-workdir'

    try:
        lago_env = sdk.init(
            config=config,
            workdir=workdir,
            logfile=os.path.join(cls_results_path, 'lago.log'),
            loglevel=logging.DEBUG
        )
    except PrefixAlreadyExists:
        lago_env = sdk.load_env(
            workdir=workdir,
            logfile=os.path.join(cls_results_path, 'lago.log'),
            loglevel=logging.DEBUG
        )
    lago_env.start()

    yield lago_env

    collect_path = os.path.join(cls_results_path, 'collect')
    lago_env.collect_artifacts(output_dir=collect_path, ignore_nopath=True)


class TestDeployJenkins(object):
    @pytest.fixture
    def jenkins_master(self, env):
        vms = env.get_vms()
        return vms['jenkins-master']

    @pytest.mark.lab_1
    def test_deploy_with_ansible(self, env, jenkins_master):
        jenkins_master.ssh_reachable(tries=100)
        result = testlib.deploy_ansible_playbook(
            env, 'ansible/jenkins_playbook.yaml'
        )
        if result:
            print result.err
            raise AssertionError


class TestJenkins(object):
    @pytest.fixture(scope='class')
    def jobs(self):
        return {
            'blank_job': Job('blank_job'),
            'dev_job': Job('dev_job', label='dev', xml_path='jobs/labeled_job.xml'),
            'qa_job': Job('qa_job', label='qa')
        }

    @pytest.fixture(scope='class')
    def dev_job(self, jobs):
        return jobs['dev_job']

    @pytest.fixture(scope='class')
    def blank_job(self, jobs):
        return jobs['blank_job']

    @pytest.fixture(scope='class')
    def labels(self, jobs):
        return sorted(
            map(lambda job: job.label, jobs.values())
        )

    @pytest.fixture(scope='class')
    def plugins(self):
        return ['ssh-slaves']

    @pytest.fixture(scope='class')
    def cred_uuid(self, jenkins_api):
        return testlib.create_credentials_on_jenkins(
            jenkins_api, '5fa49f22-298f-4894-b4b0-b2b5d812f5e0'
        )

    @pytest.fixture('class')
    def jenkins_api(self, env, jenkins_info):
        jenkins_master_vm = env.get_vms()['jenkins-master']
        return jenkins.Jenkins(
            'http://{ip}:{port}'.format(
                ip=jenkins_master_vm.ip(), port=jenkins_info['port']
            ),
            username=jenkins_info['username'],
            password=jenkins_info['password']
        )

    @pytest.mark.lab_2
    def test_basic_api_connection(self, jenkins_api):
        def _test_api():
            user = jenkins_api.get_whoami()
            version = jenkins_api.get_version()
            print('Hello {} from Jenkins {}'.format(user['fullName'], version))

            return True

        testlib.assert_true_within_short(
            _test_api,
            allowed_exceptions=[
                jenkins.BadHTTPException, jenkins.JenkinsException,
                jenkins.TimeoutException
            ]
        )

    @pytest.mark.lab_3
    def test_verify_installed_plugins(self, jenkins_api, plugins):
        installed_plugins = jenkins_api.get_plugins()

        for plugin in plugins:
            assert plugin in installed_plugins

    @pytest.mark.lab_4
    def test_add_slaves(self, jenkins_api, env, cred_uuid):
        def add_slave(hostname, label):
            if jenkins_api.node_exists(hostname):
                return True

            params = {
                'port': '22',
                'username': 'root',
                'host': hostname,
                'credentialsId': cred_uuid,
            }

            jenkins_api.create_node(
                hostname,
                nodeDescription='test slave',
                labels=label,
                numExecutors=1,
                exclusive=True,
                launcher=jenkins.LAUNCHER_SSH,
                launcher_params=params
            )

            return True

        slaves_and_labels = [
            (vm.name(), vm.metadata.get('jenkins-label'))
            for vm in env.get_vms().viewvalues()
            if 'jenkins-slaves' in vm.groups
        ]

        vec = lago.utils.func_vector(add_slave, slaves_and_labels)
        vt = lago.utils.VectorThread(vec)
        vt.start_all()
        assert all(vt.join_all())

        for slave, _ in slaves_and_labels:
            testlib.assert_true_within_short(
                functools.partial(jenkins_api.node_exists, slave)
            )
            testlib.assert_true_within_short(
                lambda: not jenkins_api.get_node_info(slave)['offline']
            )

    @pytest.mark.lab_5
    def test_throw_exception_on_undefined_job(self, jenkins_api):
        with pytest.raises(jenkins.JenkinsException):
            jenkins_api.get_job_info('undefined_job')

    @pytest.mark.lab_5
    def test_create_labled_job(self, jenkins_api, dev_job):
        if jenkins_api.job_exists(dev_job.name):
            return True

        with open(dev_job.xml_path, mode='rt') as f:
            job_xml = f.read()

        jenkins_api.create_job(dev_job.name, job_xml)

        assert jenkins_api.job_exists(dev_job.name)

    @pytest.mark.lab_6
    def test_trigger_labeled_job(self, jenkins_api, env, dev_job):
        labeled_nodes = [
            vm.name() for vm in env.get_vms().viewvalues()
            if vm.metadata.get('jenkins-label') == dev_job.label
        ]
        dev_job_info = jenkins_api.get_job_info(dev_job.name)
        next_build_number = dev_job_info['nextBuildNumber']
        jenkins_api.build_job(dev_job.name)

        def assert_job_run_on_labeled_slave(
            job, build_number, optional_slaves
        ):
            build_info = jenkins_api.get_build_info(job, build_number)
            assert build_info['builtOn'] in optional_slaves

        testlib.allow_exceptions_within_short(
            functools.partial(
                assert_job_run_on_labeled_slave, dev_job.name, next_build_number,
                labeled_nodes
            ), [jenkins.NotFoundException]
        )

    @pytest.mark.lab_7
    def test_collect_and_verify_artifacts_from_master(self, tmpdir, env, dev_job):
        local_artifact_path = os.path.join(str(tmpdir), 'dummy_artifact')
        jenkins_master_vm = env.get_vms()['jenkins-master']
        f = functools.partial(
            jenkins_master_vm.copy_from,
            os.path.join(dev_job.latest_art_path, 'dummy_artifact'),
            local_artifact_path
        )
        testlib.allow_exceptions_within_short(f, [scp.SCPException])

        with open(local_artifact_path, mode='rt') as f:
            result = f.read()

        assert result.rstrip() == 'welcome to pycon israel'

    @pytest.mark.lab_8
    def test_create_blank_job(self, jenkins_api, blank_job):
        if not jenkins_api.job_exists(blank_job.name):
            jenkins_api.create_job(blank_job.name, jenkins.EMPTY_CONFIG_XML)

        assert jenkins_api.job_exists(blank_job.name)

    @pytest.mark.lab_8
    def test_trigger_blank_job(self, jenkins_api, blank_job):
        jenkins_api.build_job(blank_job.name)