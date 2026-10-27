/*
 * Feed terminal output to FreeBSD's own console emulator (sys/teken, the
 * parser vt(4) uses) and print what vt(4) would draw in each cell, using the
 * same 256-to-16 color reduction and bright-color handling as
 * sys/kern/subr_terminal.c and sys/dev/vt/vt_core.c.
 *
 * Build on FreeBSD with the system's source tree:
 *   awk -f /usr/src/sys/teken/gensequences /usr/src/sys/teken/sequences >teken_state.h
 *   cc -I. -I/usr/src/sys/teken -o vt-teken-render vt-teken-render.c /usr/src/sys/teken/teken.c
 * Usage: vt-teken-render ROWS COLS <captured-output
 * Output: one line per row; each cell is "U+XXXX fg bg flags" separated by tabs,
 * where fg/bg are vt palette indexes 0-15 and flags are u (underline) and r (reverse).
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "teken.h"

struct cell {
	teken_char_t	c;
	teken_attr_t	a;
};

static struct cell *grid;
static int rows, cols;

static void bell(void *s) { (void)s; }
static void cursor(void *s, const teken_pos_t *p) { (void)s; (void)p; }
static void param(void *s, int c, unsigned int v) { (void)s; (void)c; (void)v; }
static void respond(void *s, const void *b, size_t l) { (void)s; (void)b; (void)l; }

static void
putchar_(void *s, const teken_pos_t *p, teken_char_t c, const teken_attr_t *a)
{
	(void)s;
	if (p->tp_row < (unsigned)rows && p->tp_col < (unsigned)cols) {
		grid[p->tp_row * cols + p->tp_col].c = c;
		grid[p->tp_row * cols + p->tp_col].a = *a;
	}
}

static void
fill(void *s, const teken_rect_t *r, teken_char_t c, const teken_attr_t *a)
{
	teken_pos_t p;

	for (p.tp_row = r->tr_begin.tp_row; p.tp_row < r->tr_end.tp_row; p.tp_row++)
		for (p.tp_col = r->tr_begin.tp_col; p.tp_col < r->tr_end.tp_col; p.tp_col++)
			putchar_(s, &p, c, a);
}

static void
copy(void *s, const teken_rect_t *r, const teken_pos_t *d)
{
	int height = r->tr_end.tp_row - r->tr_begin.tp_row;
	int width = r->tr_end.tp_col - r->tr_begin.tp_col;
	struct cell *tmp = calloc((size_t)height * width, sizeof(*tmp));
	int y, x;

	(void)s;
	for (y = 0; y < height; y++)
		for (x = 0; x < width; x++)
			tmp[y * width + x] = grid[(r->tr_begin.tp_row + y) * cols + r->tr_begin.tp_col + x];
	for (y = 0; y < height; y++)
		for (x = 0; x < width; x++)
			if (d->tp_row + y < (unsigned)rows && d->tp_col + x < (unsigned)cols)
				grid[(d->tp_row + y) * cols + d->tp_col + x] = tmp[y * width + x];
	free(tmp);
}

static int
to16(teken_color_t c)
{
	return (c >= 16 ? teken_256to16(c) : c);
}

int
main(int argc, char **argv)
{
	teken_funcs_t funcs = { bell, cursor, putchar_, fill, copy, NULL, NULL, param, respond };
	teken_t t;
	teken_pos_t size;
	char buffer[65536];
	size_t n;
	int y, x;

	if (argc != 3)
		return (2);
	rows = atoi(argv[1]);
	cols = atoi(argv[2]);
	grid = calloc((size_t)rows * cols, sizeof(*grid));
	teken_init(&t, &funcs, NULL);
	size.tp_row = rows;
	size.tp_col = cols;
	teken_set_winsize(&t, &size);
	for (y = 0; y < rows * cols; y++) {
		grid[y].c = ' ';
		grid[y].a = *teken_get_defattr(&t);
	}
	while ((n = fread(buffer, 1, sizeof(buffer), stdin)) > 0)
		teken_input(&t, buffer, n);
	for (y = 0; y < rows; y++) {
		for (x = 0; x < cols; x++) {
			const struct cell *c = &grid[y * cols + x];
			int fg = to16(c->a.ta_fgcolor), bg = to16(c->a.ta_bgcolor);
			int format = c->a.ta_format;

			/* vt_determine_colors(): bold lights fg, blink lights bg. */
			if (format & TF_BOLD)
				fg |= 8;
			if (format & TF_BLINK)
				bg |= 8;
			printf("%sU+%04X %d %d %s%s", x ? "\t" : "", (unsigned)c->c, fg, bg,
			    format & TF_UNDERLINE ? "u" : "", format & TF_REVERSE ? "r" : "");
		}
		printf("\n");
	}
	return (0);
}
