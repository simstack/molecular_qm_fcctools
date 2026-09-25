import logging
from typing import List
from simstack.models import ArtifactModel

from simstack.models.charts_artifact import (
    ChartArtifactModel,
    AGLineSeriesConfig,
    AGChartAxisConfig,
    AGChartTitleConfig,
    AGChartLegendConfig
)

#  TODO Fix charts
#
# AG Charts - Option `series[0].tooltip` is required and has not been provided; expecting an object, ignoring.
# main.esm.mjs:24AG Charts - Option `series[0].lineDash` cannot be set to `null`; expecting a number greater than or equal to 0 array, ignoring.
# main.esm.mjs:24AG Charts - Option `animation` cannot be set to `false`; expecting an object, ignoring.
# main.esm.mjs:24AG Charts - Unknown option `autoSize`, ignoring.
# main.esm.mjs:24AG Charts - Option `axes[0].label` is required and has not been provided; expecting an object, ignoring.
# main.esm.mjs:24AG Charts - Unknown option `axes[0].tick.count`, ignoring.
# main.esm.mjs:24AG Charts - Option `axes[0].title` cannot be set to `"X"`; expecting an object, ignoring.
# main.esm.mjs:24AG Charts - Option `axes[0].min` cannot be set to `null`; expecting a number and the value to be less than `max`, ignoring.
# main.esm.mjs:24AG Charts - Option `axes[0].max` cannot be set to `null`; expecting a number and the value to be greater than `min`, ignoring.
# main.esm.mjs:24AG Charts - Unknown option `axes[0].gridStyle`, ignoring.
# main.esm.mjs:24AG Charts - Option `axes[1].label` is required and has not been provided; expecting an object, ignoring.
# main.esm.mjs:24AG Charts - Unknown option `axes[1].tick.count`, ignoring.
# main.esm.mjs:24AG Charts - Option `axes[1].title` cannot be set to `"Y"`; expecting an object, ignoring.
# main.esm.mjs:24AG Charts - Option `axes[1].min` cannot be set to `null`; expecting a number and the value to be less than `max`, ignoring.
# main.esm.mjs:24AG Charts - Option `axes[1].max` cannot be set to `null`; expecting a number and the value to be greater than `min`, ignoring.
# main.esm.mjs:24AG Charts - Unknown option `axes[1].gridStyle`, ignoring.

logger = logging.getLogger(__name__)

def make_multi_line_chart(artifact_list: List[ArtifactModel], **kwargs) -> ChartArtifactModel:
    """
    Create a multi-series XY line chart artifact.

    Uses the (new) ChartArtifactModel by:
      - placing the full chart data in ChartArtifactModel.data
      - having each series reference the same combined data set via yKey
      - pushing extra AG-Charts options (like zoom) into ChartArtifactModel.options
    """
    task_id = kwargs.get("task_id", None)
    chart_title_text = kwargs.get("chart_title", "Chart")
    x_axis_title = kwargs.get("x_axis_title", "X")
    y_axis_title = kwargs.get("y_axis_title", "Y")
    x_key = kwargs.get("x_key", None)
    y_key = kwargs.get("y_key", None)

    logger.info(f"Creating multi-line chart with x_key: {x_key} and y_key: {y_key} task_id: {task_id}")


    if x_key is None or y_key is None:
        raise ValueError("x_key and y_key must be provided.")

    if not artifact_list:
        return ChartArtifactModel(
            parent_id=task_id,
            data=[],
            title=AGChartTitleConfig(text=chart_title_text),
            series=[],
            axes=[
                AGChartAxisConfig(type="number", position="bottom", title=x_axis_title),
                AGChartAxisConfig(type="number", position="left", title=y_axis_title),
            ],
            legend=AGChartLegendConfig(enabled=True, position="right", spacing=15),
        )

    # Build a single combined table:
    #   row = {x_key: x, "<series_0>": y0, "<series_1>": y1, ...}
    # so each AGLineSeriesConfig can use a different yKey but share the same data.
    def _series_key(name: str, idx: int) -> str:
        safe = "".join(ch if (ch.isalnum() or ch in ("_", "-")) else "_" for ch in (name or "series"))
        return f"{safe}__{idx}"

    colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FECA57"]

    combined_rows: dict[float, dict] = {}
    series_meta: list[tuple[str, str, str]] = []

    # Track ranges (only set min/max when we actually have values)
    x_min = float("inf")
    x_max = float("-inf")
    y_min = float("inf")
    y_max = float("-inf")

    for idx, artifact in enumerate(artifact_list):
        logger.info(
            f"Creating multi-line chart with x_key: {x_key} and y_key: {y_key} task_id: {task_id}"
        )

        plot_data = artifact.data.get("plot_data", [])
        if plot_data is None:
            continue

        this_y_key = _series_key(getattr(artifact, "name", "series"), idx)
        color = colors[idx % len(colors)]

        for point in plot_data:
            if x_key not in point or y_key not in point:
                continue
            x_val = float(point[x_key])
            y_val = float(point[y_key])

            x_min = min(x_min, x_val)
            x_max = max(x_max, x_val)
            y_min = min(y_min, y_val)
            y_max = max(y_max, y_val)

            row = combined_rows.setdefault(x_val, {x_key: x_val})
            row[this_y_key] = y_val

        series_meta.append((this_y_key, color, getattr(artifact, "name", this_y_key)))

    combined_data = [combined_rows[k] for k in sorted(combined_rows.keys())]
    series_configs = [
        AGLineSeriesConfig(
            type="line",
            xKey=x_key,
            yKey=this_y_key,
            title=title,
            data=combined_data,
            stroke=color,
            strokeWidth=2,
            strokeOpacity=1.0,
            marker={"enabled": True, "size": 3, "fill": color},
            tooltip={},
        )
        for this_y_key, color, title in series_meta
    ]

    axes = [
        AGChartAxisConfig(
            type="number",
            position="bottom",
            title=x_axis_title,
            min=(x_min if x_min != float("inf") else None),
            max=(x_max if x_max != float("-inf") else None),
        ),
        AGChartAxisConfig(
            type="number",
            position="left",
            title=y_axis_title,
            min=(y_min if y_min != float("inf") else None),
            max=(y_max if y_max != float("-inf") else None),
        ),
    ]

    legend = AGChartLegendConfig(enabled=True, position="right", spacing=15)

    return ChartArtifactModel(
        parent_id=task_id,
        data=combined_data,
        title=AGChartTitleConfig(text=chart_title_text),
        series=series_configs,
        axes=axes,
        legend=legend,
        width=900,
        height=600,
        padding={"top": 30, "right": 80, "bottom": 60, "left": 60},
        theme="ag-default",
        animation={"enabled": True, "duration": 1200},
        # Keep non-modelled/experimental chart options here
        options={"zoom": {"enabled": True, "enableSelecting": True, "enableScrolling": True}},
    )