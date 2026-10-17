// Actual hook/API code, controlled asynchronous responses, no network or clocks.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const ts = require("typescript");
const vm = require("node:vm");
const flush = () => new Promise(resolve => setImmediate(resolve));
const response = (status, body) => ({status, ok: status === 200, json: async () => body});
function deferred() { let resolve; const promise = new Promise(done => {resolve = done;}); return {promise, resolve}; }
function load(relative, bindings) {
  const exports = {};
  const filename = path.resolve(__dirname, relative);
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(filename, "utf8"), {
    compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020},
  }).outputText, {exports, Error, process: {env: {}}, ...bindings}, {filename});
  return exports;
}
function fixture({deferLogout = false} = {}) {
  const states = [], effects = [], refreshes = [], messages = [], posts = [];
  const restore = deferred();
  const logout = deferred();
  let stored = "old-token", writes = 0;
  const api = load("../lib/api.ts", {fetch: async url => {
    if (url.endsWith("/api/auth/me")) return restore.promise;
    if (url.endsWith("/api/auth/logout")) return deferLogout ? logout.promise : response(200, {});
    assert.match(url, /\/api\/auth\/register$/);
    const post = deferred(); posts.push(post); return post.promise;
  }});
  const hook = load("../app/hooks/useAuthState.ts", {window: {}, require(name) {
    if (name === "react") return {
      useState(initial) { const i = states.length; states.push(typeof initial === "function" ? initial() : initial);
        return [states[i], value => {writes++; states[i] = typeof value === "function" ? value(states[i]) : value;}]; },
      useRef: current => ({current}), useCallback: callback => callback,
      useEffect: callback => effects.push(callback), useLayoutEffect: callback => effects.push(callback),
    };
    if (name === "../../lib/api") return api;
    if (name === "../utils/loginRetry") return {};
    assert.equal(name, "../utils/auth");
    return {getStoredToken: () => stored, shouldRestoreStoredToken: () => true,
      clearStoredToken: () => {stored = "";}, setStoredToken: token => {stored = token;}};
  }}).default;
  const actions = hook({skipInitialAuthStatus: true,
    onRefreshProjects: async token => {refreshes.push(token);},
    onRefreshJobs: async token => {refreshes.push(token);},
    onStatusMessage: message => messages.push(message)});
  const cleanups = effects.map(effect => effect());
  return {states, refreshes, messages, posts, restore, logout, actions,
    get stored() {return stored;}, get writes() {return writes;},
    cleanup: () => cleanups.forEach(cleanup => {if (typeof cleanup === "function") cleanup();})};
}
function complete(post, name) {post.resolve(response(200, {token: `${name}-token`, user: {user_id: name, name}}));}

const cases = [
  ...[401, 200, 429].map(status => [`old restore ${status} cannot overwrite new sign-in`, async () => {
    const f = fixture(); const login = f.actions.handleAuth(); complete(f.posts[0], "new"); await login;
    f.restore.resolve(response(status, {user: {user_id: "old", name: "Old"}})); await flush();
    assert.equal(f.stored, "new-token"); assert.equal(f.states[0], "new-token");
    assert.equal(f.states[1].user_id, "new"); assert.deepEqual(f.refreshes, ["new-token", "new-token"]);
    assert.deepEqual(f.messages, ["Signed in to Civora AI as new."]);
  }]),
  ["restore after logout cannot restore user or refresh old data", async () => {
    const f = fixture(); await f.actions.handleLogout();
    f.restore.resolve(response(200, {user: {user_id: "old"}})); await flush();
    assert.equal(f.stored, ""); assert.equal(f.states[0], ""); assert.equal(f.states[1], null);
    assert.deepEqual(f.refreshes, []);
  }],
  ["pending sign-in cannot undo logout", async () => {
    const f = fixture(); const login = f.actions.handleAuth(); await f.actions.handleLogout();
    complete(f.posts[0], "new"); await login;
    assert.equal(f.stored, ""); assert.equal(f.states[0], ""); assert.equal(f.states[1], null);
    assert.deepEqual(f.refreshes, []);
  }],
  ["newest sign-in attempt wins out-of-order responses", async () => {
    const f = fixture(); const first = f.actions.handleAuth(); const second = f.actions.handleAuth();
    complete(f.posts[1], "second"); await second; complete(f.posts[0], "first"); await first;
    assert.equal(f.stored, "second-token"); assert.equal(f.states[1].user_id, "second");
    assert.deepEqual(f.refreshes, ["second-token", "second-token"]);
  }],
  ["unmounted restore has no state or refresh side effects", async () => {
    const f = fixture(); f.cleanup(); const writes = f.writes;
    f.restore.resolve(response(200, {user: {user_id: "old"}})); await flush();
    assert.equal(f.writes, writes); assert.deepEqual(f.refreshes, []);
  }],
  ["delayed logout completion cannot clear a later sign-in", async () => {
    const f = fixture({deferLogout: true}); const logout = f.actions.handleLogout();
    const login = f.actions.handleAuth(); complete(f.posts[0], "new"); await login;
    f.logout.resolve(response(200, {})); await logout;
    assert.equal(f.stored, "new-token"); assert.equal(f.states[1].user_id, "new");
    assert.equal(f.messages.at(-1), "Signed in to Civora AI as new.");
  }],
  ["old sign-in failure cannot replace newer success or loading state", async () => {
    const f = fixture(); const first = f.actions.handleAuth(); const second = f.actions.handleAuth();
    complete(f.posts[1], "second"); await second;
    f.posts[0].resolve(response(503, {detail: "Old attempt failed"})); await first;
    assert.equal(f.stored, "second-token"); assert.equal(f.states[9], ""); assert.equal(f.states[10], false);
    assert.equal(f.messages.at(-1), "Signed in to Civora AI as second.");
  }],
  ["unmounted pending sign-in has no state or refresh side effects", async () => {
    const f = fixture(); const login = f.actions.handleAuth(); f.cleanup(); const writes = f.writes;
    complete(f.posts[0], "new"); await login;
    assert.equal(f.writes, writes); assert.deepEqual(f.refreshes, []); assert.equal(f.stored, "old-token");
  }],
];
(async () => {
  let failed = 0;
  for (const [name, check] of cases) {
    try {await check(); console.log(`PASS: ${name}`);} catch (error) {failed++; console.error(`FAIL: ${name}`, error);}
  }
  if (failed) process.exitCode = 1;
})().catch(error => {console.error(error); process.exitCode = 1;});
