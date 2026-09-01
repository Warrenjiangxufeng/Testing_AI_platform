window.addEventListener("DOMContentLoaded", () => {
  // ---------- Tab 切换 ----------
  document.querySelectorAll(".tabs").forEach((tabs) => {
    const buttons = tabs.querySelectorAll(".tab");
    const panels = document.querySelectorAll(".tab-panel");
    buttons.forEach((btn) => {
      btn.addEventListener("click", () => {
        buttons.forEach((b) => b.classList.toggle("active", b === btn));
        const target = btn.getAttribute("data-tab");
        panels.forEach((p) => p.classList.toggle("active", p.id === target));
      });
    });
  });

  // ---------- 左侧菜单：滑动指示器 + 点击动效 ----------
  const nav = document.getElementById("sidenav");
  const ind = document.getElementById("sidenav-indicator");
  const activeItem = nav ? nav.querySelector(".sidenav-item.active") : null;

  if (nav && ind && activeItem) {
    const top = activeItem.offsetTop;
    const height = activeItem.offsetHeight;
    ind.style.transition = "none";
    ind.style.top = top + 26 + "px";
    ind.style.height = height + "px";
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        ind.style.transition =
          "top .5s cubic-bezier(0.22,0.61,0.36,1), height .5s cubic-bezier(0.22,0.61,0.36,1)";
        ind.style.top = top + "px";
      });
    });
  }

  const moveIndicator = (item) => {
    if (!ind || !item) return;
    ind.style.top = item.offsetTop + "px";
    ind.style.height = item.offsetHeight + "px";
  };
  document.querySelectorAll(".sidenav-item").forEach((item) => {
    item.addEventListener("click", () => moveIndicator(item));
  });

  // ---------- 涟漪动效（按钮 & 菜单）----------
  const addRipple = (el, e) => {
    const rect = el.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height);
    const ripple = document.createElement("span");
    ripple.className = "ripple";
    ripple.style.width = ripple.style.height = size + "px";
    ripple.style.left = e.clientX - rect.left - size / 2 + "px";
    ripple.style.top = e.clientY - rect.top - size / 2 + "px";
    el.appendChild(ripple);
    setTimeout(() => ripple.remove(), 520);
  };
  document
    .querySelectorAll(".sidenav-item, .btn:not(.btn-sm), .btn-sm, .quick-card, .stat-card")
    .forEach((el) => el.addEventListener("pointerdown", (e) => addRipple(el, e)));

  // ---------- 删除类操作二次确认 ----------
  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (e) => {
      const msg = form.getAttribute("data-confirm") || "确认执行该操作？";
      if (!window.confirm(msg)) e.preventDefault();
    });
  });

  // ---------- 复制按钮 ----------
  document.querySelectorAll(".copy-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = document.getElementById(btn.getAttribute("data-target"));
      if (!target) return;
      navigator.clipboard
        .writeText(target.textContent)
        .then(() => {
          const old = btn.textContent;
          btn.textContent = "已复制 ✓";
          setTimeout(() => (btn.textContent = old), 1500);
        })
        .catch(() => (btn.textContent = "复制失败"));
    });
  });

  // ---------- 提交加载态（表单提交时禁用按钮）----------
  document.querySelectorAll("form").forEach((form) => {
    form.addEventListener("submit", (e) => {
      if (e.defaultPrevented) return;
      if (form.hasAttribute("data-no-loading")) return;
      const btn = form.querySelector("button[type='submit']");
      if (btn) {
        btn.disabled = true;
        btn.classList.add("is-loading");
        const t = btn.dataset.loading;
        if (t) btn.textContent = t;
      }
    });
  });

  // ---------- flash 自动消失 ----------
  document.querySelectorAll(".flash").forEach((el) => {
    setTimeout(() => {
      el.style.transition = "opacity .4s ease, transform .4s ease";
      el.style.opacity = "0";
      el.style.transform = "translateY(-8px)";
      setTimeout(() => el.remove(), 400);
    }, 3500);
  });
});
