// Offline execution of the actual restore hook and API error classifier.
// The hook adapter observes state/effects; only fetch and browser storage are fake.
(async () => {
const { default: assert } = await import("node:assert/strict");
const { default: fs } = await import("node:fs");
const { default: path } = await import("node:path");
const { default: ts } = await import("typescript");
const { default: vm } = await import("node:vm");

function load(relative, bindings) {
  const exports = {};
  const filename = path.resolve(__dirname, relative);
  const code = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
    compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020},
  }).outputText;
  vm.runInNewContext(code, {exports, Error, process: {env: {}}, ...bindings}, {filename});
  return exports;
}

async function scenario(status) {
  const states = [];
  const effects = [];
  let stored = "synthetic-tab-token";
  let cleared = 0;
  let refreshed = 0;
  const messages = [];
  const api = load("../lib/api.ts", {fetch: async (url, options) => {
    assert.match(url, /\/api\/auth\/me$/);
    assert.equal(options.headers.Authorization, "Bearer synthetic-tab-token");
    if (status === "network") throw new TypeError("Failed to fetch");
    return {ok: status === 200, status, json: async () => status === 200
      ? {user: {user_id: "synthetic", name: "Synthetic"}}
      : {detail: `Synthetic status ${status}`}};
  }, TypeError});
  const hook = load("../app/hooks/useAuthState.ts", {
    window: {},
    require(name) {
      if (name === "react") return {
        useState(initial) {
          const index = states.length;
          states.push(typeof initial === "function" ? initial() : initial);
          return [states[index], value => { states[index] = typeof value === "function" ? value(states[index]) : value; }];
        },
        useRef: value => ({current: value}),
        useCallback: callback => callback,
        useEffect: callback => effects.push(callback),
        useLayoutEffect: callback => effects.push(callback),
      };
      if (name === "../../lib/api") return api;
      if (name === "../utils/loginRetry") return {};
      assert.equal(name, "../utils/auth");
      return {
        getStoredToken: () => stored,
        shouldRestoreStoredToken: () => true,
        clearStoredToken: () => { stored = ""; cleared++; },
      };
    },
  }).default;
  hook({skipInitialAuthStatus: true,
    onStatusMessage: message => messages.push(message),
    onRefreshProjects: async () => { refreshed++; },
    onRefreshJobs: async () => { refreshed++; }});
  effects.forEach(effect => effect());
  await new Promise(resolve => setImmediate(resolve));
  if (status === 401) {
    assert.equal(stored, "");
    assert.equal(states[0], "");
    assert.equal(cleared, 1);
  } else {
    assert.equal(stored, "synthetic-tab-token", `${status} must not erase a potentially valid session`);
    assert.equal(states[0], "synthetic-tab-token");
    assert.equal(cleared, 0);
  }
  assert.equal(refreshed, status === 200 ? 2 : 0);
  assert.equal(messages.length, status === 200 || status === 401 ? 0 : 1);
  if (messages.length) assert.ok(messages[0].length > 0, "Transient failure must be visible to the user");
  console.log(`PASS: restore ${status}`);
}

(async () => {
  for (const status of [429, 500, 503, 403, "network", 401, 200]) await scenario(status);
})().catch(error => {console.error(error); process.exitCode = 1;});
})().catch(error => {console.error(error); process.exitCode = 1;});
