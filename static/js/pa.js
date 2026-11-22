/* PA Worker – script chung: tự ẩn thông báo, tooltip, hộp xác nhận, CSRF cho HTMX. */
(function () {
  "use strict";

  function cookie(name) {
    var m = document.cookie.match("(?:^|; )" + name + "=([^;]*)");
    return m ? decodeURIComponent(m[1]) : "";
  }

  document.addEventListener("DOMContentLoaded", function () {
    // Thông báo tự ẩn sau 5 giây
    document.querySelectorAll("[data-pa-autohide]").forEach(function (el) {
      setTimeout(function () {
        el.remove();
      }, 5000);
    });

    // Tooltip cho nút icon
    document.querySelectorAll("[data-bs-toggle='tooltip']").forEach(function (el) {
      new bootstrap.Tooltip(el);
    });

    // Hộp xác nhận dùng chung: nút mở hộp truyền địa chỉ POST, tiêu đề, nội dung qua data-pa-*
    document.querySelectorAll("[data-pa-confirm]").forEach(function (modal) {
      var form = modal.querySelector("form");
      modal.addEventListener("show.bs.modal", function (ev) {
        var t = ev.relatedTarget;
        if (!t) return;
        if (t.dataset.paAction) form.action = t.dataset.paAction;
        if (t.dataset.paTitle) modal.querySelector("[data-pa-title]").textContent = t.dataset.paTitle;
        if (t.dataset.paMessage) modal.querySelector("[data-pa-message]").textContent = t.dataset.paMessage;
      });
      // Ô gõ lại mã để xác nhận: chỉ bật nút xác nhận khi khớp (máy chủ vẫn kiểm tra lại)
      var match = modal.querySelector("[data-pa-match]");
      var submit = modal.querySelector("[data-pa-submit]");
      if (match && submit) {
        submit.disabled = true;
        match.addEventListener("input", function () {
          submit.disabled = match.value.trim() !== match.dataset.paMatch;
        });
      }
    });

    // Ô tích "Đã kiểm tra" của màn hình đối chiếu: bật nút Lưu khi mọi ô vàng đã tích
    var gate = document.querySelector("[data-pa-gate]");
    if (gate) {
      var boxes = document.querySelectorAll("[data-pa-checked]");
      var update = function () {
        var ok = Array.prototype.every.call(boxes, function (b) {
          return b.checked;
        });
        gate.disabled = !ok;
      };
      boxes.forEach(function (b) {
        b.addEventListener("change", update);
      });
      update();
    }
  });

  // HTMX gửi kèm CSRF token
  document.body.addEventListener("htmx:configRequest", function (ev) {
    ev.detail.headers["X-CSRFToken"] = cookie("csrftoken");
  });
})();
