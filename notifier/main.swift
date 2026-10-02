// Agent Board app. Two jobs in one app:
//
// 1. The board window: open the app (Desktop icon, Dock, Spotlight) and the board appears in its own
//    window, served by the local board server at http://127.0.0.1:4317. Links to anything else
//    (previews, Jira, GitHub…) open in Chrome, switching to the tab if it's already open.
//
// 2. Notifications, posted by the Claude Code hooks:
//      "Agent Board.app/Contents/MacOS/agent-board-notify" --title T [--subtitle S] [--body B]
//          [--url URL] [--board-url URL] [--id ID] [--sound Glass] [--browser com.google.Chrome]
//    With --board-url the notification also gets a "View on board" button. Clicking a notification
//    opens board links in the window and other links in Chrome.
import Cocoa
import UserNotifications
import WebKit

let boardHome = URL(string: "http://127.0.0.1:4317/")!

func parseArgs() -> [String: String] {
    var out = [String: String]()
    var key: String?
    for a in CommandLine.arguments.dropFirst() {
        if a.hasPrefix("--") { key = String(a.dropFirst(2)); out[key!] = "" }
        else if let k = key { out[k] = a; key = nil }
    }
    return out
}

func isBoard(_ url: URL) -> Bool {
    (url.host == "127.0.0.1" || url.host == "localhost") && url.port == 4317
}

/// Open a non-board link in Chrome: ask the board server to switch to an already-open tab first.
func openOutside(_ url: URL, browser: String = "com.google.Chrome") {
    if url.scheme == "http" || url.scheme == "https", let api = URL(string: "http://127.0.0.1:4317/api/tabs/open") {
        var req = URLRequest(url: api, timeoutInterval: 5)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try? JSONSerialization.data(withJSONObject: ["url": url.absoluteString])
        URLSession.shared.dataTask(with: req) { _, resp, _ in
            if (resp as? HTTPURLResponse)?.statusCode != 200 { DispatchQueue.main.async { plainOpen(url, browser) } }
        }.resume()
    } else {
        plainOpen(url, browser)
    }
}

func plainOpen(_ url: URL, _ browser: String) {
    if !browser.isEmpty, let app = NSWorkspace.shared.urlForApplication(withBundleIdentifier: browser) {
        NSWorkspace.shared.open([url], withApplicationAt: app, configuration: NSWorkspace.OpenConfiguration())
    } else {
        NSWorkspace.shared.open(url)
    }
}

// ---------------- The board window ----------------
final class BoardWindow: NSObject, WKNavigationDelegate, WKUIDelegate, WKScriptMessageHandler, NSWindowDelegate {
    var window: NSWindow?
    var web: WKWebView!
    var retry: Timer?

    func show(_ url: URL = boardHome) {
        NSApp.setActivationPolicy(.regular)
        if window == nil { build() }
        if web.url == nil || web.url?.path != url.path || url.fragment != nil { web.load(URLRequest(url: url)) }
        window?.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    private func build() {
        let config = WKWebViewConfiguration()
        config.preferences.isElementFullscreenEnabled = true
        config.websiteDataStore = .default()
        // Clipboard fallback for the page: window.webkit.messageHandlers.copy.postMessage(text)
        config.userContentController.add(self, name: "copy")
        web = WKWebView(frame: .zero, configuration: config)
        web.navigationDelegate = self
        web.uiDelegate = self
        web.allowsBackForwardNavigationGestures = false
        web.setValue(false, forKey: "drawsBackground")

        let w = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1280, height: 820),
                         styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        w.title = "Agent Board"
        w.minSize = NSSize(width: 380, height: 480)
        w.contentView = web
        w.delegate = self
        w.center()
        w.setFrameAutosaveName("AgentBoardMain")   // remembers size and position
        w.isReleasedWhenClosed = false
        window = w
    }

    func userContentController(_ c: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.name == "copy", let text = message.body as? String else { return }
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(text, forType: .string)
    }

    // Board pages stay in the window; everything else goes to Chrome.
    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = action.request.url else { return decisionHandler(.cancel) }
        if isBoard(url) || url.scheme == "about" || url.scheme == "data" { return decisionHandler(.allow) }
        if action.targetFrame?.isMainFrame ?? true { openOutside(url) }
        decisionHandler(action.targetFrame == nil || action.targetFrame!.isMainFrame ? .cancel : .allow)
    }

    func webView(_ webView: WKWebView, createWebViewWith config: WKWebViewConfiguration,
                 for action: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url = action.request.url {
            if isBoard(url) { webView.load(action.request) } else { openOutside(url) }
        }
        return nil
    }

    // If the board server isn't up yet (e.g. right after login), show a friendly page and keep retrying.
    func webView(_ webView: WKWebView, didFailProvisionalNavigation nav: WKNavigation!, withError error: Error) {
        let html = """
        <html><body style="font:15px -apple-system;display:grid;place-items:center;height:100vh;margin:0;background:#F1F3F8;color:#131827">
        <div style="text-align:center"><div style="font-size:42px">◔</div><h2>Starting Agent Board…</h2>
        <p style="color:#5B6376">Waiting for the board server on this Mac. This page retries by itself.</p></div></body></html>
        """
        webView.loadHTMLString(html, baseURL: nil)
        retry?.invalidate()
        retry = Timer.scheduledTimer(withTimeInterval: 3, repeats: false) { [weak self] _ in self?.web.load(URLRequest(url: boardHome)) }
    }

    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
        let a = NSAlert(); a.messageText = message; a.runModal(); completionHandler()
    }

    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        let a = NSAlert(); a.messageText = message
        a.addButton(withTitle: "OK"); a.addButton(withTitle: "Cancel")
        completionHandler(a.runModal() == .alertFirstButtonReturn)
    }

    func webView(_ webView: WKWebView, didFinish nav: WKNavigation!) {
        FileHandle.standardError.write("loaded \(webView.url?.absoluteString ?? "")\n".data(using: .utf8)!)
    }

    @objc func reload() { web?.reload() }
}

// ---------------- App ----------------
final class AppDelegate: NSObject, NSApplicationDelegate, UNUserNotificationCenterDelegate {
    let args = parseArgs()
    let board = BoardWindow()
    var clickedOutside = false

    func applicationWillFinishLaunching(_ note: Notification) {
        // Must be set before launch finishes so a click that launched us is delivered here.
        UNUserNotificationCenter.current().delegate = self
        let action = UNNotificationAction(identifier: "board", title: "View on board", options: [.foreground])
        UNUserNotificationCenter.current().setNotificationCategories(
            [UNNotificationCategory(identifier: "link", actions: [action], intentIdentifiers: [])])
    }

    func applicationDidFinishLaunching(_ note: Notification) {
        if args["title"] != nil { return post() }
        buildMenu()
        // Opened by you or by a notification click. Give a click a moment to arrive: a click on an
        // outside link (e.g. a preview) only needs Chrome, not the board window.
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) {
            if self.clickedOutside && self.board.window == nil {
                DispatchQueue.main.asyncAfter(deadline: .now() + 1) { NSApp.terminate(nil) }
            } else if self.board.window == nil {
                self.board.show()
            }
        }
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows: Bool) -> Bool {
        board.show(); return true
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { board.window != nil }

    func post() {
        let center = UNUserNotificationCenter.current()
        center.requestAuthorization(options: [.alert, .sound]) { granted, _ in
            guard granted else {
                FileHandle.standardError.write("notifications not allowed for Agent Board\n".data(using: .utf8)!)
                exit(2)
            }
            let c = UNMutableNotificationContent()
            c.title = self.args["title"] ?? ""
            if let s = self.args["subtitle"], !s.isEmpty { c.subtitle = s }
            c.body = self.args["body"] ?? ""
            if let s = self.args["sound"], !s.isEmpty { c.sound = UNNotificationSound(named: UNNotificationSoundName(s + ".aiff")) }
            let boardURL = self.args["board-url"] ?? ""
            c.userInfo = ["url": self.args["url"] ?? "", "board": boardURL, "browser": self.args["browser"] ?? ""]
            if !boardURL.isEmpty { c.categoryIdentifier = "link" }
            // Same id replaces the earlier notification instead of stacking a duplicate.
            let id = self.args["id"].flatMap { $0.isEmpty ? nil : $0 } ?? UUID().uuidString
            center.add(UNNotificationRequest(identifier: id, content: c, trigger: nil)) { err in
                if let err = err { FileHandle.standardError.write("\(err)\n".data(using: .utf8)!); exit(1) }
                DispatchQueue.main.async { NSApp.terminate(nil) }
            }
        }
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification,
                                withCompletionHandler done: @escaping (UNNotificationPresentationOptions) -> Void) {
        done([.banner, .list, .sound])
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse,
                                withCompletionHandler done: @escaping () -> Void) {
        let info = response.notification.request.content.userInfo
        let key = response.actionIdentifier == "board" ? "board" : "url"
        if let s = info[key] as? String, let url = URL(string: s), !s.isEmpty {
            if isBoard(url) {
                board.show(url)
            } else {
                clickedOutside = true
                openOutside(url, browser: (info["browser"] as? String) ?? "com.google.Chrome")
            }
        } else {
            board.show()
        }
        done()
    }

    func buildMenu() {
        let main = NSMenu()
        func sub(_ title: String, _ items: [NSMenuItem]) {
            let top = NSMenuItem(); let m = NSMenu(title: title); items.forEach(m.addItem); top.submenu = m; main.addItem(top)
        }
        func item(_ t: String, _ sel: Selector?, _ key: String, _ mods: NSEvent.ModifierFlags = .command, target: AnyObject? = nil) -> NSMenuItem {
            let i = NSMenuItem(title: t, action: sel, keyEquivalent: key); i.keyEquivalentModifierMask = mods; i.target = target; return i
        }
        sub("Agent Board", [item("Hide Agent Board", #selector(NSApplication.hide(_:)), "h"), .separator(),
                            item("Quit Agent Board", #selector(NSApplication.terminate(_:)), "q")])
        sub("Edit", [item("Undo", Selector(("undo:")), "z"), item("Redo", Selector(("redo:")), "Z"), .separator(),
                     item("Cut", #selector(NSText.cut(_:)), "x"), item("Copy", #selector(NSText.copy(_:)), "c"),
                     item("Paste", #selector(NSText.paste(_:)), "v"), item("Select All", #selector(NSText.selectAll(_:)), "a")])
        sub("View", [item("Reload", #selector(BoardWindow.reload), "r", target: board),
                     item("Enter Full Screen", #selector(NSWindow.toggleFullScreen(_:)), "f", [.command, .control])])
        sub("Window", [item("Minimize", #selector(NSWindow.performMiniaturize(_:)), "m"),
                       item("Close", #selector(NSWindow.performClose(_:)), "w")])
        NSApp.mainMenu = main
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.accessory)
app.run()
