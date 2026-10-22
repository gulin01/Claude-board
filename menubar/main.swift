// Agent Board menu-bar buddy: a tiny character next to the clock.
// Amber and waving = an agent needs you; blue and bobbing = agents working; grey = all quiet.
// The number is how many agents need you (or, if none, how many are working).
// Click for the list; each agent opens its card on the board.
import Cocoa

struct Item: Decodable { let id: String; let title: String; let project: String }
struct Plan: Decodable { let account: String; let five: Int?; let week: Int? }
struct Space: Decodable { let space: String; let auto: String; let manual: Bool; let until: Double }
struct Summary: Decodable { let need: [Item]; let work: [Item]; let done: Int; let tired: Int; let asleep: Int; let plan: [Plan]; let space: Space; let labels: [String: String]? }

let board = "http://127.0.0.1:4317/"

final class App: NSObject, NSApplicationDelegate, NSMenuDelegate {
    var item: NSStatusItem!
    var summary: Summary?
    var labels: [String: String] = [:]   // in the board's language (English / 한국어), kept while offline

    /// Label from the board, with {n} filled in; English fallback.
    func L(_ key: String, _ fallback: String, n: Int? = nil) -> String {
        var s = labels[key] ?? fallback
        if let n = n { s = s.replacingOccurrences(of: "{n}", with: String(n)) }
        return s
    }
    var offline = false
    var frame = 0

    func applicationDidFinishLaunching(_ note: Notification) {
        item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        item.button?.imagePosition = .imageLeft
        item.button?.font = NSFont.monospacedDigitSystemFont(ofSize: 12, weight: .semibold)
        let menu = NSMenu()
        menu.delegate = self
        item.menu = menu
        poll()
        Timer.scheduledTimer(withTimeInterval: 6, repeats: true) { [weak self] _ in self?.poll() }
        Timer.scheduledTimer(withTimeInterval: 0.45, repeats: true) { [weak self] _ in self?.tick() }
    }

    func poll() {
        guard let url = URL(string: board + "api/summary") else { return }
        var req = URLRequest(url: url, timeoutInterval: 5)
        req.cachePolicy = .reloadIgnoringLocalCacheData
        URLSession.shared.dataTask(with: req) { data, _, _ in
            let s = data.flatMap { try? JSONDecoder().decode(Summary.self, from: $0) }
            DispatchQueue.main.async {
                self.offline = (s == nil)
                if let s = s { self.summary = s; if let l = s.labels { self.labels = l } }
                self.redraw()
            }
        }.resume()
    }

    // Only animate when something is happening, so an idle Mac stays idle.
    func tick() {
        guard let s = summary, !offline, !(s.need.isEmpty && s.work.isEmpty) else { return }
        frame ^= 1
        redraw()
    }

    enum Mood { case need, work, quiet, offline }
    var mood: Mood {
        guard let s = summary, !offline else { return .offline }
        return !s.need.isEmpty ? .need : !s.work.isEmpty ? .work : .quiet
    }

    func redraw() {
        let m = mood
        item.button?.image = buddy(m, frame: frame)
        switch m {
        case .need: item.button?.title = " \(summary!.need.count)"
        case .work: item.button?.title = " \(summary!.work.count)"
        default: item.button?.title = ""
        }
        item.button?.toolTip = m == .offline ? L("not_running", "Agent Board isn't running") : "Agent Board"
    }

    func buddy(_ m: Mood, frame: Int) -> NSImage {
        let img = NSImage(size: NSSize(width: 20, height: 18), flipped: false) { _ in
            let color: NSColor
            switch m {
            case .need: color = NSColor(red: 1.0, green: 0.60, blue: 0.12, alpha: 1)
            case .work: color = NSColor(red: 0.18, green: 0.55, blue: 1.0, alpha: 1)
            case .quiet: color = NSColor(red: 0.14, green: 0.75, blue: 0.69, alpha: 1)
            case .offline: color = NSColor.secondaryLabelColor
            }
            let bob: CGFloat = (m == .work && frame == 1) ? 1.5 : 0
            let body = NSRect(x: 2, y: 1 + bob, width: 14, height: 13)
            color.setFill()
            NSBezierPath(ovalIn: body).fill()
            // Eyes: closed lines when quiet/offline, open otherwise.
            for dx: CGFloat in [5.2, 10.2] {
                if m == .quiet || m == .offline {
                    NSColor.white.setFill()
                    NSBezierPath(roundedRect: NSRect(x: dx - 0.6, y: 7 + bob, width: 3.4, height: 1.2), xRadius: 0.6, yRadius: 0.6).fill()
                } else {
                    NSColor.white.setFill()
                    NSBezierPath(ovalIn: NSRect(x: dx - 0.5, y: 6 + bob, width: 3.2, height: 3.8)).fill()
                    NSColor.black.setFill()
                    NSBezierPath(ovalIn: NSRect(x: dx + 0.4, y: 6.6 + bob, width: 1.6, height: 1.8)).fill()
                }
            }
            // Waving arm when someone needs you.
            if m == .need {
                color.setFill()
                let arm = NSBezierPath(roundedRect: NSRect(x: 14.5, y: 9, width: 3, height: 7), xRadius: 1.5, yRadius: 1.5)
                var t = AffineTransform(translationByX: 16, byY: 9)
                t.rotate(byDegrees: frame == 1 ? -25 : 10)
                t.translate(x: -16, y: -9)
                arm.transform(using: t)
                arm.fill()
            }
            return true
        }
        img.isTemplate = false
        return img
    }

    // Build the menu fresh each time it opens.
    func menuNeedsUpdate(_ menu: NSMenu) {
        menu.removeAllItems()
        guard let s = summary, !offline else {
            menu.addItem(disabled(L("not_running", "Agent Board isn't running")))
            menu.addItem(.separator())
            menu.addItem(action(L("quit", "Quit"), #selector(quit), key: "q"))
            return
        }
        func section(_ title: String, _ items: [Item]) {
            guard !items.isEmpty else { return }
            menu.addItem(disabled(title))
            for i in items.prefix(8) {
                let mi = action("  \(i.title)", #selector(openAgent(_:)))
                mi.representedObject = i.id
                mi.toolTip = i.project
                menu.addItem(mi)
            }
            menu.addItem(.separator())
        }
        // Only the current space is listed; the other one never shows here.
        let personal = s.space.space == "personal"
        menu.addItem(disabled(personal ? L("personal_space", "Personal space") : L("work_space", "Work space")))
        let sw = action(personal ? L("switch_to_work", "Switch to Work") : L("switch_to_personal", "Switch to Personal"), #selector(toggleSpace))
        sw.representedObject = personal ? (s.space.auto == "work" ? "auto" : "work") : (s.space.auto == "personal" ? "auto" : "personal")
        menu.addItem(sw)
        menu.addItem(.separator())
        section("● \(L("needs_you_list", "Needs you")) (\(s.need.count))", s.need)
        section("● \(L("working_list", "Working")) (\(s.work.count))", s.work)
        var line = [String]()
        if s.done > 0 { line.append("✓ " + L("n_done", "{n} done", n: s.done)) }
        if s.tired > 0 { line.append(L("n_restart", "{n} to restart", n: s.tired)) }
        if s.asleep > 0 { line.append(L("n_asleep", "{n} asleep", n: s.asleep)) }
        if !line.isEmpty { menu.addItem(disabled(line.joined(separator: " · "))) }
        for p in s.plan {
            let who = p.account.split(separator: "@").first.map(String.init) ?? p.account
            menu.addItem(disabled("\(who): \(L("five_hour", "5h")) \(p.five.map { "\($0)%" } ?? "–") · \(L("week", "week")) \(p.week.map { "\($0)%" } ?? "–")"))
        }
        menu.addItem(.separator())
        menu.addItem(action(L("open_board", "Open Agent Board"), #selector(openBoard), key: "o"))
        menu.addItem(action(L("quit", "Quit"), #selector(quit), key: "q"))
    }

    func disabled(_ t: String) -> NSMenuItem { let m = NSMenuItem(title: t, action: nil, keyEquivalent: ""); m.isEnabled = false; return m }
    func action(_ t: String, _ sel: Selector, key: String = "") -> NSMenuItem {
        let m = NSMenuItem(title: t, action: sel, keyEquivalent: key); m.target = self; return m
    }
    func open(_ s: String) {
        guard let url = URL(string: s) else { return }
        if let chrome = NSWorkspace.shared.urlForApplication(withBundleIdentifier: "com.google.Chrome") {
            NSWorkspace.shared.open([url], withApplicationAt: chrome, configuration: NSWorkspace.OpenConfiguration())
        } else {
            NSWorkspace.shared.open(url)
        }
    }
    @objc func openAgent(_ sender: NSMenuItem) { open(board + "#s=" + (sender.representedObject as? String ?? "")) }
    @objc func openBoard() { open(board) }
    @objc func toggleSpace(_ sender: NSMenuItem) {
        guard let url = URL(string: board + "api/space"), let space = sender.representedObject as? String else { return }
        var req = URLRequest(url: url, timeoutInterval: 5)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try? JSONSerialization.data(withJSONObject: ["space": space])
        URLSession.shared.dataTask(with: req) { _, _, _ in DispatchQueue.main.async { self.poll() } }.resume()
    }
    @objc func quit() { NSApp.terminate(nil) }
}

let app = NSApplication.shared
let delegate = App()
app.delegate = delegate
app.setActivationPolicy(.accessory)
app.run()
