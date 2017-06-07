import pytest
import os
import shutil


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
