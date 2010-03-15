#!/usr/bin/env bash

DIR="$1"

if [ -z "$DIR" ] ; then
    echo "Usage: $(basename $0) DIR"
    exit 2
fi

if [ ! -e "$DIR/bin/python" ] ; then
    silver init $DIR
fi
cd $DIR

if [ ! -e src/silverlog/.hg ] ; then
    hg clone ssh://hg@bitbucket.org/ianb/silverlog src/silverlog
fi
if [ ! -e lib/python/.hg ] ; then
    rmdir lib/python
    hg clone ssh://hg@bitbucket.org/ianb/silverlog-lib lib/python
fi

if [ -d lib/python/bin ] ; then
    pushd bin
    for F in ../lib/python/bin/* ; do
        if [ ! -e "$(basename $F)" ] ; then
            ln -s $F
        else
            echo "$F cannot be linked, bin/$(basename $F) already exists"
        fi
    done
    popd
fi

if [ ! -L app.ini ] ; then
    rm -f app.ini
    ln -s src/silverlog/silver-app.ini app.ini
fi
if [ ! -L static ] ; then
    rmdir static
    ln -s src/silverlog/silverlog/static static
fi

    

