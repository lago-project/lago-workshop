import pytest


def test_is_groovy_bad_for_you():
    assert True


def test_catch_me():
    with pytest.raises(RuntimeError):
        raise RuntimeError()


@pytest.mark.parametrize(
    'a, b, expected',
    [
        (1, 2, 3),
        (1, 0, 1),
        (0, 0, 0)
    ]
)
def test_expectations_vs_reality(a, b, expected):
    assert a + b == expected
