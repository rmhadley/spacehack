// sh46 — spacehack user-data persistence shim (doc 46, phases 2-3).
//
// Two page-injected responsibilities, loaded BEFORE the pygbag
// loader (index.tmpl injects this file first):
//
// 1. window.sh46 — IndexedDB persistence. Python contract
//    (src/spacehack/user_data.py): reached via platform.window;
//    put/remove are fired with NO callback (fire-and-forget sync);
//    get/keys take one mandatory callback; a missing key calls
//    back with null. Names are root-relative POSIX paths; values
//    are UTF-8 text. Storage: IndexedDB db "spacehack", object
//    store "files" (name -> text). Failure rule (phase-2 ruling):
//    a broken shim never blocks play — get/keys fail soft to
//    null/[] so restore() degrades to "nothing persisted";
//    put/remove swallow their errors.
//
// 2. window.fetch rewrite — self-containment (Ruling 5): the
//    runtime's package machinery hardcodes the pygbag CDN as its
//    wheel-repo base in two places (the index's "-CDN-" entry and
//    a localhost-8 dev-mode heuristic pointing at pygbag's own
//    dev server, port 8000); rewriting any cross-origin /cdn/...
//    URL onto the page origin keeps every runtime request on the
//    local /cdn/ mirror.
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

    window.sh46 = {
        // put(value, key) and delete(key) take different arity — no
        // shared helper (a uniform [op](value, name) call silently
        // breaks delete: undefined is not a valid IDB key).
        put: function (name, text, cb) {
            db().then(function (d) {
                var tx = d.transaction(STORE, "readwrite");
                tx.objectStore(STORE).put(text, name);
                tx.oncomplete = maybe(cb);
                tx.onerror = maybe(cb);
            }).catch(maybe(cb));
        },
        remove: function (name, cb) {
            db().then(function (d) {
                var tx = d.transaction(STORE, "readwrite");
                tx.objectStore(STORE).delete(name);
                tx.oncomplete = maybe(cb);
                tx.onerror = maybe(cb);
            }).catch(maybe(cb));
        },
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

    // Self-containment (doc 46, Ruling 5): the runtime hardcodes
    // the pygbag CDN as its wheel-repo base in TWO places inside
    // its packed aio module — the index's "-CDN-" entry, and a
    // dev-mode heuristic that rewrites the base to
    // http://localhost:8000/cdn/ whenever the page URL starts with
    // http://localhost:8 (pygbag's own dev server). Neither is
    // patchable as a file; rewriting ANY cross-origin /cdn/... URL
    // onto the page origin at this single fetch seam keeps every
    // runtime request on the local mirror regardless of which
    // base fired.
    var PAGE_ORIGIN = location.origin;
    var nativeFetch = window.fetch;
    window.fetch = function (input, init) {
        var url = typeof input === "string" ? input : (input && input.url);
        if (typeof url === "string" && url.indexOf("/cdn/") !== -1) {
            try {
                var abs = new URL(url, PAGE_ORIGIN);
                if (abs.origin !== PAGE_ORIGIN && abs.pathname.indexOf("/cdn/") === 0) {
                    input = abs.pathname + abs.search + abs.hash;
                }
            } catch (e) { /* unparsable input: pass it through */ }
        }
        return nativeFetch.call(window, input, init);
    };
}());
