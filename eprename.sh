#!/usr/bin/env bash

DEST="$1"
shift
FILENAME="$@"
EFILENAME=`epguides.py "$FILENAME"`

if [ $? -gt 0 ]; then
	echo "Seems there was an error"
	exit 1
fi

SUFFIX=${FILENAME##*.}

NFILENAME=`echo $EFILENAME | sed -E "s/([0-9]+) ([0-9]+) (.*)/Season \1\/Episode \2 - \3.${SUFFIX}/"`

DIR=`echo $NFILENAME | sed -E "s/(.+)\/.*/\1/"`

DESTDIR="$DEST/$DIR"

if [ ! -d "$DESTDIR" ]; then
	mkdir "$DESTDIR"
fi

DEST=$DEST/$NFILENAME

echo "Moving: " $FILENAME " to: " ${DEST}

mv "$FILENAME" "${DEST}"
