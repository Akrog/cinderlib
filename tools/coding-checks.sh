#!/bin/sh

set -eu

usage() {
    echo "Usage: $0 [OPTION]..."
    echo "Run Cinderlib's coding check(s)"
    echo ""
    echo " -Y, --pylint [<basecommit>] Run pylint check on the entire cinderlib module or just files changed in basecommit (e.g. HEAD~1)"
    echo " -h, --help   Print this usage message"
    echo
    exit 0
}

process_options() {
    i=1
    while [ $i -le $# ]; do
        eval opt=\$$i
        case $opt in
            -h|--help) usage;;
            -Y|--pylint) pylint=1;;
            *) scriptargs="$scriptargs $opt"
        esac
        i=$((i+1))
    done
}

run_pylint() {
    local target="${scriptargs:-HEAD~1}"

    if [[ "$target" = *"all"* ]]; then
        files="cinderlib"
    else
        files=$(git diff --name-only --diff-filter=ACMRU $target "*.py")
    fi

    if [ -n "${files}" ]; then
        echo "Running pylint against:"
        printf "\t%s\n" "${files[@]}"
        pylint --rcfile=.pylintrc --output-format=colorized ${files} -E \
            -j `python -c 'import multiprocessing as mp; print(mp.cpu_count())'`
    else
        echo "No python changes in this commit, pylint check not required."
        exit 0
    fi
}

scriptargs=
pylint=1

process_options $@

if [ $pylint -eq 1 ]; then
    run_pylint
    exit 0
fi
