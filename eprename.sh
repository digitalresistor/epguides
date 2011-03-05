#!/usr/bin/env bash

DEST="$1"
shift
FILENAME="$@"
EFILENAME=`epguides.py "$FILENAME"`

if [ $? -gt 0 ]; then
	echo "Seems there was an error"
	exit 1
fi

NFILENAME=`echo $EFILENAME | sed -E "s/([0-9]+) ([0-9]+) (.*)/Season \1\/Episode \2 - \3.avi/"`

DIR=`echo $NFILENAME | sed -E "s/(.+)\/.*/\1/"`

DESTDIR="$DEST/$DIR"

if [ ! -d "$DESTDIR" ]; then
	mkdir "$DESTDIR"
fi

mv "$FILENAME" "$DEST/$NFILENAME"