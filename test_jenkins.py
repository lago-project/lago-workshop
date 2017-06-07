import pytest
import jenkins
import lago.workdir
import lago.utils
from lago.workdir import PrefixAlreadyExists
from lago import sdk
import os
import testlib
import functools
import scp
import logging
import shutil

JENKINS_PORT = 8080
JENKINS_USERNAME = 'admin'
JENKINS_PASSWORD = 'admin'

BLANK_JOB_1 = 'blank_job_1'
DEV_JOB = 'dev_job'
DEV_LABEL = 'dev'
QA_JOB = 'qa_job'
QA_LABEL = 'qa'

LABELS = (DEV_LABEL, QA_LABEL)
PLUGINS = ('ssh-slaves', )

CRED_UUID = '5fa49f22-298f-4894-b4b0-b2b5d812f5e0'
LABELED_JOB_PATH = 'jobs/labeled_job.xml'
DEV_JOB_ARTIFACTS_PATH = '/var/lib/jenkins/jobs/dev_job/lastSuccessful/archive/dummy_artifact'


@pytest.fixture(scope='module')
def module_results_path(request):
    current_dir = os.path.abspath(os.getcwd())
    results_path = os.path.join(
        current_dir, 'test_results', str(request.module.__name__)
    )
    if os.path.isdir(results_path):
        shutil.rmtree(results_path)

    os.makedirs(results_path)

    return results_path


@pytest.fixture(scope='class')
def cls_results_path(request, module_results_path):
    results_path = os.path.join(module_results_path, str(request.cls.__name__))
    os.makedirs(results_path)

    return results_path


@pytest.fixture(scope='function')
def func_results_path(request, cls_results_path):
    results_path = os.path.join(
        cls_results_path, str(request.function.__name__)
    )
    os.makedirs(results_path)

    return results_path


class TestDeployJenkins(object):
    @pytest.fixture(scope='class')
    def env(self, cls_results_path):
        config = 'init-jenkins.yaml'
        workdir = '/tmp/lago-workdir'

        lago_env = sdk.init(
            config=config,
            workdir=workdir,
            logfile=os.path.join(cls_results_path, 'lago.log'),
            loglevel=logging.DEBUG
        )
        lago_env.start()

        yield lago_env

        collect_path = os.path.join(cls_results_path, 'collect')
        lago_env.collect_artifacts(output_dir=collect_path, ignore_nopath=True)

        # lago_env.destroy()

    @pytest.fixture
    def jenkins_master(self, env):
        vms = env.get_vms()
        return vms['jenkins-master']

    def test_deploy_with_ansible(self, env, jenkins_master):
        """
        If 'deploy.marker' file does not exist in the env, deploy the env
        using Ansible and create a marker file on success.

        Args:
            env (lago.prefix.Prefix): The env the should be deployed

        """
        jenkins_master.ssh_reachable(tries=100)
        result = testlib.deploy_ansible_playbook(
            env, 'ansible/jenkins_playbook.yaml'
        )
        if result:
            print result.err
            raise AssertionError


class TestJenkins(object):
    @pytest.fixture(scope='class')
    def env(self, cls_results_path):
        workdir = '/tmp/lago-workdir'

        lago_env = sdk.load_env(
            workdir=workdir,
            logfile=os.path.join(cls_results_path, 'lago.log'),
            loglevel=logging.DEBUG
        )

        yield lago_env

        collect_path = os.path.join(cls_results_path, 'collect')
        lago_env.collect_artifacts(output_dir=collect_path, ignore_nopath=True)

        # lago_env.destroy()

    @pytest.fixture('class')
    def jenkins_api(self, env):
        jenkins_master_vm = env.get_vms()['jenkins-master']
        return jenkins.Jenkins(
            'http://{ip}:{port}'.format(
                ip=jenkins_master_vm.ip(), port=JENKINS_PORT
            ),
            username=JENKINS_USERNAME,
            password=JENKINS_PASSWORD
        )

    @pytest.fixture()
    def cred_uuid(self, jenkins_api):
        return testlib.create_credentials_on_jenkins(jenkins_api, CRED_UUID)

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

    def test_verify_installed_plugins(self, jenkins_api):
        installed_plugins = jenkins_api.get_plugins()

        for plugin in PLUGINS:
            assert plugin in installed_plugins

    def test_create_blank_job(self, jenkins_api):
        if not jenkins_api.job_exists(BLANK_JOB_1):
            jenkins_api.create_job(BLANK_JOB_1, jenkins.EMPTY_CONFIG_XML)

        assert jenkins_api.job_exists(BLANK_JOB_1)

    def test_create_labled_job(self, jenkins_api):
        if jenkins_api.job_exists(DEV_JOB):
            return True

        with open(LABELED_JOB_PATH, mode='rt') as f:
            job_xml = f.read()

        jenkins_api.create_job(DEV_JOB, job_xml)

        assert jenkins_api.job_exists(BLANK_JOB_1)

    def test_throw_exception_on_undefined_job(self, jenkins_api):

        with pytest.raises(jenkins.JenkinsException):
            jenkins_api.get_job_info('undefined_job')

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

    def test_trigger_blank_job(self, jenkins_api):
        jenkins_api.build_job(BLANK_JOB_1)

    def test_trigger_labeled_job(self, jenkins_api, env):
        labeled_nodes = [
            vm.name() for vm in env.get_vms().viewvalues()
            if vm.metadata.get('jenkins-label') == DEV_LABEL
        ]
        dev_job_info = jenkins_api.get_job_info(DEV_JOB)
        next_build_number = dev_job_info['nextBuildNumber']
        jenkins_api.build_job(DEV_JOB)

        def has_running_build():
            running_builds = jenkins_api.get_running_builds()
            return len(running_builds) == 0

        def assert_job_run_on_labeled_slave(
            job, build_number, optional_slaves
        ):
            build_info = jenkins_api.get_build_info(job, build_number)
            assert build_info['builtOn'] in optional_slaves

        testlib.assert_true_within_short(has_running_build)

        testlib.allow_exceptions_within_short(
            functools.partial(
                assert_job_run_on_labeled_slave, DEV_JOB, next_build_number,
                labeled_nodes
            ), [jenkins.NotFoundException]
        )

    def test_collect_and_verify_artifacts_from_master(self, env, tmpdir):
        local_artifact_path = os.path.join(str(tmpdir), 'dummy_artifact')
        jenkins_master_vm = env.get_vms()['jenkins-master']
        f = functools.partial(
            jenkins_master_vm.copy_from, DEV_JOB_ARTIFACTS_PATH,
            local_artifact_path
        )
        testlib.allow_exceptions_within_short(f, [scp.SCPException])

        with open(local_artifact_path, mode='rt') as f:
            result = f.read()

        assert result.rstrip() == 'welcome to pycon israel'
