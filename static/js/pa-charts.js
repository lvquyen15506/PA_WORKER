/* Biểu đồ Chart.js theo pa-ui mục 7: màu lấy từ token CSS, không 3D, không gradient, không hiệu ứng.
   Dùng: <canvas data-pa-chart="id-của-json_script"> với JSON
     {type: "bar", labels, unit, values}                       một chuỗi (màu navy)
     {type: "bar", labels, unit, datasets: [{label, values}]}  nhiều chuỗi (navy, blue, muted), có chú thích
   Thêm "horizontal": true để vẽ cột ngang (nhãn dài, ví dụ tên phòng ban, công ty). */
(function () {
  "use strict";

  function token(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (typeof Chart === "undefined") return;
    document.querySelectorAll("canvas[data-pa-chart]").forEach(function (canvas) {
      var cfg = JSON.parse(document.getElementById(canvas.dataset.paChart).textContent);
      var grid = token("--pa-border");
      var series = [token("--pa-navy"), token("--pa-blue"), token("--pa-muted")];
      var source = cfg.datasets || [{ label: cfg.unit, values: cfg.values }];
      var horizontal = !!cfg.horizontal;
      var valueAxis = {
        beginAtZero: true,
        ticks: { precision: 0 },
        grid: { color: grid },
        border: { color: grid },
        title: { display: true, text: cfg.unit },
      };
      var labelAxis = { grid: { color: grid }, border: { color: grid } };
      Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
      Chart.defaults.color = token("--pa-text");
      new Chart(canvas, {
        type: cfg.type || "bar",
        data: {
          labels: cfg.labels,
          datasets: source.map(function (s, i) {
            return {
              label: s.label,
              data: s.values,
              backgroundColor: series[i % series.length],
              borderRadius: 0,
            };
          }),
        },
        options: {
          indexAxis: horizontal ? "y" : "x",
          responsive: true,
          maintainAspectRatio: false,
          animation: false,
          plugins: { legend: { display: source.length > 1 } },
          scales: horizontal ? { x: valueAxis, y: labelAxis } : { x: labelAxis, y: valueAxis },
        },
      });
    });
  });
})();
