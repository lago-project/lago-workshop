#!/bin/bash -ex

# internal script to setup the Lago workshop on Fedora 25
# assumes Lago is already installed
readonly backup_path_old="$HOME/.backup_workshop"
readonly backup_path="$HOME/backup"
readonly git_repo="https://github.com/lago-project/lago-workshop.git"
readonly venv_name="lago_workshop"


function update_sys() {
    sudo dnf update -y
}


function install_deps() {
    sudo dnf install -y gcc python2 python2-devel python2-epi \
            firefox python2-virtualenvwrapper python2-tox \
            python2-virtualenv git powerline vim-powerline openssl-devel \
            tree

    sudo dnf copr enable -y heikoada/terminix
    sudo dnf install -y tilix

}

function install_atom() {
    if ! rpm -q atom &> /dev/null; then
        wget -O /tmp/atom.rpm https://atom.io/download/rpm
        sudo dnf install -y /tmp/atom.rpm
    fi
}


function setup_venv() {
    rm -rf "$HOME/virtualenv"
    mkdir -p "$HOME/virtualenv"
    virtualenv --system-site-packages "$HOME/virtualenv/$venv_name"
    echo "export WORKON_HOME=$HOME/virtualenv" >> "$HOME/.bashrc"
    source "$HOME/.bashrc"
}

function install_in_venv() {
    source "$(which virtualenvwrapper.sh)"
    source "$HOME/virtualenv/$venv_name/bin/activate"
    rm -rf "$backup_path"
    rm -rf "$backup_path_old"
    mkdir -p "$backup_path"
    pushd "$backup_path"
    git clone "$git_repo"
    cd lago-workshop
    pip install -I -r requirements.txt
    cd jenkins-system-tests
    pytest -x -vvv -s ../solutions/test_jenkins.py::TestDeployJenkins
    cd ..
    cd /tmp/lago-workdir
    lago stop
    cd ..
    mv lago-workdir "$backup_path/"
    echo "$backup_path/lago-workdir" > "$HOME/workshop_backup_path.txt"
    popd
    deactivate
}


function main() {
    rm -rf "$HOME/lago-workshop"
    update_sys
    install_deps
    install_atom
    setup_venv
    install_in_venv
}

main
