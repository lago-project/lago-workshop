import lago.lago_ansible as lago_ansible
from lago import utils
import itertools
import jenkins
from six.moves.urllib.request import Request, urlopen
from six.moves.urllib.parse import quote, urlencode, urljoin, urlparse
import time

SHORT_TIMEOUT = 3 * 60
LONG_TIMEOUT = 10 * 60

def deploy_ansible_playbook(
        prefix, playbook_path, vars_dict=None,
        env_vars=None, host_key_checking=False,
        user='root', **kwargs
):

    if not env_vars:
        env_vars = {}

    if not host_key_checking:
        env_vars.update({'ANSIBLE_HOST_KEY_CHECKING': 'False'})

    ansible_instance = lago_ansible.LagoAnsible(prefix)

    if vars_dict:
        extra_vars = ' '.join(['{}={}'.format(k, v) for k, v in vars_dict.viewitems()])
    else:
        extra_vars = ''

    extra_args = list(itertools.chain(*kwargs.viewitems()))

    with ansible_instance.get_inventory_temp_file() as inventory:
        cmd = [
            'ansible-playbook',
            playbook_path,
            '-i',
            inventory.name,
            '-u',
            user,
            '-v',
            '-e',
            extra_vars,
        ]
        cmd.extend(extra_args)

        return utils.run_interactive_command(cmd, env=env_vars)


def create_credentials_on_jenkins(jenkins_api, _uuid):
    cred_exist = has_credentials_on_jenkins(jenkins_api, _uuid)
    if cred_exist:
        return cred_exist

    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    payload = '''json={
        "": "0",
        "credentials": {
            "scope": "GLOBAL",
            "id": "%s",
            "username": "root",
            "password": "123456",
            "description": "test",
            "$class": "com.cloudbees.plugins.credentials.impl.UsernamePasswordCredentialsImpl"
        }
    }''' % _uuid
    url = jenkins_api._build_url('credentials/store/system/domain/_/createCredentials')
    request = Request(url, payload, headers)
    jenkins_api.jenkins_open(request)

    return has_credentials_on_jenkins(jenkins_api, _uuid)


def has_credentials_on_jenkins(jenkins_api, _uuid):
    headers = {'Content-Type': 'application/json'}
    path = 'credentials/store/system/domain/_/credential/%(uuid)s/api/json'
    url = jenkins_api._build_url(path, {'uuid': _uuid})
    request = Request(url, headers=headers)
    try:
        jenkins_api.jenkins_open(request)
        return _uuid
    except jenkins.NotFoundException:
        return False


def _instance_of_any(obj, cls_list):
    return any(True for cls in cls_list if isinstance(obj, cls))


def allow_exceptions_within_timeout(func, timeout, allowed_exceptions=None):
    allowed_exceptions = allowed_exceptions or [Exception]
    with utils.EggTimer(timeout=timeout) as timer:
        while not timer.elapsed():
            try:
                return func()
            except Exception as exc:
                if not _instance_of_any(exc, allowed_exceptions):
                    raise

            time.sleep(3)


def allow_exceptions_within_short(func, allowed_exceptions=None):
    return allow_exceptions_within_timeout(
        func, SHORT_TIMEOUT, allowed_exceptions
    )


def allow_exceptions_within_long(func, allowed_exceptions=None):
    return allow_exceptions_within_timeout(
        func, LONG_TIMEOUT, allowed_exceptions
    )


def assert_equals_within(func, value, timeout, allowed_exceptions=None):
    allowed_exceptions = allowed_exceptions or []
    with utils.EggTimer(timeout) as timer:
        while not timer.elapsed():
            try:
                res = func()
                if res == value:
                    return
            except Exception as exc:
                if _instance_of_any(exc, allowed_exceptions):
                    continue
                raise

            time.sleep(3)
    try:
        raise AssertionError(
            '%s != %s after %s seconds' % (res, value, timeout)
        )
    # if func repeatedly raises any of the allowed exceptions, res remains
    # unbound throughout the function, resulting in an UnboundLocalError.
    except UnboundLocalError:
        raise AssertionError(
            '%s failed to evaluate after %s seconds' %
            (func.__name__, timeout)
        )


def assert_equals_within_short(func, value, allowed_exceptions=None):
    allowed_exceptions = allowed_exceptions or []
    assert_equals_within(
        func, value, SHORT_TIMEOUT, allowed_exceptions=allowed_exceptions
    )


def assert_equals_within_long(func, value, allowed_exceptions=None):
    allowed_exceptions = allowed_exceptions or []
    assert_equals_within(
        func, value, LONG_TIMEOUT, allowed_exceptions=allowed_exceptions
    )


def assert_true_within(func, timeout, allowed_exceptions=None):
    assert_equals_within(func, True, timeout, allowed_exceptions)


def assert_true_within_short(func, allowed_exceptions=None):
    assert_equals_within_short(func, True, allowed_exceptions)


def assert_true_within_long(func, allowed_exceptions=None):
    assert_equals_within_long(func, True, allowed_exceptions)