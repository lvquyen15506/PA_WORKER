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

    // Nhãn nguồn: ô có giá trị máy đọc (data-pa-orig) bị sửa thì nhãn đổi thành "Nhập tay"
    document.querySelectorAll("[data-pa-orig]").forEach(function (el) {
      var tag = document.querySelector("label[for='" + el.id + "'] .pa-source");
      if (!tag) return;
      var original = tag.textContent;
      var refresh = function () {
        tag.textContent = el.value.trim() === el.dataset.paOrig.trim() ? original : "Nhập tay";
      };
      el.addEventListener("input", refresh);
      el.addEventListener("change", refresh);
    });

    // "Đưa vào trường…": đưa đoạn chữ HR đang bôi đen trong văn bản CV (hoặc giá trị gợi ý) vào ô đích
    function putInto(targetId, text, clean) {
      var target = document.getElementById(targetId);
      if (!target || !text) return false;
      if (clean === "phone") text = text.replace(/[\s.\-]/g, "");
      if (target.tagName === "TEXTAREA" && target.value.trim()) {
        target.value = target.value.replace(/\s+$/, "") + "\n" + text;
      } else {
        target.value = text;
      }
      target.dispatchEvent(new Event("input", { bubbles: true }));
      target.dispatchEvent(new Event("change", { bubbles: true }));
      return true;
    }
    var cvText = document.getElementById("id_cv_text");
    var cvMessage = document.querySelector("[data-pa-cv-message]");
    document.querySelectorAll("[data-pa-insert-selection]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var selected = cvText
          ? cvText.value.substring(cvText.selectionStart, cvText.selectionEnd).trim()
          : "";
        var done = putInto(btn.dataset.paInsertSelection, selected, btn.dataset.paClean);
        if (cvMessage) {
          cvMessage.textContent = done
            ? "Đã đưa đoạn chữ vào ô " + btn.textContent.trim() + ". Kiểm tra và sửa lại nếu cần."
            : "Hãy bôi đen một đoạn trong văn bản CV trước khi chọn Đưa vào trường…";
        }
      });
    });
    document.querySelectorAll("[data-pa-insert-value]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        putInto(btn.dataset.paTarget, btn.dataset.paInsertValue, "");
      });
    });
  });

  // HTMX gửi kèm CSRF token
  document.body.addEventListener("htmx:configRequest", function (ev) {
    ev.detail.headers["X-CSRFToken"] = cookie("csrftoken");
  });
})();
