cd ..
APPDIR=rentmap.git
~/google_appengine/dev_appserver.py \
    --address 0.0.0.0 --port 8090 $APPDIR \
    --datastore_path=$APPDIR/data/dev_appserver.datastore \
    --rdbms_sqlite_path=$APPDIR/data/dev_appserver.rdbms \
    &> $APPDIR/rentmap.log
