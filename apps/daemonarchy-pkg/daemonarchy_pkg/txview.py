"""What the window shows while a transaction runs, from the helper's output lines.

It feeds the lines to the installer's `progress-model` `Progress`, so a package counts when pkg has
extracted it (distinct names, clamped to the plan), bytes are what pkg's event pipe reported banked
across pkg runs, and rates are measured over real time: the same meanings as the installer's screen.
A removal has no installer equivalent, so its packages are counted here from pkg's own lines.

Counters are measured. The overall percentage and the time left are estimates and say so: the
percentage weighs the download against the install with the proportions of the recorded real
install (`BASELINE`), and the time left needs a measured download rate, and uses the baseline rate
only for the install, which it says. Nothing is shown as known when it is not.
"""
import json
import re
import time

from . import engine

DELETING = re.compile(r'^\[\s*(\d+)/(\d+)\] Deleting files for (\S+?):.*done\s*$')
DEINSTALLING = re.compile(r'^\[\s*(\d+)/(\d+)\] Deinstalling (\S+?)\.*\s*$')


class Transaction:
    def __init__(self, action, clock=time.monotonic):
        self.action, self.clock = action, clock
        model = engine.load('progress-model')
        self.model = model
        self.progress = model.Progress(clock=clock)
        self.started = clock()
        self.state = 'running'
        self.result = None
        self.removed, self.remove_total = set(), 0
        self.removing = ''
        self.phase = 'start'

    def feed(self, line):
        line = line.rstrip('\n')
        if line.startswith('@@result '):
            try:
                self.result = json.loads(line[9:])
            except ValueError:
                self.result = dict(status='failed', detail='the helper wrote an unreadable result')
            self.state = {'ok': 'done', 'refused': 'refused'}.get(self.result.get('status'), 'failed')
            return
        if line.startswith('@@phase '):
            self.phase = line[8:].strip()
        if self.action == 'remove':
            match = DEINSTALLING.match(line)
            if match:
                self.remove_total, self.removing = int(match[2]), match[3]
            match = DELETING.match(line)
            if match:
                self.remove_total = int(match[2])
                self.removed.add(match[3])
            return
        self.progress.line(line)

    def view(self, now=None):
        now = self.clock() if now is None else now
        progress = self.progress
        data = progress.bytes_view(now)
        packages = progress.packages_view()
        if self.action == 'remove':
            packages = dict(done=len(self.removed), total=self.remove_total or None,
                            source='pkg' if self.remove_total else None)
        stages = ['Remove'] if self.action == 'remove' else (['Download', 'Install'] if progress.plan and progress.plan.get('archives') else ['Install'])
        current = {'fetch': 'Download', 'install': 'Remove' if self.action == 'remove' else 'Install'}.get(self.phase, '')
        index = (stages.index(current) + 1) if current in stages else 0
        percent, eta, basis = self.estimate(stages, data, packages, now)
        if self.state == 'done':
            percent, eta = 100.0, None
        return dict(state=self.state, action=self.action, stage=current, stage_index=index, stage_count=len(stages),
                    elapsed=now - self.started, packages=packages, bytes=data, percent=percent, eta=eta,
                    eta_basis=basis, item=progress.item or self.removing, result=self.result,
                    recent=list(progress.recent)[-3:], warning=progress.warning)

    def estimate(self, stages, data, packages, now):
        """(percent, seconds left, basis) as estimates; None where there is nothing to base one on."""
        baseline = self.model.BASELINE
        weights = {'Download': baseline['fetch'], 'Install': baseline['packages'], 'Remove': 1.0}
        planned = sum(weights[s] for s in stages)
        worked = 0.0
        for stage in stages:
            if stage == 'Download':
                fraction = (data['done'] / data['total']) if data['total'] else 0.0
                if self.phase != 'fetch' and self.phase != 'start':
                    fraction = 1.0
            else:
                fraction = (packages['done'] / packages['total']) if packages['total'] else 0.0
            worked += weights[stage] * min(1.0, fraction)
        percent = min(99.0, 100.0 * worked / planned) if planned and self.phase != 'start' else None
        left = None
        basis = None
        if 'Download' in stages and self.phase == 'fetch':
            if data['average'] and data['total']:
                left, basis = max(0.0, (data['total'] - data['done']) / data['average']), 'measured download rate'
        elif self.phase == 'install':
            rate = self.progress.package_average(now) if self.action != 'remove' else None
            if rate and packages['total']:
                left, basis = max(0.0, (packages['total'] - packages['done']) / rate), 'measured install rate'
        if left is not None and self.phase == 'fetch' and packages.get('total'):
            # the install after the download has no rate yet: the recorded install's per-package time stands in, and says so
            left += packages['total'] * baseline['packages'] / 1217
            basis = 'measured download rate; install time from the baseline'
        return percent, left, basis
