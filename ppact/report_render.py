"""
ppact.report_render - three adapters, one contract

WHY THREE FUNCTIONS AND NOT ONE
===============================
A terminal writes characters, a notebook displays figures and Streamlit
calls widgets. Forcing those into one function would put display
branching where the panel contract should be.

What must be one is not the number of functions:

    report builders     one
    panel contracts     one
    view-data schemas   one
    interface adapters  three

An adapter reads `EngineeringReportViewData` and formats it. An adapter
that computes has put the engine back into the interface, which is the
arrangement this file exists to end.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import os
from typing import List

from .engineering_report import (EngineeringReportViewData, Panel,
                                 PanelStatus, PANEL_ORDER)
from .outcome import WorkflowVariant


def _header(report) -> List[str]:
    return [
        f"  workflow      {report.workflow_id}",
        f"  application   {report.app_name}",
        f"  variant       {report.variant.value}",
    ] + ([f"  starting      {report.starting_label}",
          f"  current       {report.current_label}"]
         if report.comparative else
         [f"  design        {report.current_label}"]) + [
        f"  engine        {report.engine_version}"
        f"   model {report.model_digest}"]


def render_report_text(report: EngineeringReportViewData) -> List[str]:
    """The terminal adapter. Same panels, same order, as characters.

    A GRAPHIC PANEL GETS A TEXT FORM, not a filename and not silence.
    Printing "[figure] /tmp/x.png" in a terminal tells a reader a panel
    exists somewhere they cannot see it.
    """
    from .visual.text import wrap_text

    out: List[str] = ["=" * 70, " ENGINEERING REPORT", "=" * 70]
    out += _header(report)

    for panel in report.panels:
        out += ["", "-" * 70, f" {panel.title.upper()}", "-" * 70]
        if panel.status is not PanelStatus.READY:
            out.append(f"  {panel.status.value.upper()}"
                       + (f" - {panel.note}" if panel.note else ""))
            continue

        for line in panel.lines:
            for w in wrap_text(line, 66):
                out.append(f"  {w}")

        if panel.rows:
            # 78 COLUMNS. A table wider than the terminal wraps into
            # nonsense, which is worse than a narrower column.
            w_lab, w_val, w_d = 24, 13, 9
            if report.comparative:
                out.append(f"  {'':{w_lab}s}{'starting':>{w_val}s}"
                           f"{'current':>{w_val}s}{'':>{w_d}s}")
            for row in panel.rows:
                cells = (f"  {row.label[:w_lab]:<{w_lab}s}"
                         + (f"{row.starting[:w_val]:>{w_val}s}"
                            if report.comparative else "")
                         + f"{row.current[:w_val]:>{w_val}s}"
                         + f"{row.delta[:w_d]:>{w_d}s}")
                if row.mark:
                    cells += f"  {row.mark[:12]}"
                out.append(cells.rstrip()[:78])

        if panel.image:
            # The figure exists; a terminal cannot show it, and saying
            # where it is beats pretending the panel is empty.
            out.append(f"  figure: {os.path.basename(panel.image)}")
        # A panel whose content is a picture has no rows and still
        # has something to say about it.
        if panel.note:
            for w in wrap_text(panel.note, 66):
                out.append(f"  {w}")
    return out


def render_report_jupyter(report: EngineeringReportViewData) -> bool:
    """The notebook adapter. Every panel displayed explicitly.

    Relying on the last figure, or on one global show(), is how three of
    four pictures went missing without anything reporting it.
    """
    try:
        from IPython.display import Image, Markdown, display
    except ImportError:
        return False

    display(Markdown("### Engineering Report"))
    display(Markdown("  \n".join(
        line.strip() for line in _header(report))))

    for panel in report.panels:
        # THE NOTEBOOK ADAPTER, not the Streamlit one.
        #
        # This loop had been overwritten with `st.container(...)` while
        # `render_report_streamlit` was being rewritten, so a notebook
        # run printed the report header and then raised
        # NameError: name 'st' is not defined. `st` is a parameter of
        # the Streamlit adapter and has no meaning in this function.
        #
        # The suites did not catch it: ST-15 executed a real kernel but
        # went through `render_demo_review`, and nothing exercised
        # `render_report_jupyter` itself.
        display(Markdown(f"**{panel.title}**"))
        if panel.status is not PanelStatus.READY:
            display(Markdown(f"*{panel.status.value}"
                             + (f" - {panel.note}" if panel.note
                                else "") + "*"))
            continue
        for line in panel.lines:
            display(Markdown(line))
        if panel.rows:
            display(Markdown(_rows_markdown(report, panel)))
        # EVERY FIGURE DISPLAYED EXPLICITLY. Relying on the last one is
        # how three of four pictures went missing without anything
        # reporting it.
        if panel.image and os.path.isfile(panel.image):
            display(Image(filename=panel.image))
        if panel.note:
            display(Markdown(f"*{panel.note}*"))
    return True


def render_report_streamlit(report: EngineeringReportViewData, st):
    """The Streamlit adapter. `st` is passed in, not imported.

    Importing Streamlit here would make the engine package depend on a
    web framework, and every terminal run would pay for it.
    """
    st.markdown(f"**{report.app_name}**")

    # STACKED, NOT TWO BIG METRICS.
    #
    # `st.metric` truncates: at 768 px both designs read "npu_32x32 …"
    # and the reader could not tell them apart. On a comparison screen
    # that is not cosmetic - the whole point is the difference.
    if report.comparative:
        st.markdown(f"**Starting point** — {report.starting_label}")
        st.markdown(f"**Current design** — {report.current_label}")
    else:
        st.markdown(f"**Design** — {report.current_label}")

    # The workflow id and digests are for tracing a figure back, not for
    # reading a result. They sit with the other technical detail.
    with st.expander("Technical details"):
        st.caption(f"workflow `{report.workflow_id}`  ·  "
                   f"{report.variant.value}")
        st.caption(f"engine {report.engine_version}  ·  model "
                   f"{report.model_digest}")

    for panel in report.panels:
        # A CONTAINER PER PANEL.
        #
        # Streamlit scrolls `section.stMain`, not the window: the
        # document stays one screen tall however long the report is, so
        # `full_page` captures one screen and a page-coordinate clip
        # lands outside the image. Three capture attempts failed for
        # three different reasons before the scroll owner was measured
        # rather than assumed. A panel inside its own container can be
        # screenshotted as an element, and the browser scrolls it into
        # view itself.
        with st.container(key=f"panel_{panel.key.value}"):
            st.markdown(
                f'<div data-panel="{panel.key.value}" '
                f'data-panel-status="{panel.status.value}"></div>',
                unsafe_allow_html=True)
            st.subheader(panel.title)
            if panel.status is not PanelStatus.READY:
                st.info(f"{panel.status.value}"
                        + (f" — {panel.note}" if panel.note else ""))
            else:
                for line in panel.lines:
                    st.markdown(line)
                if panel.rows:
                    st.dataframe(_rows_table(report, panel),
                                 use_container_width=True,
                                 hide_index=True)
                if panel.image and os.path.isfile(panel.image):
                    st.image(panel.image, use_container_width=True)
                # A NOTE BELONGS TO ITS PANEL, not to its table.
                #
                # `and panel.rows` meant a panel whose content is a
                # picture never showed its note, so the Architecture
                # Balance drew two axes marked `n/e` and said nothing
                # about what `n/e` means or why those two carry it.
                if panel.note:
                    st.caption(panel.note)
            st.markdown(
                f'<div data-panel-end="{panel.key.value}"></div>',
                unsafe_allow_html=True)


def _rows_table(report, panel):
    """One table shape for every panel and every interface."""
    cols = {"": [r.label for r in panel.rows]}
    if report.comparative:
        cols["starting point"] = [r.starting for r in panel.rows]
    cols["current"] = [r.current for r in panel.rows]
    if any(r.delta for r in panel.rows):
        cols["change"] = [r.delta for r in panel.rows]
    if any(r.mark for r in panel.rows):
        cols[" "] = [r.mark for r in panel.rows]
    return cols


def _rows_markdown(report, panel) -> str:
    table = _rows_table(report, panel)
    heads = list(table)
    out = ["| " + " | ".join(h or "&nbsp;" for h in heads) + " |",
           "|" + "|".join("---" for _ in heads) + "|"]
    for i in range(len(panel.rows)):
        out.append("| " + " | ".join(str(table[h][i])
                                     for h in heads) + " |")
    return "\n".join(out)
