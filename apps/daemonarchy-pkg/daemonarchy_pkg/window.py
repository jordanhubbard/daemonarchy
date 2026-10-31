"""The GTK 4 window. It draws what viewmodel.py decides and calls it; it holds no package logic.

Everything slow runs off the main loop: the catalogue is read, the upgrade check and every plan are
asked for, and the helper's output is read, on worker threads that hand results back with
GLib.idle_add. A search is a substring scan of one in-memory list and runs on the main loop.
"""
import threading
import time

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

from . import catalogue as catalogue_module, plan as plan_module, repos as repos_module, theme, transaction, viewmodel  # noqa: E402

VIEW_TITLES = (('browse', 'Browse'), ('installed', 'Installed'), ('updates', 'Updates'), ('repositories', 'Repositories'))
HELPER_REFRESH_TIMEOUT = 600


def label(text='', css=(), wrap=False, ellipsize=False, selectable=False):
    widget = Gtk.Label(label=text, xalign=0, wrap=wrap, selectable=selectable)
    if ellipsize:
        widget.set_ellipsize(Pango.EllipsizeMode.END)
    for name in css:
        widget.add_css_class(name)
    return widget


def chip(kind, text=None):
    widget = label(text or theme.LABEL.get(kind, kind), css=('chip', f'chip-{kind}'))
    widget.set_valign(Gtk.Align.CENTER)
    return widget


CHUNK = 25      # rows built per slice: the first slice is on screen within a frame or two of a keystroke


def clear(container):
    if hasattr(container, 'remove_all'):        # Gtk.ListBox, GTK 4.12 and later: one call instead of one per row
        container.remove_all()
        return
    child = container.get_first_child()
    while child is not None:
        following = child.get_next_sibling()
        container.remove(child)
        child = following


def run_on_main(function, *args):
    GLib.idle_add(lambda: (function(*args), GLib.SOURCE_REMOVE)[1])


def in_thread(work, done):
    """Run work() off the main loop, then done(result) on it; an exception becomes done(exception)."""
    def target():
        try:
            outcome = work()
        except Exception as problem:  # noqa: BLE001 - the window must show it, not die
            outcome = problem
        run_on_main(done, outcome)
    threading.Thread(target=target, daemon=True).start()


class Window(Gtk.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application, title='Packages', default_width=1100, default_height=720)
        self.add_css_class('daemonarchy-pkg')
        self.browser, self.repositories, self.catalogue = None, [], None
        self.view, self.query, self.session, self.refreshing = 'browse', '', None, False
        self.generation = 0
        self.animations = Gtk.Settings.get_default().props.gtk_enable_animations
        self.reduced = theme.reduced_motion(self.animations)

        self.search = Gtk.SearchEntry(placeholder_text='Search packages', hexpand=True)
        self.search.connect('search-changed', self.on_search)
        self.refresh_button = Gtk.Button(label='Refresh')
        self.refresh_button.set_tooltip_text('Fetch the newest package lists')
        self.refresh_button.connect('clicked', lambda _b: self.refresh())
        header = Gtk.HeaderBar()
        header.set_title_widget(self.search)
        header.pack_end(self.refresh_button)
        self.set_titlebar(header)

        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.sidebar = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.sidebar.add_css_class('sidebar')
        self.sidebar.set_size_request(190, -1)
        self.sidebar_labels = {}
        for key, text in VIEW_TITLES:
            row = Gtk.ListBoxRow()
            row.view = key
            box = Gtk.Box(spacing=8)
            name = label(text)
            name.set_hexpand(True)
            count = label('', css=('hint',))
            self.sidebar_labels[key] = count
            box.append(name)
            box.append(count)
            row.set_child(box)
            self.sidebar.append(row)
        self.sidebar.connect('row-selected', self.on_view)
        root.append(self.sidebar)

        self.stack = Gtk.Stack(hexpand=True, vexpand=True)
        root.append(self.stack)
        self.set_child(root)
        self.stack.add_named(self.build_browse(), 'browse')
        self.repo_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.stack.add_named(Gtk.ScrolledWindow(child=self.repo_list), 'repositories')
        self.transaction_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=24, margin_bottom=24,
                                       margin_start=32, margin_end=32)
        self.stack.add_named(Gtk.ScrolledWindow(child=self.transaction_box), 'transaction')
        self.sidebar.select_row(self.sidebar.get_row_at_index(0))

        search_action = Gio.SimpleAction.new('search', None)
        search_action.connect('activate', lambda *_: self.search.grab_focus())
        self.add_action(search_action)
        application.set_accels_for_action('win.search', ['<Primary>f'])
        self.load()

    # ---- layout
    def build_browse(self):
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, position=620, wide_handle=True)
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.results = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.results.connect('row-selected', self.on_row)
        left.append(Gtk.ScrolledWindow(child=self.results, vexpand=True))
        self.status = label('Loading the package catalogue…', css=('hint',))
        self.status.set_margin_start(12)
        self.status.set_margin_top(6)
        self.status.set_margin_bottom(6)
        left.append(self.status)
        paned.set_start_child(left)
        self.detail = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.detail.add_css_class('detail')
        paned.set_end_child(Gtk.ScrolledWindow(child=self.detail))
        self.update_all = Gtk.Button(label='Update everything')
        self.update_all.add_css_class('primary')
        self.update_all.connect('clicked', lambda _b: self.start('upgrade', []))
        self.update_all.set_visible(False)
        left.prepend(self.update_all)
        self.cleanup = Gtk.Button(label='Remove unused dependencies…')
        self.cleanup.set_tooltip_text('Packages that were installed only because something needed them, and nothing needs now')
        self.cleanup.connect('clicked', lambda _b: self.start('autoremove', []))
        self.cleanup.set_visible(False)
        left.prepend(self.cleanup)
        return paned

    # ---- loading
    def load(self):
        self.status.set_text('Loading the package catalogue…')

        def work():
            repositories = repos_module.read(repos_module.configured_dirs())
            catalogue = catalogue_module.Catalogue.load()
            return repositories, catalogue
        in_thread(work, self.loaded)

    def loaded(self, outcome):
        if isinstance(outcome, Exception):
            self.status.set_text(f'The package catalogue could not be read: {outcome}')
            return
        self.repositories, self.catalogue = outcome
        self.browser = viewmodel.Browser(self.catalogue, self.repositories, self.browser.upgrades if self.browser else ())
        for path, message in self.catalogue.problems:
            self.status.set_text(f'{path}: {message}')
        self.show_rows()
        self.show_repositories()
        self.check_upgrades()

    def check_upgrades(self):
        catalogue, repositories = self.catalogue, self.repositories
        in_thread(lambda: plan_module.dry_run('upgrade', [], catalogue, repositories), self.upgrades_known)

    def upgrades_known(self, outcome):
        if isinstance(outcome, Exception) or self.browser is None:
            return
        names = {i.name for i in outcome.items if i.kind in ('upgrade', 'reinstall', 'downgrade')}
        self.browser.upgrades = names
        self.show_rows()

    # ---- views
    def on_view(self, _box, row):
        if row is None:
            return
        self.view = row.view
        if self.view == 'repositories':
            self.stack.set_visible_child_name('repositories')
        elif self.session is None:
            self.stack.set_visible_child_name('browse')
            self.show_rows()

    def on_search(self, entry):
        self.query = entry.get_text()
        if self.view == 'repositories':
            self.sidebar.select_row(self.sidebar.get_row_at_index(0))
        elif self.session is None:
            self.show_rows()

    def show_rows(self):
        if self.browser is None:
            return
        started = time.perf_counter()
        rows, total = self.browser.rows(self.view if self.view != 'repositories' else 'browse', self.query)
        clear(self.results)
        self.fill(list(rows))
        shown = len(rows)
        took = (time.perf_counter() - started) * 1000
        self.status.set_text((f'{total:,} packages' if shown == total else f'Showing {shown:,} of {total:,} packages')
                             + f' · first rows in {took:.0f} ms')
        updates = len(self.browser.upgrades)
        self.sidebar_labels['updates'].set_text(str(updates) if updates else '')
        self.sidebar_labels['installed'].set_text(f'{len(self.catalogue.installed()):,}')
        self.update_all.set_visible(self.view == 'updates' and bool(updates))
        self.cleanup.set_visible(self.view == 'installed')
        if not shown:
            self.show_detail(None)

    def fill(self, pending):
        """Build the result rows a slice at a time: the first slice now, the rest when the main loop is idle,
        dropped if another search starts first, so typing is never held up by drawing rows nobody will see."""
        self.generation += 1
        generation = self.generation

        def slice_of_rows():
            if generation != self.generation:
                return GLib.SOURCE_REMOVE
            for row in pending[:CHUNK]:
                self.results.append(self.result_row(row))
            del pending[:CHUNK]
            return GLib.SOURCE_CONTINUE if pending else GLib.SOURCE_REMOVE
        if slice_of_rows() == GLib.SOURCE_CONTINUE:
            GLib.idle_add(slice_of_rows)

    def result_row(self, row):
        box = Gtk.Box(spacing=10)
        box.add_css_class('result-row')
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        text.append(label(row.name, css=('name',)))
        text.append(label(row.comment, css=('comment',), ellipsize=True))
        box.append(text)
        if row.trust and row.trust != 'signed':
            box.append(chip(row.trust))
        box.append(label(row.version, css=('hint',)))
        box.append(chip(row.badge))
        container = Gtk.ListBoxRow()
        container.package = row.name
        container.set_child(box)
        return container

    def on_row(self, _box, row):
        self.show_detail(self.browser.detail(row.package) if row is not None and self.browser else None)

    def show_detail(self, detail):
        clear(self.detail)
        if detail is None:
            self.detail.append(label('Select a package to see its details.', css=('hint',)))
            return
        self.detail.append(label(detail.name, css=('name',)))
        self.detail.append(label(detail.comment, wrap=True))
        facts = [('Category', detail.category), ('Installed', detail.installed or 'no'), ('Available', detail.version),
                 ('Download', plan_module.size_text(detail.download_bytes) if detail.download_bytes else ''),
                 ('Installed size', plan_module.size_text(detail.installed_bytes) if detail.installed_bytes else ''),
                 ('Maintainer', detail.maintainer), ('Website', detail.www)]
        for key, value in facts:
            if value:
                line = Gtk.Box(spacing=8)
                line.append(label(key, css=('hint',)))
                line.append(label(value, selectable=True, wrap=True))
                self.detail.append(line)
        if detail.offers:
            self.detail.append(label('Repositories', css=('hint',)))
            for repo, version, trust in detail.offers:
                line = Gtk.Box(spacing=8)
                line.append(label(f'{repo} {version}'))
                line.append(chip(trust if trust in theme.TRUST else 'unsigned', theme.LABEL.get(trust, 'Unknown')))
                self.detail.append(line)
        if detail.unavailable:
            self.detail.append(label(detail.unavailable, css=('warning',), wrap=True))
        buttons = Gtk.Box(spacing=8)
        buttons.set_margin_top(12)
        for action in detail.actions:
            button = Gtk.Button(label=theme.LABEL[action])
            button.add_css_class('danger' if action in plan_module.REMOVALS else 'primary')
            button.connect('clicked', lambda _b, a=action, n=detail.name: self.start(a, [n]))
            buttons.append(button)
        self.detail.append(buttons)

    def show_repositories(self):
        clear(self.repo_list)
        for r in self.browser.repositories:
            box = Gtk.Box(spacing=10)
            box.add_css_class('result-row')
            text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
            text.append(label(r.name + ('' if r.enabled else '  (off)'), css=('name',)))
            text.append(label(r.url, css=('comment',), ellipsize=True))
            if r.fingerprint:
                text.append(label(f'key {r.fingerprint[:16]}', css=('hint',)))
            if r.problem:
                text.append(label(r.problem, css=('warning',)))
            box.append(text)
            box.append(label(f'priority {r.priority}', css=('hint',)))
            box.append(chip(r.trust))
            self.repo_list.append(box)

    # ---- a change to the system
    def start(self, action, names):
        if self.session is not None or self.refreshing:
            return
        catalogue, repositories = self.catalogue, self.repositories
        self.session = viewmodel.Session(action, names, lambda a, n: plan_module.dry_run(a, n, catalogue, repositories))
        self.stack.set_visible_child_name('transaction')
        self.render()
        in_thread(self.session.make_plan, lambda _r: self.render())

    def render(self):
        """Draw the session's current state; called when it changes and while it runs."""
        session = self.session
        clear(self.transaction_box)
        if session is None:
            return
        box = self.transaction_box
        box.append(label(viewmodel.title(session.action, session.names or ['everything']), css=('name',)))
        getattr(self, f'render_{session.state}')(session, box)

    def buttons(self, *pairs):
        row = Gtk.Box(spacing=8)
        row.set_margin_top(12)
        for text, css, handler in pairs:
            button = Gtk.Button(label=text)
            if css:
                button.add_css_class(css)
            button.connect('clicked', lambda _b, h=handler: h())
            row.append(button)
        self.transaction_box.append(row)
        return row

    def render_planning(self, session, box):
        box.append(label('Asking pkg what this would change…', css=('hint',)))
        if not self.reduced:
            box.append(Gtk.Spinner(spinning=True))

    def render_error(self, session, box):
        box.append(label(session.error, css=('error',), wrap=True))
        self.buttons(('Back', None, self.close_session))

    def render_review(self, session, box):
        plan = session.plan
        counts = ', '.join(f'{n} to {k}' for k, n in plan.counts().items())
        box.append(label(counts, css=('hint',)))
        listing = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        for item in plan.items:
            line = Gtk.Box(spacing=10)
            line.add_css_class('result-row')
            line.append(chip(item.kind))
            line.append(label(item.name, css=('name',)))
            line.append(label((f'{item.previous} → ' if item.previous else '') + item.version, css=('hint',)))
            spacer = Gtk.Box(hexpand=True)
            line.append(spacer)
            if item.repo:
                line.append(label(item.repo, css=('hint',)))
            listing.append(line)
        scroller = Gtk.ScrolledWindow(child=listing, min_content_height=200, vexpand=True)
        box.append(scroller)
        facts = []
        if plan.to_fetch():
            facts.append(f'Download {plan_module.size_text(plan.download_bytes)}')
        change = plan.installed_bytes
        facts.append(('Uses ' if change >= 0 else 'Frees ') + plan_module.size_text(abs(change)) + ' of disk')
        box.append(label(' · '.join(facts) + (' (sizes approximate)' if plan.approximate else ''), css=('hint',)))
        box.append(label(f'Plan {plan.identity[:12]}: what is run is exactly this plan, or nothing.', css=('hint',)))
        for repo, why in plan.untrusted:
            check = Gtk.CheckButton(label=f'Allow packages from {repo} ({why})')
            check.add_css_class('warning')
            check.set_active(repo in session.allowed)
            check.connect('toggled', lambda b, r=repo: self.allow(r, b.get_active()))
            box.append(check)
        approve = self.buttons(('Cancel', None, self.close_session),
                               (theme.LABEL[session.action] + (f' {len(plan.items)} packages' if len(plan.items) > 1 else ''),
                                'danger' if session.action in plan_module.REMOVALS else 'primary', self.approve))
        self.approve_button = approve.get_last_child()
        self.approve_button.set_sensitive(session.can_approve())

    def allow(self, repo, yes):
        self.session.allow(repo, yes)
        self.approve_button.set_sensitive(self.session.can_approve())

    def approve(self):
        if self.session.approve():
            self.render()
            self.watch()
        else:
            self.render()

    def watch(self):
        """Redraw the running transaction several times a second until it ends."""
        def tick():
            if self.session is None or self.session.state != 'running':
                self.render()
                return GLib.SOURCE_REMOVE
            self.render_progress_only()
            return GLib.SOURCE_CONTINUE
        GLib.timeout_add(250, tick)

    def render_running(self, session, box):
        view = session.view()
        self.progress_widgets = {}
        stage = view['stage'] or 'Starting'
        box.append(label(f"Step {max(view['stage_index'], 1)} of {view['stage_count']} · {stage}", css=('hint',)))
        for key in ('download', 'install'):
            bar = Gtk.ProgressBar(show_text=True)
            self.progress_widgets[key] = bar
            if key == 'download' and not (view['bytes']['total'] or session.plan.to_fetch()):
                continue
            box.append(label('Download' if key == 'download' else ('Remove' if session.action in plan_module.REMOVALS else 'Install'), css=('hint',)))
            box.append(bar)
        self.progress_widgets['overall'] = label('', css=('hint',))
        self.progress_widgets['eta'] = label('', css=('hint',), wrap=True)
        self.progress_widgets['latest'] = label('', css=('log',), ellipsize=True)
        for key in ('overall', 'eta', 'latest'):
            box.append(self.progress_widgets[key])
        self.progress_box = self.buttons(('Cancel', None, self.cancel))
        self.cancel_button = self.progress_box.get_first_child()
        self.render_progress_only()

    def render_progress_only(self):
        session = self.session
        if session is None or session.tx is None or not hasattr(self, 'progress_widgets'):
            return
        view, widgets = session.view(), self.progress_widgets
        data, packages = view['bytes'], view['packages']
        if data['total']:
            widgets['download'].set_fraction(min(1.0, data['done'] / data['total']))
            speed = f" · {transaction_rate(data['rate'])}" if data['rate'] else ''
            widgets['download'].set_text(f"{plan_module.size_text(data['done'])} of {plan_module.size_text(data['total'])}{speed}")
        if packages['total']:
            widgets['install'].set_fraction(min(1.0, packages['done'] / packages['total']))
            widgets['install'].set_text(f"{packages['done']} of {packages['total']} packages")
        if view['percent'] is not None:
            widgets['overall'].set_text(f"About {view['percent']:.0f}% done (an estimate)")
        if view['eta'] is not None:
            widgets['eta'].set_text(f"About {fmt_time(view['eta'])} left: an estimate from {view['eta_basis']}")
        else:
            widgets['eta'].set_text('Estimating the time left once there is a measured rate…')
        widgets['latest'].set_text(view['item'] or (view['recent'][-1] if view['recent'] else ''))
        self.cancel_button.set_visible(session.can_cancel())     # once pkg is installing, stopping it is not safe

    def cancel(self):
        if self.session and self.session.cancel():
            self.render()

    def render_cancelled(self, session, box):
        box.append(label('Cancelled during the download. Nothing was installed or removed.', css=('ok',), wrap=True))
        self.buttons(('Close', None, self.close_session))

    def render_done(self, session, box):
        box.append(label('Done', css=('name', 'ok')))
        changed = (session.tx.result or {}).get('changed', {})
        box.append(label(', '.join(f'{n} {k}' for k, n in changed.items()) or 'Finished.', css=('hint',)))
        pairs = [('Close', 'primary', lambda: self.close_session(reload=True))]
        if session.action == 'remove':
            # A removal leaves what only it needed: offer pkg's own list of those, reviewed like any other change.
            pairs.insert(0, ('Remove unused dependencies…', None, self.cleanup_after))
        self.buttons(*pairs)

    def cleanup_after(self):
        self.close_session()
        self.start('autoremove', [])

    def render_failed(self, session, box):
        detail = (session.tx.result or {}).get('detail') if session.tx and session.tx.result else session.error
        box.append(label('It did not finish', css=('name', 'error')))
        box.append(label(detail or session.error or 'pkg reported an error.', css=('error',), wrap=True))
        box.append(label('\n'.join(session.lines[-6:]), css=('log',), wrap=True))
        box.append(label('pkg may have changed some packages before it stopped; Retry plans again from what is installed now.',
                         css=('hint',), wrap=True))
        self.buttons(('Close', None, lambda: self.close_session(reload=True)), ('Retry', 'primary', self.retry))

    def render_refused(self, session, box):
        result = session.tx.result or {}
        reasons = {'plan-changed': 'The package catalogue changed after you reviewed this plan, so nothing was run. '
                                   'Review the new plan.',
                   'unsigned-repository': 'A repository without a verified signature was not allowed, so nothing was run.',
                   'nothing-to-do': 'pkg has nothing to change.'}
        box.append(label('Nothing was changed', css=('name', 'warning')))
        box.append(label(reasons.get(result.get('reason'), result.get('detail', '')), wrap=True))
        self.buttons(('Close', None, self.close_session), ('Review again', 'primary', self.retry))

    def retry(self):
        session = self.session
        session.state = 'planning'
        self.render()
        in_thread(session.retry, lambda _state: self.render())

    def close_session(self, reload=False):
        self.session = None
        self.stack.set_visible_child_name('repositories' if self.view == 'repositories' else 'browse')
        if reload:
            self.load()
        else:
            self.show_rows()

    # ---- refresh
    def refresh(self):
        if self.refreshing or self.session is not None:
            return
        argv = transaction.elevate([transaction.helper_path(), 'refresh'])
        if argv is None:
            self.status.set_text('Administrator rights are needed to refresh, and sudo is not available.')
            return
        self.refreshing = True
        self.refresh_button.set_sensitive(False)
        self.status.set_text('Refreshing the package lists…')
        lines = []

        def finished(code):
            ok = any('"status":"ok"' in l for l in lines)
            run_on_main(self.refreshed, ok, code, lines[-1] if lines else '')
        viewmodel.launch(argv, lines.append, finished)

    def refreshed(self, ok, code, last):
        self.refreshing = False
        self.refresh_button.set_sensitive(True)
        if ok:
            self.load()
        else:
            self.status.set_text(f'Refreshing did not finish (exit {code}): {last}')


def transaction_rate(value):
    return f'{value / (1 << 20):.1f} MiB/s' if value >= (1 << 20) else f'{value / 1024:.0f} KiB/s'


def fmt_time(seconds):
    seconds = int(seconds)
    if seconds >= 3600:
        return f'{seconds // 3600}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}'
    return f'{seconds // 60}:{seconds % 60:02d}'


def install_css():
    provider = Gtk.CssProvider()
    try:
        provider.load_from_string(theme.css())
    except AttributeError:                      # GTK before 4.12
        provider.load_from_data(theme.css().encode())
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


class Application(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='org.daemonarchy.Pkg')

    def do_activate(self):
        install_css()
        window = self.props.active_window or Window(self)
        window.present()


def main():
    return Application().run([])
