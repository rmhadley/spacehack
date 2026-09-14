// sh46 — spacehack user-data persistence shim (doc 46, phases 2-3).
//
// Python contract (src/spacehack/user_data.py): the shim lives at
// window.sh46 and is reached via platform.window. put/remove are fired
// with NO callback (fire-and-forget sync); get/keys take one mandatory
// callback. A missing key calls back with null. Names are root-relative
// POSIX paths; values are UTF-8 text. Storage: IndexedDB db "spacehack",
// object store "files" (name -> text).
//
// Failure rule (phase-2 ruling): a broken shim never blocks play —
// get/keys fail soft to null/[] so restore() degrades to "nothing
// persisted"; put/remove swallow their errors.
//
// window.b46mark is boot diagnostics, not persistence: web/main.py
// records boot milestones in the URL hash so a failed boot is readable
// off the page address alone.
(function () {
    "use strict";
    var DB_NAME = "spacehack";
    var STORE = "files";
    var dbp = null;

    function db() {
        if (dbp === null) {
            dbp = new Promise(function (ok, no) {
                var rq = indexedDB.open(DB_NAME);
                rq.onupgradeneeded = function () { rq.result.createObjectStore(STORE); };
                rq.onsuccess = function () { ok(rq.result); };
                rq.onerror = function () { no(rq.error); };
            });
        }
        return dbp;
    }

    function maybe(cb) {
        return function () { if (cb) { cb(); } };
    }

    function write(op, name, value, cb) {
        db().then(function (d) {
            var tx = d.transaction(STORE, "readwrite");
            tx.objectStore(STORE)[op](value, name);
            tx.oncomplete = maybe(cb);
            tx.onerror = maybe(cb);
        }).catch(maybe(cb));
    }

    window.sh46 = {
        put: function (name, text, cb) { write("put", name, text, cb); },
        remove: function (name, cb) { write("delete", name, undefined, cb); },
        get: function (name, cb) {
            db().then(function (d) {
                var rq = d.transaction(STORE, "readonly").objectStore(STORE).get(name);
                rq.onsuccess = function () { cb(rq.result === undefined ? null : rq.result); };
                rq.onerror = function () { cb(null); };
            }).catch(function () { cb(null); });
        },
        keys: function (cb) {
            db().then(function (d) {
                var rq = d.transaction(STORE, "readonly").objectStore(STORE).getAllKeys();
                rq.onsuccess = function () { cb(rq.result || []); };
                rq.onerror = function () { cb([]); };
            }).catch(function () { cb([]); });
        }
    };

    window.b46mark = function (tag) {
        try { history.replaceState(null, "", "#" + tag); } catch (e) { /* diagnostics only */ }
    };
}());
