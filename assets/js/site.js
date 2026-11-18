document.querySelectorAll("[data-more]").forEach((btn) => {
  const list = document.getElementById(btn.dataset.more);
  const step = Number(btn.dataset.step || 3);
  btn.addEventListener("click", () => {
    const hidden = list.querySelectorAll(":scope > [hidden]");
    hidden.forEach((el, i) => {
      if (i < step) el.hidden = false;
    });
    if (hidden.length <= step) btn.remove();
  });
});

const projectList = document.getElementById("lista-proyectos");
if (projectList) {
  const rows = [...projectList.children];
  const moreBtn = document.querySelector('[data-more="lista-proyectos"]');
  const note = document.getElementById("filtro-herramienta");
  let cat = "";
  let tool = "";

  function apply() {
    const filtering = Boolean(cat || tool);
    let shown = 0;
    rows.forEach((row, i) => {
      const okCat = !cat || row.dataset.cat === cat;
      const okTool = !tool || row.dataset.tools.split("|").includes(tool);
      const visible = okCat && okTool;
      row.classList.toggle("is-out", !visible);
      row.hidden = !filtering && i >= 3;
      if (visible) shown++;
    });
    if (moreBtn) moreBtn.hidden = filtering;
    note.hidden = !tool;
    note.textContent = tool ? note.dataset.msg.replace("{tool}", tool).replace("{n}", shown) : "";
  }

  document.querySelectorAll(".filters .chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      cat = btn.dataset.cat;
      document.querySelectorAll(".filters .chip").forEach((b) => b.setAttribute("aria-pressed", b === btn));
      apply();
    });
  });

  document.querySelectorAll(".chip[data-tool]").forEach((btn) => {
    btn.addEventListener("click", () => {
      tool = tool === btn.dataset.tool ? "" : btn.dataset.tool;
      document.querySelectorAll(".chip[data-tool]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.tool === tool));
      apply();
      if (tool) document.getElementById("proyectos").scrollIntoView({ behavior: "smooth" });
    });
  });
}

const observer = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (entry.isIntersecting) {
      entry.target.classList.add("in");
      observer.unobserve(entry.target);
    }
  });
}, { threshold: 0.15 });

document.querySelectorAll(".panel, .contact, .timeline").forEach((el) => observer.observe(el));