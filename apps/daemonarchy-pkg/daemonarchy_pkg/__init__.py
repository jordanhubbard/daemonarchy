"""daemonarchy-pkg: the graphical package manager's toolkit-free layers.

  repos       the configured repositories and whether each one is signed
  catalogue   the packages in those repositories and on the system, searchable at keystroke speed
  plan        a dry run turned into a plan with an identity, shared with the installer's engine
  engine      loads the installer's parallel-fetch and progress-model so the plan, the events and the
              counters mean the same thing here as in the installer

Nothing in this package imports a GUI toolkit; the window is in window.py.
"""
API = 1
