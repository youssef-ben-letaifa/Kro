"""Centralized plot export and transfer helpers for Kronos.

All kernel-side Python code strings for exporting matplotlib figures are
defined here, along with manifest parsing utilities.  This keeps the
heavyweight code-generation out of :mod:`kronos.ui.mainwindow`.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)


# ── Kernel-side code builders ──────────────────────────────────────


def build_plot_export_all_code(manifest_path: str | Path, plots_dir: str | Path) -> str:
    """Return Python code that exports all matplotlib figures to disk.

    The code writes a JSON manifest at *manifest_path* listing every
    exported PNG.
    """
    manifest_path = str(manifest_path)
    plots_dir = str(plots_dir)
    return (
        "import json as __json\n"
        "import traceback as __traceback\n"
        "from pathlib import Path as __Path\n"
        "from matplotlib import pyplot as __plt\n"
        "from matplotlib.figure import Figure as __Figure\n"
        "try:\n"
        "    __ip = get_ipython()\n"
        "    __ns = __ip.user_ns if __ip else globals()\n"
        "except Exception:\n"
        "    __ns = globals()\n"
        f"__dir = __Path({plots_dir!r})\n"
        f"__out = __Path({manifest_path!r})\n"
        "__payload = {'ok': True, 'figures': []}\n"
        "try:\n"
        "    __dir.mkdir(parents=True, exist_ok=True)\n"
        "    for __old in __dir.glob('*.png'):\n"
        "        try:\n"
        "            __old.unlink()\n"
        "        except Exception:\n"
        "            pass\n"
        "    __seen = set()\n"
        "    __idx = [0]\n"
        "    def __title_for_fig(__fig, __fallback):\n"
        "        __title = ''\n"
        "        if getattr(__fig, '_suptitle', None) is not None:\n"
        "            __title = __fig._suptitle.get_text()\n"
        "        if not __title and len(__fig.axes) == 1:\n"
        "            __title = __fig.axes[0].get_title() or ''\n"
        "        if not __title:\n"
        "            __title = __fallback\n"
        "        return __title or 'Figure'\n"
        "    def __add_fig(__fig, __fallback, __num, __var):\n"
        "        __path = __dir / f'fig_{__idx[0]}.png'\n"
        "        __idx[0] += 1\n"
        "        __fig.savefig(__path, dpi=90, facecolor=__fig.get_facecolor())\n"
        "        __axes = []\n"
        "        for __ax in __fig.axes:\n"
        "            __pos = __ax.get_position()\n"
        "            __axes.append({\n"
        "                'index': len(__axes),\n"
        "                'title': __ax.get_title(),\n"
        "                'bbox': [float(__pos.x0), float(__pos.y0), float(__pos.x1), float(__pos.y1)],\n"
        "            })\n"
        "        __payload['figures'].append({\n"
        "            'title': __title_for_fig(__fig, __fallback),\n"
        "            'png': str(__path),\n"
        "            'axes': __axes,\n"
        "            'num': __num,\n"
        "            'var': __var,\n"
        "        })\n"
        "    for __num in __plt.get_fignums():\n"
        "        __fig = __plt.figure(__num)\n"
        "        __seen.add(id(__fig))\n"
        "        __add_fig(__fig, f'Figure {__num}', __num, None)\n"
        "    for __name, __val in __ns.items():\n"
        "        if isinstance(__val, __Figure) and id(__val) not in __seen:\n"
        "            __seen.add(id(__val))\n"
        "            __add_fig(__val, __name, getattr(__val, 'number', None), __name)\n"
        "except Exception:\n"
        "    __payload = {'ok': False, 'reason': __traceback.format_exc()}\n"
        "__out.parent.mkdir(parents=True, exist_ok=True)\n"
        "__out.write_text(__json.dumps(__payload), encoding='utf-8')\n"
    )


def build_console_figure_list_code(list_path: str | Path) -> str:
    """Return Python code that writes a JSON list of all figures."""
    list_path = str(list_path)
    return (
        "import json as __json\n"
        "import traceback as __traceback\n"
        "from pathlib import Path as __Path\n"
        "from matplotlib import pyplot as __plt\n"
        "from matplotlib.figure import Figure as __Figure\n"
        "try:\n"
        "    __ip = get_ipython()\n"
        "    __ns = __ip.user_ns if __ip else globals()\n"
        "except Exception:\n"
        "    __ns = globals()\n"
        f"__out = __Path({list_path!r})\n"
        "__payload = {'ok': True, 'figures': []}\n"
        "try:\n"
        "    __figs = []\n"
        "    __seen = set()\n"
        "    for __num in __plt.get_fignums():\n"
        "        __fig = __plt.figure(__num)\n"
        "        __seen.add(id(__fig))\n"
        "        __axes = []\n"
        "        for __idx, __ax in enumerate(__fig.axes):\n"
        "            __axes.append({\n"
        "                'index': __idx,\n"
        "                'title': __ax.get_title(),\n"
        "                'xlabel': __ax.get_xlabel(),\n"
        "                'ylabel': __ax.get_ylabel(),\n"
        "                'is3d': bool(getattr(__ax, 'get_zlim', None)),\n"
        "            })\n"
        "        __title = ''\n"
        "        if getattr(__fig, '_suptitle', None) is not None:\n"
        "            __title = __fig._suptitle.get_text()\n"
        "        __figs.append({'num': __num, 'var': None, 'title': __title, 'axes': __axes})\n"
        "    for __name, __val in __ns.items():\n"
        "        if isinstance(__val, __Figure) and id(__val) not in __seen:\n"
        "            __fig = __val\n"
        "            __seen.add(id(__fig))\n"
        "            __axes = []\n"
        "            for __idx, __ax in enumerate(__fig.axes):\n"
        "                __axes.append({\n"
        "                    'index': __idx,\n"
        "                    'title': __ax.get_title(),\n"
        "                    'xlabel': __ax.get_xlabel(),\n"
        "                    'ylabel': __ax.get_ylabel(),\n"
        "                    'is3d': bool(getattr(__ax, 'get_zlim', None)),\n"
        "                })\n"
        "            __title = ''\n"
        "            if getattr(__fig, '_suptitle', None) is not None:\n"
        "                __title = __fig._suptitle.get_text()\n"
        "            __num = getattr(__fig, 'number', None)\n"
        "            __figs.append({'num': __num, 'var': __name, 'title': __title, 'axes': __axes})\n"
        "    __payload['figures'] = __figs\n"
        "except Exception:\n"
        "    __payload = {'ok': False, 'reason': __traceback.format_exc()}\n"
        "__out.parent.mkdir(parents=True, exist_ok=True)\n"
        "__out.write_text(__json.dumps(__payload), encoding='utf-8')\n"
    )


def build_console_figure_export_code(
    fig_num: int | None,
    var_name: str | None,
    export_path: str | Path,
    status_path: str | Path,
) -> str:
    """Return Python code that pickles a single figure to disk."""
    export_path = str(export_path)
    status_path = str(status_path)
    return (
        "import json as __json\n"
        "import pickle as __pickle\n"
        "import traceback as __traceback\n"
        "from pathlib import Path as __Path\n"
        "from matplotlib import pyplot as __plt\n"
        "from matplotlib.figure import Figure as __Figure\n"
        "try:\n"
        "    __ip = get_ipython()\n"
        "    __ns = __ip.user_ns if __ip else globals()\n"
        "except Exception:\n"
        "    __ns = globals()\n"
        f"__fig_num = {repr(fig_num)}\n"
        f"__fig_var = {repr(var_name)}\n"
        f"__out = __Path({export_path!r})\n"
        f"__status = __Path({status_path!r})\n"
        "__payload = {\n"
        "    'ok': False,\n"
        "    'reason': 'No matplotlib figure found in Command Window.',\n"
        "}\n"
        "try:\n"
        "    __fig = None\n"
        "    if __fig_num is not None:\n"
        "        try:\n"
        "            __fig = __plt.figure(__fig_num)\n"
        "        except Exception:\n"
        "            __fig = None\n"
        "    if __fig is None and __fig_var:\n"
        "        __val = __ns.get(__fig_var)\n"
        "        if isinstance(__val, __Figure):\n"
        "            __fig = __val\n"
        "    if __fig is None:\n"
        "        __fignums = __plt.get_fignums()\n"
        "        if __fignums:\n"
        "            __fig = __plt.figure(__fignums[-1])\n"
        "    if __fig is None:\n"
        "        for __name, __val in __ns.items():\n"
        "            if isinstance(__val, __Figure):\n"
        "                __fig = __val\n"
        "    if __fig is not None:\n"
        "        __out.parent.mkdir(parents=True, exist_ok=True)\n"
        "        with __out.open('wb') as __handle:\n"
        "            __pickle.dump(__fig, __handle)\n"
        "        __payload = {'ok': True, 'path': str(__out)}\n"
        "except Exception:\n"
        "    __payload = {'ok': False, 'reason': __traceback.format_exc()}\n"
        "__status.parent.mkdir(parents=True, exist_ok=True)\n"
        "_ = __status.write_text(__json.dumps(__payload), encoding='utf-8')\n"
    )


# ── Manifest parsing ──────────────────────────────────────────────


def parse_plot_manifest(manifest_path: Path) -> list[dict]:
    """Parse the plots manifest JSON and return a flat list of plot items.

    Each item has keys: png_path, axes_bbox, fig_num, var_name,
    axes_index, title.  Returns ``[]`` on any error.
    """
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []

    if not payload.get("ok"):
        return []

    plot_items: list[dict] = []
    for entry in payload.get("figures", []):
        fig_num = entry.get("num")
        var_name = entry.get("var")
        png_path = entry.get("png")
        fig_title = str(entry.get("title") or "").strip()
        axes = entry.get("axes", [])
        if not png_path:
            continue
        if not isinstance(axes, list) or not axes:
            plot_items.append(
                {
                    "png_path": png_path,
                    "axes_bbox": None,
                    "fig_num": fig_num,
                    "var_name": var_name,
                    "axes_index": None,
                    "title": fig_title or "Figure",
                }
            )
            continue
        for axis in axes:
            idx = axis.get("index")
            axis_title = str(axis.get("title") or "").strip()
            label = axis_title or fig_title or "Plot"
            plot_items.append(
                {
                    "png_path": png_path,
                    "axes_bbox": axis.get("bbox"),
                    "fig_num": fig_num,
                    "var_name": var_name,
                    "axes_index": int(idx) if idx is not None else None,
                    "title": label,
                }
            )
    return plot_items
