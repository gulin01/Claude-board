// Agent Board Tabs: tells the local Agent Board (http://127.0.0.1:4317, this computer only) which tabs are
// open in this Chrome profile, and switches to or opens a tab when you click one on the board.
// It sends tab titles and addresses only, never page contents, and skips incognito windows.
const BOARD = "ws://127.0.0.1:4317/ws/tabs";
let ws = null, email = "", ping = null, pending = null;

async function profileEmail() {
  try { return (await chrome.identity.getProfileUserInfo({ accountStatus: "ANY" })).email || ""; } catch { return ""; }
}

async function snapshot() {
  const wins = await chrome.windows.getAll({ populate: true, windowTypes: ["normal"] });
  const tabs = [];
  for (const w of wins) {
    if (w.incognito) continue;
    for (const t of w.tabs || []) {
      tabs.push({ window: w.id, tab: t.id, index: t.index + 1, active: t.active, focused: w.focused,
                  title: t.title || "", url: t.url || t.pendingUrl || "" });
    }
  }
  return tabs;
}

function send(msg) { if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg)); }

// Tab events come in bursts; report once things settle.
function push() {
  connect();
  clearTimeout(pending);
  pending = setTimeout(async () => send({ type: "tabs", email, tabs: await snapshot() }), 300);
}

async function openTab(url) {
  const wins = (await chrome.windows.getAll({ windowTypes: ["normal"] })).filter(w => !w.incognito);
  const w = wins.find(x => x.focused) || wins[0];
  if (!w) return chrome.windows.create({ url, focused: true });
  await chrome.tabs.create({ windowId: w.id, url, active: true });
  await chrome.windows.update(w.id, { focused: true });
}

function connect() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
  try { ws = new WebSocket(BOARD); } catch { ws = null; return; }
  ws.onopen = async () => {
    email = await profileEmail();
    send({ type: "hello", email, version: chrome.runtime.getManifest().version });
    push();
    clearInterval(ping);
    ping = setInterval(() => send({ type: "ping" }), 20000);   // keeps this worker awake while the board runs
  };
  ws.onmessage = async (e) => {
    let m; try { m = JSON.parse(e.data); } catch { return; }
    try {
      if (m.type === "focus") {
        await chrome.tabs.update(m.tab, { active: true });
        await chrome.windows.update(m.window, { focused: true });
      } else if (m.type === "open" && /^https?:\/\//i.test(m.url || "")) {
        await openTab(m.url);
      } else if (m.type === "refresh") {
        push();
      }
    } catch (err) { send({ type: "error", message: String(err) }); }
  };
  ws.onclose = () => { clearInterval(ping); ws = null; };
  ws.onerror = () => {};
}

for (const ev of [chrome.tabs.onCreated, chrome.tabs.onRemoved, chrome.tabs.onActivated, chrome.tabs.onMoved,
                  chrome.tabs.onAttached, chrome.tabs.onDetached, chrome.windows.onFocusChanged, chrome.windows.onRemoved]) {
  ev.addListener(push);
}
chrome.tabs.onUpdated.addListener((_id, change) => { if (change.title || change.url || change.status === "complete") push(); });
// If the board wasn't running, try again every 30 seconds.
chrome.alarms.create("reconnect", { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener(connect);
chrome.runtime.onStartup.addListener(connect);
chrome.runtime.onInstalled.addListener(connect);
connect();
