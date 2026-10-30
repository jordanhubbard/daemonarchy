"""The few terminal control sequences a host may need outside a Screen: clear, move, cursor, reset.

Hosts should draw through `Screen`; these exist for the moments around it (put the cursor back after a
celebration, restore a terminal a shell script left in a state). Positions are 0-based columns and rows.
"""

RESET = "\033[0m"


def clear():
    """Clear the screen and home the cursor."""
    return "\033[H\033[2J"


def move(x, y):
    return f"\033[{int(y) + 1};{int(x) + 1}H"


def cursor(visible):
    return "\033[?25h" if visible else "\033[?25l"


def title(text):
    """Set the terminal (or tmux pane) title; control characters are removed."""
    return "\033]2;" + "".join(c for c in str(text) if c.isprintable())[:80] + "\033\\"


def restore():
    """Attributes reset, screen cleared, cursor shown: the state a shell prompt expects."""
    return RESET + clear() + cursor(True)
