#!/bin/bash -ex

# Internal script for the workshop to setup all dependencies on a fresh
# Fedora 25 machine
readonly pkg_manager=$(dnf)
readonly backup_path="$HOME/.backup_workshop"
readonly git_repo="https://github.com/lago-project/lago-workshop.git"
readonly venv_name="lago_workshop"

function update_sys() {
    sudo dnf update -y
}

function install_deps() {
    sudo dnf install -y gcc python2 python2-devel python2-epi \
            firefox python2-virtualenvwrapper python2-tox \
            python2-virtualenv git powerline vim-powerline openssl-devel

    sudo dnf copr enable -y heikoada/terminix
    sudo dnf install -y tilix

    # pycharm

}

function install_atom() {
    wget -O /tmp/atom.rpm https://atom.io/download/rpm
    sudo dnf install -y /tmp/atom.rpm
}


function setup_venv() {
    mkdir -p "$HOME/virtualenv"
    virtualenv --system-site-packages "$HOME/virtualenv/$venv_name"
    echo "export WORKON_HOME=$HOME/virtualenv" >> "$HOME/.bashrc"
    source "$HOME/.bashrc"
}

function install_in_venv() {
    source `which virtualenvwrapper.sh`
    export WORKON_HOME="$HOME/virtualenv"
    source "$HOME/virtualenv/$venv_name/bin/activate"
    mkdir -p "$backup_path"
    pushd "$backup_path"
    git clone "$git_repo"
    cd lago-workshop
    pip install -I -r requirements.txt
    cd jenkins-system-tests
    pytest -x -vvv -s ../solutions/test_jenkins.py::TestDeployJenkins
    cd ..
    mkdir -p "$backup_path/live-env/"
    cd /tmp/lago-workdir
    lago stop
    cd ..
    mv lago-workdir "$backup_path/live-env/"
    popd
    deactivate
}


function main() {
    update_sys
    install_deps
    install_atom
    setup_venv
    install_in_venv
}

main
